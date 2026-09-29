package mx.unach.dosys.data.repository

import kotlinx.coroutines.CancellationException
import mx.unach.dosys.core.auth.SessionManager
import mx.unach.dosys.data.model.TwoFactorConfirmRequest
import mx.unach.dosys.data.model.TwoFactorDisableRequest
import mx.unach.dosys.data.model.TwoFactorEnableResult
import mx.unach.dosys.data.model.TwoFactorSetup
import mx.unach.dosys.data.model.TwoFactorStatus
import mx.unach.dosys.data.remote.ApiService
import retrofit2.HttpException
import java.io.IOException

/** Seguridad de la propia cuenta (segundo factor). */
interface SecurityRepository {
    suspend fun status(): ClinicalResult<TwoFactorStatus>
    suspend fun setup(): ClinicalResult<TwoFactorSetup>
    suspend fun confirm(code: String): ClinicalResult<TwoFactorEnableResult>
    suspend fun disable(password: String): ClinicalResult<TwoFactorStatus>
}

class RemoteSecurityRepository(
    private val api: ApiService,
    private val session: SessionManager,
) : SecurityRepository {

    override suspend fun status(): ClinicalResult<TwoFactorStatus> = authorized { header ->
        api.twoFactorStatus(header)
    }

    override suspend fun setup(): ClinicalResult<TwoFactorSetup> = authorized { header ->
        api.setupTwoFactor(header)
    }

    override suspend fun confirm(code: String): ClinicalResult<TwoFactorEnableResult> = authorized { header ->
        api.confirmTwoFactor(header, TwoFactorConfirmRequest(code.trim()))
    }

    override suspend fun disable(password: String): ClinicalResult<TwoFactorStatus> = authorized { header ->
        api.disableTwoFactor(header, TwoFactorDisableRequest(password))
    }

    private suspend fun <T> authorized(call: suspend (String) -> T): ClinicalResult<T> {
        val token = session.currentToken()
            ?: return ClinicalResult.Error("Tu sesión terminó. Inicia sesión nuevamente")

        return try {
            ClinicalResult.Success(call("Bearer $token"))
        } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (error: HttpException) {
            when (error.code()) {
                400, 401, 409 -> ClinicalResult.Error(error.serverDetail() ?: "No se pudo completar la operación")
                else -> ClinicalResult.Error("No se pudo completar la operación. Intenta más tarde")
            }
        } catch (error: IOException) {
            ClinicalResult.Error("No se pudo conectar con el servidor")
        } catch (error: Exception) {
            ClinicalResult.Error("No se pudo completar la operación. Intenta más tarde")
        }
    }
}
