package mx.unach.dosys.data.repository

import kotlinx.coroutines.CancellationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import mx.unach.dosys.core.auth.SessionManager
import mx.unach.dosys.data.model.AppointmentAvailabilityResponse
import mx.unach.dosys.data.model.AppointmentRequest
import mx.unach.dosys.data.model.CheckInRequest
import mx.unach.dosys.data.model.DoctorOption
import mx.unach.dosys.data.model.DocumentIntegrityResponse
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.data.model.PatientConsultation
import mx.unach.dosys.data.model.PatientDocument
import mx.unach.dosys.data.model.PatientPrescription
import mx.unach.dosys.data.model.PatientProfile
import mx.unach.dosys.data.model.PatientStudy
import mx.unach.dosys.data.remote.ApiService
import mx.unach.dosys.data.remote.SessionExpiredException
import mx.unach.dosys.data.remote.TokenRefresher
import retrofit2.HttpException
import java.io.IOException

sealed interface ClinicalResult<out T> {
    data class Success<T>(val value: T) : ClinicalResult<T>
    data class Error(
        val message: String,
        val code: Int? = null,
    ) : ClinicalResult<Nothing>
}

/** Mensajes visibles del flujo de solicitud de cita. */
internal fun appointmentRequestMessage(code: Int, serverDetail: String? = null): String = when (code) {
    401 -> "Tu sesión terminó. Inicia sesión nuevamente"
    409 -> "Ese horario acaba de ocuparse. Elige otro."
    422 -> serverDetail?.takeIf { it.isNotBlank() } ?: "Revisa los datos de la solicitud."
    429 -> "Espera un minuto antes de intentar de nuevo."
    else -> "No se pudo solicitar la cita. Intenta más tarde."
}

/** Datos clínicos visibles exclusivamente para el paciente autenticado. */
interface PatientRepository {
    suspend fun profile(): ClinicalResult<PatientProfile>
    suspend fun consultations(): ClinicalResult<List<PatientConsultation>>
    suspend fun appointments(): ClinicalResult<List<PatientAppointment>>
    suspend fun doctors(): ClinicalResult<List<DoctorOption>>
    suspend fun availability(doctorId: Int, date: String): ClinicalResult<AppointmentAvailabilityResponse>
    suspend fun requestAppointment(request: AppointmentRequest): ClinicalResult<PatientAppointment>
    suspend fun documents(): ClinicalResult<List<PatientDocument>>
    suspend fun verifyDocument(documentId: Int): ClinicalResult<DocumentIntegrityResponse>
    suspend fun studies(): ClinicalResult<List<PatientStudy>>
    suspend fun prescriptions(): ClinicalResult<List<PatientPrescription>>
    suspend fun documentFile(documentId: Int): ClinicalResult<ByteArray>
    suspend fun checkIn(appointmentId: Int, code: String): ClinicalResult<PatientAppointment>
    suspend fun checkInWithCode(code: String): ClinicalResult<PatientAppointment>
}

class RemotePatientRepository(
    private val api: ApiService,
    private val session: SessionManager,
    private val refresher: TokenRefresher,
) : PatientRepository {

    override suspend fun profile(): ClinicalResult<PatientProfile> = authorized { header ->
        api.me(header)
    }

    override suspend fun consultations(): ClinicalResult<List<PatientConsultation>> = authorized { header ->
        api.myConsultations(header)
    }

    override suspend fun appointments(): ClinicalResult<List<PatientAppointment>> = authorized { header ->
        api.myAppointments(header)
    }

    override suspend fun doctors(): ClinicalResult<List<DoctorOption>> =
        authorized("No se pudieron cargar los médicos.") { header ->
            api.appointmentDoctors(header)
        }

    override suspend fun availability(
        doctorId: Int,
        date: String,
    ): ClinicalResult<AppointmentAvailabilityResponse> =
        authorized("No se pudieron cargar los horarios disponibles.") { header ->
            api.appointmentAvailability(header, doctorId, date)
        }

    override suspend fun requestAppointment(request: AppointmentRequest): ClinicalResult<PatientAppointment> {
        return try {
            ClinicalResult.Success(refresher.withFreshToken { header ->
                api.requestAppointment(header, request)
            })
        } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (error: SessionExpiredException) {
            session.clear()
            ClinicalResult.Error("Tu sesión terminó. Inicia sesión nuevamente", 401)
        } catch (error: HttpException) {
            when (error.code()) {
                401 -> {
                    session.clear()
                    ClinicalResult.Error(appointmentRequestMessage(401), 401)
                }
                409 -> ClinicalResult.Error(appointmentRequestMessage(409), 409)
                422 -> ClinicalResult.Error(
                    appointmentRequestMessage(422, error.serverMessage()),
                    422,
                )
                429 -> ClinicalResult.Error(appointmentRequestMessage(429), 429)
                else -> ClinicalResult.Error(
                    appointmentRequestMessage(error.code()),
                    error.code(),
                )
            }
        } catch (error: IOException) {
            ClinicalResult.Error("No se pudo conectar con el servidor")
        } catch (error: Exception) {
            ClinicalResult.Error("No se pudo solicitar la cita. Intenta más tarde.")
        }
    }

    override suspend fun documents(): ClinicalResult<List<PatientDocument>> = authorized { header ->
        api.myDocuments(header)
    }

    override suspend fun verifyDocument(
        documentId: Int,
    ): ClinicalResult<DocumentIntegrityResponse> =
        authorized("No se pudo verificar la firma electrónica.") { header ->
            api.verifyDocument(header, documentId)
        }

    override suspend fun studies(): ClinicalResult<List<PatientStudy>> = authorized { header ->
        api.myStudies(header)
    }

    override suspend fun prescriptions(): ClinicalResult<List<PatientPrescription>> = authorized { header ->
        api.myPrescriptions(header)
    }

    override suspend fun documentFile(documentId: Int): ClinicalResult<ByteArray> {
        val token = session.currentToken()
            ?: return ClinicalResult.Error("Tu sesión terminó. Inicia sesión nuevamente")

        return try {
            ClinicalResult.Success(api.documentFile("Bearer $token", documentId).bytes())
        } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (error: HttpException) {
            if (error.code() == 401) {
                session.clear()
                ClinicalResult.Error("Tu sesión terminó. Inicia sesión nuevamente")
            } else {
                ClinicalResult.Error("No se pudo descargar el documento")
            }
        } catch (error: IOException) {
            ClinicalResult.Error("No se pudo conectar con el servidor")
        } catch (error: Exception) {
            ClinicalResult.Error("No se pudo descargar el documento")
        }
    }

    override suspend fun checkIn(appointmentId: Int, code: String): ClinicalResult<PatientAppointment> {
        val token = session.currentToken()
            ?: return ClinicalResult.Error("Tu sesión terminó. Inicia sesión nuevamente")

        return try {
            ClinicalResult.Success(api.checkIn("Bearer $token", appointmentId, CheckInRequest(code.trim().uppercase())))
        } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (error: HttpException) {
            checkInError(error)
        } catch (error: IOException) {
            ClinicalResult.Error("No se pudo conectar con el servidor")
        } catch (error: Exception) {
            ClinicalResult.Error("No se pudo confirmar la llegada. Intenta más tarde")
        }
    }

    override suspend fun checkInWithCode(code: String): ClinicalResult<PatientAppointment> {
        val token = session.currentToken()
            ?: return ClinicalResult.Error("Tu sesión terminó. Inicia sesión nuevamente")

        return try {
            ClinicalResult.Success(api.checkInWithCode("Bearer $token", CheckInRequest(code.trim().uppercase())))
        } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (error: HttpException) {
            checkInError(error)
        } catch (error: IOException) {
            ClinicalResult.Error("No se pudo conectar con el servidor")
        } catch (error: Exception) {
            ClinicalResult.Error("No se pudo confirmar la llegada. Intenta más tarde")
        }
    }

    private suspend fun checkInError(error: HttpException): ClinicalResult.Error {
        if (error.code() == 401) {
            session.clear()
            return ClinicalResult.Error("Tu sesión terminó. Inicia sesión nuevamente")
        }
        val detail = runCatching {
            val body = error.response()?.errorBody()?.string().orEmpty()
            Regex("\"detail\"\\s*:\\s*\"([^\"]+)\"").find(body)?.groupValues?.get(1)
        }.getOrNull()
        val message = when (error.code()) {
            400 -> detail ?: "El código no corresponde a ninguna cita vigente"
            404 -> "No encontramos esa cita en tu expediente"
            409 -> detail ?: "El check-in no está disponible en este momento"
            429 -> "Demasiados intentos. Espera un minuto."
            else -> "No se pudo confirmar la llegada. Intenta más tarde"
        }
        return ClinicalResult.Error(message)
    }

    private fun HttpException.serverMessage(): String? {
        val body = runCatching { response()?.errorBody()?.string().orEmpty() }.getOrDefault("")
        if (body.isBlank()) return null
        return runCatching {
            val detail = Json.parseToJsonElement(body).jsonObject["detail"]
            when (detail) {
                is JsonPrimitive -> detail.contentOrNull
                is JsonArray -> detail.mapNotNull { element ->
                    (element as? JsonObject)?.get("msg")?.jsonPrimitive?.contentOrNull
                }.joinToString(" ").ifBlank { null }
                else -> null
            }
        }.getOrNull()?.takeIf { it.isNotBlank() }
    }

    private suspend fun <T> authorized(
        errorMessage: String = "No se pudo obtener la información clínica",
        call: suspend (String) -> T,
    ): ClinicalResult<T> {
        return try {
            ClinicalResult.Success(refresher.withFreshToken(call))
        } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (error: SessionExpiredException) {
            session.clear()
            ClinicalResult.Error("Tu sesión terminó. Inicia sesión nuevamente", 401)
        } catch (error: HttpException) {
            if (error.code() == 401) {
                session.clear()
                ClinicalResult.Error("Tu sesión terminó. Inicia sesión nuevamente", 401)
            } else {
                ClinicalResult.Error(errorMessage, error.code())
            }
        } catch (error: IOException) {
            ClinicalResult.Error("No se pudo conectar con el servidor")
        } catch (error: Exception) {
            ClinicalResult.Error(errorMessage)
        }
    }
}
