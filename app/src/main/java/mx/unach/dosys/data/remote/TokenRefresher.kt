package mx.unach.dosys.data.remote

import kotlinx.coroutines.CancellationException
import mx.unach.dosys.core.auth.SessionManager
import mx.unach.dosys.data.model.RefreshRequest
import retrofit2.HttpException

/** La sesión local ya no tiene tokens utilizables. */
class SessionExpiredException : Exception("Sesión expirada")

/**
 * Renueva la sesión de forma transparente: cuando una llamada responde 401,
 * rota el token de renovación y repite la llamada una sola vez.
 */
class TokenRefresher(
    private val api: ApiService,
    private val session: SessionManager,
) {

    suspend fun <T> withFreshToken(call: suspend (String) -> T): T {
        val token = session.currentToken() ?: throw SessionExpiredException()
        return try {
            call("Bearer $token")
        } catch (error: HttpException) {
            if (error.code() != 401) throw error
            if (!refresh()) throw error
            val renewed = session.currentToken() ?: throw SessionExpiredException()
            call("Bearer $renewed")
        }
    }

    private suspend fun refresh(): Boolean = try {
        val refreshToken = session.currentRefreshToken()
        if (refreshToken.isNullOrBlank()) {
            false
        } else {
            val response = api.refresh(RefreshRequest(refreshToken))
            val access = response.accessToken
            if (access == null) {
                false
            } else {
                session.saveSession(access, response.refreshToken ?: refreshToken)
                true
            }
        }
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (_: Exception) {
        false
    }
}
