package mx.unach.dosys.data.remote

import mx.unach.dosys.data.model.ChangePasswordRequest
import mx.unach.dosys.data.model.CheckInRequest
import mx.unach.dosys.data.model.DeviceRegisterRequest
import mx.unach.dosys.data.model.LoginRequest
import mx.unach.dosys.data.model.LoginResponse
import mx.unach.dosys.data.model.LogoutRequest
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.data.model.PatientConsultation
import mx.unach.dosys.data.model.PatientDocument
import mx.unach.dosys.data.model.PatientPrescription
import mx.unach.dosys.data.model.PatientProfile
import mx.unach.dosys.data.model.PatientStudy
import mx.unach.dosys.data.model.PasswordForgotRequest
import mx.unach.dosys.data.model.PasswordForgotResponse
import mx.unach.dosys.data.model.PendingTransfer
import mx.unach.dosys.data.model.RefreshRequest
import mx.unach.dosys.data.model.SimpleMessage
import mx.unach.dosys.data.model.TransferApproveRequest
import mx.unach.dosys.data.model.TransferCodeRequest
import mx.unach.dosys.data.model.TransferCodeResponse
import mx.unach.dosys.data.model.TransferRejectRequest
import mx.unach.dosys.data.model.TransferStatusRequest
import mx.unach.dosys.data.model.TransferStatusResponse
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
import retrofit2.http.PUT
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

    // ── Transferencia de sesión (dispositivo nuevo, sin sesión) ───────────────

    /** Deja el código propuesto para que el dispositivo activo lo compare. */
    @POST("auth/device-transfer/{id}/code")
    suspend fun submitTransferCode(
        @Path("id") transferId: String,
        @Body request: TransferCodeRequest,
    ): TransferCodeResponse

    /** Sondeo del estado; los tokens llegan una sola vez al aprobarse. */
    @POST("auth/device-transfer/{id}/status")
    suspend fun transferStatus(
        @Path("id") transferId: String,
        @Body request: TransferStatusRequest,
    ): TransferStatusResponse

    @POST("auth/device-transfer/{id}/cancel")
    suspend fun cancelTransfer(
        @Path("id") transferId: String,
        @Body request: TransferStatusRequest,
    ): SimpleMessage

    /** Alternativa "no tengo mi dispositivo anterior" (2FA o recuperación). */
    @POST("auth/device-transfer/{id}/fallback")
    suspend fun transferFallback(
        @Path("id") transferId: String,
        @Body request: TransferStatusRequest,
    ): LoginResponse

    // ── Dispositivo de confianza (dispositivo activo, con sesión) ─────────────

    @PUT("devices/me")
    suspend fun registerDevice(
        @Header("Authorization") authorization: String,
        @Body request: DeviceRegisterRequest,
    ): SimpleMessage

    @GET("devices/transfers/pending")
    suspend fun pendingTransfer(@Header("Authorization") authorization: String): PendingTransfer?

    @POST("devices/transfers/{id}/approve")
    suspend fun approveTransfer(
        @Header("Authorization") authorization: String,
        @Path("id") transferId: String,
        @Body request: TransferApproveRequest,
    ): SimpleMessage

    @POST("devices/transfers/{id}/reject")
    suspend fun rejectTransfer(
        @Header("Authorization") authorization: String,
        @Path("id") transferId: String,
        @Body request: TransferRejectRequest,
    ): SimpleMessage

    /** Renueva la sesión sin pedir credenciales otra vez. */
    @POST("auth/refresh")
    suspend fun refresh(@Body request: RefreshRequest): LoginResponse

    /** Revoca la sesión renovable al cerrar sesión. */
    @POST("auth/logout")
    suspend fun logout(@Body request: LogoutRequest): SimpleMessage

    /** Solicita el enlace para restablecer la contraseña. */
    @POST("auth/password/forgot")
    suspend fun forgotPassword(@Body request: PasswordForgotRequest): PasswordForgotResponse

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

    @GET("patients/me/studies")
    suspend fun myStudies(@Header("Authorization") authorization: String): List<PatientStudy>

    @GET("patients/me/prescriptions")
    suspend fun myPrescriptions(@Header("Authorization") authorization: String): List<PatientPrescription>

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

    /** Check-in con solo el código: el servidor busca la cita vigente. */
    @POST("patients/me/check-in")
    suspend fun checkInWithCode(
        @Header("Authorization") authorization: String,
        @Body request: CheckInRequest,
    ): PatientAppointment

    // Próximos endpoints:
    // @GET("study-orders")         estudios y resultados
    // @GET("prescriptions")        recetas + tomas
    // @GET("qr/token")            token temporal para el check-in
}
