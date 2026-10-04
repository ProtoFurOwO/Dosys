package mx.unach.dosys.data.remote

import mx.unach.dosys.data.model.ChangePasswordRequest
import mx.unach.dosys.data.model.CheckInRequest
import mx.unach.dosys.data.model.LoginRequest
import mx.unach.dosys.data.model.LoginResponse
import mx.unach.dosys.data.model.LogoutRequest
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.data.model.PatientConsultation
import mx.unach.dosys.data.model.PatientDocument
import mx.unach.dosys.data.model.PatientProfile
import mx.unach.dosys.data.model.RefreshRequest
import mx.unach.dosys.data.model.SimpleMessage
import mx.unach.dosys.data.model.TwoFactorConfirmRequest
import mx.unach.dosys.data.model.TwoFactorDisableRequest
import mx.unach.dosys.data.model.TwoFactorEnableResult
import mx.unach.dosys.data.model.TwoFactorSetup
import mx.unach.dosys.data.model.TwoFactorStatus
import mx.unach.dosys.data.model.TwoFactorVerifyRequest
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Streaming

/**
 * Contrato de la API REST (backend en FastAPI).
 *
 * Nota de seguridad: el rol PACIENTE solo dispone de endpoints de LECTURA.
 * Las únicas escrituras permitidas son el inicio de sesión, el segundo factor,
 * confirmar la llegada de una cita (check-in) y la seguridad de su propia cuenta.
 */
interface ApiService {

    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @POST("auth/2fa/verify")
    suspend fun verifyTwoFactor(@Body request: TwoFactorVerifyRequest): LoginResponse

    /** Renueva la sesión sin pedir credenciales otra vez. */
    @POST("auth/refresh")
    suspend fun refresh(@Body request: RefreshRequest): LoginResponse

    /** Revoca la sesión renovable al cerrar sesión. */
    @POST("auth/logout")
    suspend fun logout(@Body request: LogoutRequest): SimpleMessage

    /** Cambio de contraseña propio (exige la contraseña actual). */
    @POST("auth/password/change")
    suspend fun changePassword(
        @Header("Authorization") authorization: String,
        @Body request: ChangePasswordRequest,
    ): SimpleMessage

    @GET("auth/2fa/status")
    suspend fun twoFactorStatus(@Header("Authorization") authorization: String): TwoFactorStatus

    @POST("auth/2fa/setup")
    suspend fun setupTwoFactor(@Header("Authorization") authorization: String): TwoFactorSetup

    @POST("auth/2fa/confirm")
    suspend fun confirmTwoFactor(
        @Header("Authorization") authorization: String,
        @Body request: TwoFactorConfirmRequest,
    ): TwoFactorEnableResult

    @POST("auth/2fa/disable")
    suspend fun disableTwoFactor(
        @Header("Authorization") authorization: String,
        @Body request: TwoFactorDisableRequest,
    ): TwoFactorStatus

    @GET("patients/me")
    suspend fun me(@Header("Authorization") authorization: String): PatientProfile

    @GET("patients/me/consultations")
    suspend fun myConsultations(@Header("Authorization") authorization: String): List<PatientConsultation>

    @GET("patients/me/appointments")
    suspend fun myAppointments(@Header("Authorization") authorization: String): List<PatientAppointment>

    @GET("patients/me/documents")
    suspend fun myDocuments(@Header("Authorization") authorization: String): List<PatientDocument>

    @Streaming
    @GET("patients/me/documents/{id}/file")
    suspend fun documentFile(
        @Header("Authorization") authorization: String,
        @Path("id") documentId: Int,
    ): ResponseBody

    @POST("patients/me/appointments/{id}/check-in")
    suspend fun checkIn(
        @Header("Authorization") authorization: String,
        @Path("id") appointmentId: Int,
        @Body request: CheckInRequest,
    ): PatientAppointment

    // Próximos endpoints:
    // @GET("study-orders")         estudios y resultados
    // @GET("prescriptions")        recetas + tomas
    // @GET("qr/token")            token temporal para el check-in
}
