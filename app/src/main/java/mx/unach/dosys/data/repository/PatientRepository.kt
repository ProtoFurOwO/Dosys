package mx.unach.dosys.data.repository

import kotlinx.coroutines.CancellationException
import mx.unach.dosys.core.auth.SessionManager
import mx.unach.dosys.data.model.CheckInRequest
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
    data class Error(val message: String) : ClinicalResult<Nothing>
}

/** Datos clínicos visibles exclusivamente para el paciente autenticado. */
interface PatientRepository {
    suspend fun profile(): ClinicalResult<PatientProfile>
    suspend fun consultations(): ClinicalResult<List<PatientConsultation>>
    suspend fun appointments(): ClinicalResult<List<PatientAppointment>>
    suspend fun documents(): ClinicalResult<List<PatientDocument>>
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

    override suspend fun documents(): ClinicalResult<List<PatientDocument>> = authorized { header ->
        api.myDocuments(header)
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

    private suspend fun <T> authorized(call: suspend (String) -> T): ClinicalResult<T> {
        return try {
            ClinicalResult.Success(refresher.withFreshToken(call))
        } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (error: SessionExpiredException) {
            session.clear()
            ClinicalResult.Error("Tu sesión terminó. Inicia sesión nuevamente")
        } catch (error: HttpException) {
            if (error.code() == 401) {
                session.clear()
                ClinicalResult.Error("Tu sesión terminó. Inicia sesión nuevamente")
            } else {
                ClinicalResult.Error("No se pudo obtener la información clínica")
            }
        } catch (error: IOException) {
            ClinicalResult.Error("No se pudo conectar con el servidor")
        } catch (error: Exception) {
            ClinicalResult.Error("No se pudo obtener la información clínica")
        }
    }
}
