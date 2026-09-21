package mx.unach.dosys.data.remote

import mx.unach.dosys.data.model.CheckInRequest
import mx.unach.dosys.data.model.LoginRequest
import mx.unach.dosys.data.model.LoginResponse
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.data.model.PatientConsultation
import mx.unach.dosys.data.model.PatientProfile
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path

/**
 * Contrato de la API REST (backend en FastAPI).
 *
 * Nota de seguridad: el rol PACIENTE solo dispone de endpoints de LECTURA.
 * Las únicas escrituras permitidas son el inicio de sesión y confirmar la
 * llegada de una cita con el código del hospital (check-in).
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

    @POST("patients/me/appointments/{id}/check-in")
    suspend fun checkIn(
        @Header("Authorization") authorization: String,
        @Path("id") appointmentId: Int,
        @Body request: CheckInRequest,
    ): PatientAppointment

    // Próximos endpoints:
    // @GET("study-orders")         estudios y resultados
    // @GET("prescriptions")        recetas + tomas
    // @POST("qr/token")            token temporal para el check-in
}
