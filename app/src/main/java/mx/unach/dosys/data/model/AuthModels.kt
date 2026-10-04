package mx.unach.dosys.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Credenciales que la app envía al endpoint /auth/login. */
@Serializable
data class LoginRequest(
    @SerialName("username") val username: String,
    @SerialName("password") val password: String,
)

/**
 * Respuesta del backend: tokens JWT, o bien el desafío del segundo factor
 * cuando la cuenta tiene 2FA activo (requires_2fa = true).
 */
@Serializable
data class LoginResponse(
    @SerialName("access_token") val accessToken: String? = null,
    @SerialName("refresh_token") val refreshToken: String? = null,
    @SerialName("token_type") val tokenType: String = "bearer",
    val role: String = "",
    @SerialName("requires_2fa") val requires2fa: Boolean = false,
    @SerialName("challenge_token") val challengeToken: String? = null,
)

/** Verificación del segundo factor (código TOTP o código de recuperación). */
@Serializable
data class TwoFactorVerifyRequest(
    @SerialName("challenge_token") val challengeToken: String,
    val code: String,
)

/** Datos básicos del paciente autenticado (solo lectura). */
@Serializable
data class PatientProfile(
    val id: Int,
    @SerialName("full_name") val fullName: String,
    val curp: String? = null,
    @SerialName("blood_type") val bloodType: String? = null,
    @SerialName("birth_date") val birthDate: String? = null,
    @SerialName("emergency_contact") val emergencyContact: String? = null,
)

// ── Segundo factor (Mi seguridad) ─────────────────────────────────────────────

@Serializable
data class TwoFactorStatus(
    val enabled: Boolean = false,
    @SerialName("recovery_codes_remaining") val recoveryCodesRemaining: Int = 0,
)

@Serializable
data class TwoFactorSetup(
    val secret: String,
    @SerialName("otpauth_uri") val otpauthUri: String,
    val issuer: String = "",
)

@Serializable
data class TwoFactorConfirmRequest(
    val code: String,
)

@Serializable
data class TwoFactorEnableResult(
    val enabled: Boolean = false,
    @SerialName("recovery_codes") val recoveryCodes: List<String> = emptyList(),
)

@Serializable
data class TwoFactorDisableRequest(
    val password: String,
)

// ── Sesión renovable y contraseña ─────────────────────────────────────────────

/** Renovación de la sesión sin volver a pedir credenciales. */
@Serializable
data class RefreshRequest(
    @SerialName("refresh_token") val refreshToken: String,
)

/** Cambio de contraseña propio desde la app. */
@Serializable
data class ChangePasswordRequest(
    @SerialName("current_password") val currentPassword: String,
    @SerialName("new_password") val newPassword: String,
    @SerialName("new_password_confirm") val newPasswordConfirm: String,
)

/** Respuesta simple con el mensaje del servidor. */
@Serializable
data class SimpleMessage(
    val detail: String = "",
)

/** Cierre de sesión: revoca el token de renovación en el servidor. */
@Serializable
data class LogoutRequest(
    @SerialName("refresh_token") val refreshToken: String,
)
