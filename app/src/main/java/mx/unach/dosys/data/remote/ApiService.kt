package mx.unach.dosys.data.remote

import mx.unach.dosys.data.model.LoginRequest
import mx.unach.dosys.data.model.LoginResponse
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.data.model.PatientConsultation
import mx.unach.dosys.data.model.PatientProfile
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

/**
 * Contrato de la API REST (backend en FastAPI).
 *
 * Nota de seguridad: el rol PACIENTE solo dispone de endpoints de LECTURA.
 * La única escritura permitida es el inicio de sesión y, más adelante,
 * marcar la toma de un medicamento y confirmar/cancelar una cita.
 */
interface ApiService {

    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @GET("patients/me")
    suspend fun me(@Header("Authorization") authorization: String): PatientProfile

    @GET("patients/me/consultations")
    suspend fun myConsultations(@Header("Authorization") authorization: String): List<PatientConsultation>

    @GET("patients/me/appointments")
    suspend fun myAppointments(@Header("Authorization") authorization: String): List<PatientAppointment>

    // Próximos endpoints:
    // @GET("study-orders")         estudios y resultados
    // @GET("prescriptions")        recetas + tomas
    // @POST("qr/token")            token temporal para el check-in
}
