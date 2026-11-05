package mx.unach.dosys.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// ── Dispositivo de confianza ──────────────────────────────────────────────────

@Serializable
data class DeviceRegisterRequest(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_name") val deviceName: String,
    @SerialName("fcm_token") val fcmToken: String? = null,
)

/** Solicitud pendiente que el dispositivo activo debe revisar al abrir la alerta. */
@Serializable
data class PendingTransfer(
    @SerialName("transfer_id") val transferId: String,
    @SerialName("requested_device_name") val requestedDeviceName: String,
    @SerialName("requested_at") val requestedAt: String = "",
    @SerialName("expires_in") val expiresIn: Int = 0,
    @SerialName("approval_token") val approvalToken: String,
    @SerialName("submitted_code_hash") val submittedCodeHash: String? = null,
    @SerialName("submissions_left") val submissionsLeft: Int = 0,
)

@Serializable
data class TransferApproveRequest(
    @SerialName("approval_token") val approvalToken: String,
)

@Serializable
data class TransferRejectRequest(
    val reason: String,
)

// ── Lado público (dispositivo nuevo) ──────────────────────────────────────────

@Serializable
data class TransferCodeRequest(
    @SerialName("challenge_token") val challengeToken: String,
    val code: String,
)

@Serializable
data class TransferCodeResponse(
    @SerialName("submissions_left") val submissionsLeft: Int = 0,
    val detail: String = "",
)

@Serializable
data class TransferStatusRequest(
    @SerialName("challenge_token") val challengeToken: String,
)

@Serializable
data class TransferStatusResponse(
    val status: String,
    @SerialName("expires_in") val expiresIn: Int = 0,
    @SerialName("submissions_left") val submissionsLeft: Int = 0,
    /** Solo llega una vez, cuando el dispositivo activo aprueba. */
    val tokens: LoginResponse? = null,
)
