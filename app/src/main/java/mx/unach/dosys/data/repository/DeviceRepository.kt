package mx.unach.dosys.data.repository

import kotlinx.coroutines.CancellationException
import mx.unach.dosys.core.auth.SessionManager
import mx.unach.dosys.core.device.DeviceIdentity
import mx.unach.dosys.data.model.DeviceRegisterRequest
import mx.unach.dosys.data.model.PendingTransfer
import mx.unach.dosys.data.model.TransferApproveRequest
import mx.unach.dosys.data.model.TransferRejectRequest
import mx.unach.dosys.data.model.TrustedDevice
import mx.unach.dosys.data.remote.ApiService
import mx.unach.dosys.data.remote.SessionExpiredException
import mx.unach.dosys.data.remote.TokenRefresher
import retrofit2.HttpException
import java.io.IOException

sealed interface DeviceResult<out T> {
    data class Success<T>(val value: T) : DeviceResult<T>
    data class Error(
        val message: String,
        val code: Int? = null,
    ) : DeviceResult<Nothing>
}

/**
 * Dispositivos de confianza del paciente y resolución de las solicitudes de
 * alta. Cualquier dispositivo activo puede aprobar a otro; el límite lo impone
 * el servidor.
 */
interface DeviceRepository {
    suspend fun registerDevice(): DeviceResult<Unit>
    suspend fun trustedDevices(): DeviceResult<List<TrustedDevice>>
    suspend fun revokeDevice(deviceId: Int): DeviceResult<String>
    suspend fun pendingTransfer(): DeviceResult<PendingTransfer?>
    suspend fun approve(transferId: String, approvalToken: String): DeviceResult<String>
    suspend fun reject(transferId: String, reason: String): DeviceResult<String>
}

class RemoteDeviceRepository(
    private val api: ApiService,
    private val session: SessionManager,
    private val refresher: TokenRefresher,
    private val deviceIdentity: DeviceIdentity,
) : DeviceRepository {

    override suspend fun registerDevice(): DeviceResult<Unit> = authorized { header ->
        api.registerDevice(
            header,
            DeviceRegisterRequest(
                deviceId = deviceIdentity.deviceId(),
                deviceName = DeviceIdentity.localDeviceName(),
                fcmToken = deviceIdentity.fcmToken(),
            ),
        )
        Unit
    }

    override suspend fun trustedDevices(): DeviceResult<List<TrustedDevice>> = authorized { header ->
        api.trustedDevices(header)
    }

    override suspend fun revokeDevice(deviceId: Int): DeviceResult<String> = authorized { header ->
        api.revokeDevice(header, deviceId).detail
            .ifBlank { "Dispositivo revocado." }
    }

    override suspend fun pendingTransfer(): DeviceResult<PendingTransfer?> = authorized { header ->
        // 204 significa que no hay solicitudes: Retrofit devuelve null.
        api.pendingTransfer(header)
    }

    override suspend fun approve(
        transferId: String,
        approvalToken: String,
    ): DeviceResult<String> = authorized { header ->
        api.approveTransfer(header, transferId, TransferApproveRequest(approvalToken)).detail
            .ifBlank { "Dispositivo autorizado. Los demás dispositivos siguen activos." }
    }

    override suspend fun reject(transferId: String, reason: String): DeviceResult<String> =
        authorized { header ->
            api.rejectTransfer(header, transferId, TransferRejectRequest(reason)).detail
                .ifBlank { "Solicitud resuelta." }
        }

    private suspend fun <T> authorized(call: suspend (String) -> T): DeviceResult<T> {
        return try {
            DeviceResult.Success(refresher.withFreshToken(call))
        } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (error: SessionExpiredException) {
            session.expire("Este dispositivo ya no está autorizado. Inicia sesión de nuevo.")
            DeviceResult.Error(
                "Este dispositivo ya no está autorizado. Inicia sesión de nuevo.",
                401,
            )
        } catch (error: HttpException) {
            when (error.code()) {
                401 -> {
                    // El dispositivo fue revocado o la sesión ya no es válida.
                    val message = error.serverDetail()
                        ?: "Este dispositivo ya no está autorizado. Inicia sesión de nuevo."
                    session.expire(message)
                    DeviceResult.Error(message, 401)
                }
                403, 404, 409, 429 -> DeviceResult.Error(
                    error.serverDetail() ?: "No se pudo completar la operación",
                    error.code(),
                )
                else -> DeviceResult.Error(
                    "No se pudo completar la operación. Intenta más tarde",
                    error.code(),
                )
            }
        } catch (error: IOException) {
            DeviceResult.Error("No se pudo conectar con el servidor")
        } catch (error: Exception) {
            DeviceResult.Error("No se pudo completar la operación. Intenta más tarde")
        }
    }
}
