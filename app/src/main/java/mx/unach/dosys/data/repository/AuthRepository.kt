package mx.unach.dosys.data.repository

import kotlinx.coroutines.CancellationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import mx.unach.dosys.core.auth.SessionManager
import mx.unach.dosys.data.model.LoginRequest
import mx.unach.dosys.data.model.LogoutRequest
import mx.unach.dosys.data.model.PasswordForgotRequest
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
) : AuthRepository {

    override suspend fun login(username: String, password: String): AuthResult = try {
        val response = api.login(LoginRequest(username = username, password = password))
        when {
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
            423 -> AuthResult.Error(error.serverDetail() ?: "Cuenta bloqueada temporalmente")
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
