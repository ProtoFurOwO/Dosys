package mx.unach.dosys.data.repository

import kotlinx.coroutines.CancellationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import mx.unach.dosys.core.auth.SessionManager
import mx.unach.dosys.core.device.DeviceIdentity
import mx.unach.dosys.data.model.LoginRequest
import mx.unach.dosys.data.model.LogoutRequest
import mx.unach.dosys.data.model.PasswordForgotRequest
import mx.unach.dosys.data.model.TransferCodeRequest
import mx.unach.dosys.data.model.TransferStatusRequest
import mx.unach.dosys.data.model.TwoFactorVerifyRequest
import mx.unach.dosys.data.remote.ApiService
import retrofit2.HttpException
import java.io.IOException

/** Resultado de una operación de autenticación. */
sealed interface AuthResult {
    data class Success(val token: String) : AuthResult
    data class Error(val message: String) : AuthResult

    /** La contraseña es correcta pero falta el segundo factor. */
    data class NeedsTwoFactor(val challengeToken: String) : AuthResult

    /** La cuenta ya está activa en otro teléfono: hay que transferir la sesión. */
    data class NeedsDeviceTransfer(
        val transferId: String,
        val challengeToken: String,
        val expiresIn: Int,
        val message: String,
    ) : AuthResult
}

/** Resultado de proponer el código en el dispositivo nuevo. */
sealed interface TransferSubmitResult {
    data class Accepted(val submissionsLeft: Int) : TransferSubmitResult
    data class Error(val message: String) : TransferSubmitResult
}

/** Resultado del sondeo de estado de la transferencia. */
sealed interface TransferStatusResult {
    data class Pending(
        val status: String,
        val secondsLeft: Int,
        val submissionsLeft: Int,
    ) : TransferStatusResult

    data class Approved(val token: String) : TransferStatusResult
    data class Error(val message: String) : TransferStatusResult
}

/** Resultado de la alternativa "no tengo mi dispositivo anterior". */
sealed interface TransferFallbackResult {
    data class NeedsTwoFactor(val challengeToken: String) : TransferFallbackResult
    data class Error(val message: String) : TransferFallbackResult
}

/** Resultado de solicitar el enlace de recuperación de contraseña. */
sealed interface RecoveryResult {
    data class Success(val message: String, val previewUrl: String?) : RecoveryResult
    data class Error(val message: String) : RecoveryResult
}

/** Contrato del repositorio de autenticación. */
interface AuthRepository {
    suspend fun login(username: String, password: String): AuthResult
    suspend fun verifyTwoFactor(challengeToken: String, code: String): AuthResult

    suspend fun submitTransferCode(
        transferId: String,
        challengeToken: String,
        code: String,
    ): TransferSubmitResult

    suspend fun transferStatus(transferId: String, challengeToken: String): TransferStatusResult

    suspend fun cancelTransfer(transferId: String, challengeToken: String)

    suspend fun transferFallback(
        transferId: String,
        challengeToken: String,
    ): TransferFallbackResult

    /** Solicita el enlace de restablecimiento (usuario o correo). */
    suspend fun requestPasswordReset(identifier: String): RecoveryResult

    /** Cierra la sesión local y revoca el token de renovación en el servidor. */
    suspend fun logout()
}

/** Mensaje del backend (campo detail) para no inventar textos distintos a la API. */
internal fun HttpException.serverDetail(): String? = try {
    response()?.errorBody()?.string()?.let { body ->
        Json.parseToJsonElement(body).jsonObject["detail"]?.jsonPrimitive?.content
    }
} catch (_: Exception) {
    null
}

/**
 * Implementación SIMULADA: permite probar la app en el emulador
 * mientras el equipo construye el backend en FastAPI.
 */
class FakeAuthRepository(private val session: SessionManager) : AuthRepository {

    override suspend fun login(username: String, password: String): AuthResult {
        if (username.isBlank() || password.length < 4) {
            return AuthResult.Error("Usuario o contraseña incorrectos")
        }
        val token = "demo-token-jwt"
        session.saveSession(token)
        return AuthResult.Success(token)
    }

    override suspend fun verifyTwoFactor(challengeToken: String, code: String): AuthResult =
        AuthResult.Error("El segundo factor no está disponible en el modo demo")

    override suspend fun submitTransferCode(
        transferId: String,
        challengeToken: String,
        code: String,
    ): TransferSubmitResult = TransferSubmitResult.Error("La transferencia no está disponible en el modo demo")

    override suspend fun transferStatus(
        transferId: String,
        challengeToken: String,
    ): TransferStatusResult = TransferStatusResult.Error("La transferencia no está disponible en el modo demo")

    override suspend fun cancelTransfer(transferId: String, challengeToken: String) = Unit

    override suspend fun transferFallback(
        transferId: String,
        challengeToken: String,
    ): TransferFallbackResult = TransferFallbackResult.Error("La transferencia no está disponible en el modo demo")

    override suspend fun requestPasswordReset(identifier: String): RecoveryResult =
        RecoveryResult.Success(
            "Si la cuenta existe, enviamos un enlace de restablecimiento.",
            previewUrl = null,
        )

    override suspend fun logout() {
        session.clear()
    }
}

/** Implementación REAL contra la API del hospital. */
class RemoteAuthRepository(
    private val api: ApiService,
    private val session: SessionManager,
    private val deviceIdentity: DeviceIdentity,
) : AuthRepository {

    override suspend fun login(username: String, password: String): AuthResult = try {
        val response = api.login(
            LoginRequest(
                username = username,
                password = password,
                deviceId = deviceIdentity.deviceId(),
                deviceName = DeviceIdentity.localDeviceName(),
            )
        )
        when {
            response.requiresDeviceTransfer &&
                response.transferId != null &&
                response.challengeToken != null ->
                AuthResult.NeedsDeviceTransfer(
                    transferId = response.transferId,
                    challengeToken = response.challengeToken,
                    expiresIn = response.expiresIn,
                    message = response.message
                        ?: "Autoriza este dispositivo desde tu teléfono de confianza.",
                )

            response.requires2fa && response.challengeToken != null ->
                AuthResult.NeedsTwoFactor(response.challengeToken)

            response.role != "patient" -> AuthResult.Error("Este acceso es exclusivo para pacientes")

            response.accessToken != null -> {
                session.saveSession(response.accessToken, response.refreshToken)
                AuthResult.Success(response.accessToken)
            }

            else -> AuthResult.Error("No se pudo iniciar sesión. Intenta más tarde")
        }
    } catch (cancellation: CancellationException) {
        throw cancellation // nunca se debe "tragar" la cancelación de una corrutina
    } catch (error: HttpException) {
        when (error.code()) {
            401 -> AuthResult.Error(error.serverDetail() ?: "Usuario o contraseña incorrectos")
            429 -> AuthResult.Error(
                error.serverDetail() ?: "Cuenta bloqueada o demasiadas solicitudes. Espera un momento."
            )
            else -> AuthResult.Error("No se pudo iniciar sesión. Intenta más tarde")
        }
    } catch (error: IOException) {
        AuthResult.Error("No se pudo conectar con el servidor")
    } catch (error: Exception) {
        AuthResult.Error(error.message ?: "No se pudo conectar con el servidor")
    }

    override suspend fun verifyTwoFactor(challengeToken: String, code: String): AuthResult = try {
        val response = api.verifyTwoFactor(
            TwoFactorVerifyRequest(challengeToken = challengeToken, code = code.trim().uppercase())
        )
        val token = response.accessToken
        if (token == null) {
            AuthResult.Error("No se pudo completar la verificación. Intenta de nuevo")
        } else {
            session.saveSession(token, response.refreshToken)
            AuthResult.Success(token)
        }
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (error: HttpException) {
        when (error.code()) {
            401 -> AuthResult.Error(error.serverDetail() ?: "Código incorrecto o verificación expirada")
            else -> AuthResult.Error("No se pudo verificar el código. Intenta más tarde")
        }
    } catch (error: IOException) {
        AuthResult.Error("No se pudo conectar con el servidor")
    } catch (error: Exception) {
        AuthResult.Error("No se pudo verificar el código. Intenta más tarde")
    }

    override suspend fun submitTransferCode(
        transferId: String,
        challengeToken: String,
        code: String,
    ): TransferSubmitResult = try {
        val response = api.submitTransferCode(
            transferId,
            TransferCodeRequest(
                challengeToken = challengeToken,
                code = code.filter { it.isDigit() },
            ),
        )
        TransferSubmitResult.Accepted(response.submissionsLeft)
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (error: HttpException) {
        when (error.code()) {
            409 -> TransferSubmitResult.Error(
                error.serverDetail() ?: "La solicitud ya no está disponible."
            )
            429 -> TransferSubmitResult.Error("Demasiadas solicitudes. Espera un momento.")
            else -> TransferSubmitResult.Error("No se pudo enviar el código. Intenta más tarde")
        }
    } catch (error: IOException) {
        TransferSubmitResult.Error("No se pudo conectar con el servidor")
    } catch (error: Exception) {
        TransferSubmitResult.Error("No se pudo enviar el código. Intenta más tarde")
    }

    override suspend fun transferStatus(
        transferId: String,
        challengeToken: String,
    ): TransferStatusResult = try {
        val response = api.transferStatus(
            transferId,
            TransferStatusRequest(challengeToken = challengeToken),
        )
        when (response.status) {
            "approved" -> {
                val tokens = response.tokens
                val access = tokens?.accessToken
                if (access == null) {
                    TransferStatusResult.Error(
                        "La sesión ya se aprobó, pero no se recibieron los tokens. Inicia sesión otra vez."
                    )
                } else {
                    session.saveSession(access, tokens.refreshToken)
                    TransferStatusResult.Approved(access)
                }
            }
            "rejected" -> TransferStatusResult.Error(
                "El dispositivo de confianza rechazó la solicitud."
            )
            "failed" -> TransferStatusResult.Error(
                "Se agotaron los intentos. Inicia sesión otra vez para pedir un código nuevo."
            )
            "expired" -> TransferStatusResult.Error(
                "La solicitud expiró. Intenta de nuevo."
            )
            else -> TransferStatusResult.Pending(
                status = response.status,
                secondsLeft = response.expiresIn,
                submissionsLeft = response.submissionsLeft,
            )
        }
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (error: HttpException) {
        when (error.code()) {
            401 -> TransferStatusResult.Error(
                error.serverDetail() ?: "La solicitud expiró. Intenta de nuevo."
            )
            else -> TransferStatusResult.Error("No se pudo consultar la solicitud. Intenta más tarde")
        }
    } catch (error: IOException) {
        TransferStatusResult.Error("No se pudo conectar con el servidor")
    } catch (error: Exception) {
        TransferStatusResult.Error("No se pudo consultar la solicitud. Intenta más tarde")
    }

    override suspend fun cancelTransfer(transferId: String, challengeToken: String) {
        try {
            api.cancelTransfer(transferId, TransferStatusRequest(challengeToken = challengeToken))
        } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (_: Exception) {
            // Cancelar es best-effort: el servidor la expirará igualmente.
        }
    }

    override suspend fun transferFallback(
        transferId: String,
        challengeToken: String,
    ): TransferFallbackResult = try {
        val response = api.transferFallback(
            transferId,
            TransferStatusRequest(challengeToken = challengeToken),
        )
        val challenge = response.challengeToken
        if (response.requires2fa && challenge != null) {
            TransferFallbackResult.NeedsTwoFactor(challenge)
        } else {
            TransferFallbackResult.Error("No se pudo iniciar la recuperación de acceso.")
        }
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (error: HttpException) {
        when (error.code()) {
            409 -> TransferFallbackResult.Error(
                error.serverDetail()
                    ?: "No puedes recuperar el acceso sin tu segundo factor. Restablece tu contraseña."
            )
            401 -> TransferFallbackResult.Error("La solicitud expiró. Intenta de nuevo.")
            429 -> TransferFallbackResult.Error("Demasiadas solicitudes. Espera un momento.")
            else -> TransferFallbackResult.Error("No se pudo recuperar el acceso. Intenta más tarde")
        }
    } catch (error: IOException) {
        TransferFallbackResult.Error("No se pudo conectar con el servidor")
    } catch (error: Exception) {
        TransferFallbackResult.Error("No se pudo recuperar el acceso. Intenta más tarde")
    }

    override suspend fun requestPasswordReset(identifier: String): RecoveryResult = try {
        val response = api.forgotPassword(PasswordForgotRequest(identifier.trim()))
        RecoveryResult.Success(
            response.message.ifBlank { "Si la cuenta existe, enviamos un enlace de restablecimiento." },
            previewUrl = response.previewUrl,
        )
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (error: HttpException) {
        when (error.code()) {
            429 -> RecoveryResult.Error(error.serverDetail() ?: "Demasiadas solicitudes. Espera un minuto.")
            else -> RecoveryResult.Error("No se pudo solicitar el enlace. Intenta más tarde")
        }
    } catch (error: IOException) {
        RecoveryResult.Error("No se pudo conectar con el servidor")
    } catch (error: Exception) {
        RecoveryResult.Error("No se pudo solicitar el enlace. Intenta más tarde")
    }

    override suspend fun logout() {
        val refreshToken = session.currentRefreshToken()
        if (!refreshToken.isNullOrBlank()) {
            try {
                api.logout(LogoutRequest(refreshToken))
            } catch (cancellation: CancellationException) {
                throw cancellation
            } catch (_: Exception) {
                // Si el servidor no responde, la sesión local se cierra de todos modos.
            }
        }
        session.clear()
    }
}
