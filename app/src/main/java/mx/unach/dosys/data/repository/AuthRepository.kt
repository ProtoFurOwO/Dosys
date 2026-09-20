package mx.unach.dosys.data.repository

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import mx.unach.dosys.core.auth.SessionManager
import mx.unach.dosys.data.model.LoginRequest
import mx.unach.dosys.data.remote.ApiService
import retrofit2.HttpException
import java.io.IOException

/** Resultado de una operación de autenticación. */
sealed interface AuthResult {
    data class Success(val token: String) : AuthResult
    data class Error(val message: String) : AuthResult
}

/** Contrato del repositorio de autenticación. */
interface AuthRepository {
    suspend fun login(username: String, password: String): AuthResult
}

/**
 * Implementación SIMULADA: permite probar la app en el emulador
 * mientras el equipo construye el backend en FastAPI.
 */
class FakeAuthRepository(private val session: SessionManager) : AuthRepository {

    override suspend fun login(username: String, password: String): AuthResult {
        delay(700) // simula la latencia de la red
        if (username.isBlank() || password.length < 4) {
            return AuthResult.Error("Usuario o contraseña incorrectos")
        }
        val token = "demo-token-jwt"
        session.saveToken(token)
        return AuthResult.Success(token)
    }
}

/** Implementación REAL contra la API del hospital. */
class RemoteAuthRepository(
    private val api: ApiService,
    private val session: SessionManager,
) : AuthRepository {

    override suspend fun login(username: String, password: String): AuthResult = try {
        val response = api.login(LoginRequest(username = username, password = password))
        if (response.role != "patient") {
            AuthResult.Error("Este acceso es exclusivo para pacientes")
        } else {
            session.saveToken(response.accessToken)
            AuthResult.Success(response.accessToken)
        }
    } catch (cancellation: CancellationException) {
        throw cancellation // nunca se debe "tragar" la cancelación de una corrutina
    } catch (error: HttpException) {
        if (error.code() == 401) {
            AuthResult.Error("Usuario o contraseña incorrectos")
        } else {
            AuthResult.Error("No se pudo iniciar sesión. Intenta más tarde")
        }
    } catch (error: IOException) {
        AuthResult.Error("No se pudo conectar con el servidor")
    } catch (error: Exception) {
        AuthResult.Error(error.message ?: "No se pudo conectar con el servidor")
    }
}
