package mx.unach.dosys.ui.devices

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.TrustedDevice
import mx.unach.dosys.data.repository.DeviceResult

data class TrustedDevicesUiState(
    val devices: List<TrustedDevice> = emptyList(),
    val isLoading: Boolean = false,
    val revokingId: Int? = null,
    val error: String? = null,
    val message: String? = null,
)

class TrustedDevicesViewModel : ViewModel() {

    private val repository = ServiceLocator.deviceRepository
    private val session = ServiceLocator.sessionManager

    private val _state = MutableStateFlow(TrustedDevicesUiState())
    val state: StateFlow<TrustedDevicesUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        if (_state.value.isLoading) return
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.trustedDevices()) {
                is DeviceResult.Success -> _state.update {
                    it.copy(devices = result.value, isLoading = false)
                }
                is DeviceResult.Error -> _state.update {
                    it.copy(isLoading = false, error = result.message)
                }
            }
        }
    }

    fun revoke(device: TrustedDevice) {
        if (_state.value.revokingId != null) return
        _state.update { it.copy(revokingId = device.id, error = null) }
        viewModelScope.launch {
            when (val result = repository.revokeDevice(device.id)) {
                is DeviceResult.Success -> {
                    if (device.isCurrent) {
                        // El servidor ya invalidó este teléfono. La sesión local
                        // se limpia y el NavHost vuelve al login con el motivo.
                        session.expire(
                            "Revocaste este dispositivo. Inicia sesión de nuevo."
                        )
                        _state.update { it.copy(revokingId = null) }
                    } else {
                        _state.update {
                            it.copy(revokingId = null, message = result.value)
                        }
                        refresh()
                    }
                }
                is DeviceResult.Error -> {
                    _state.update {
                        it.copy(revokingId = null, error = result.message)
                    }
                    // 404/409 suelen significar que la lista quedó desfasada.
                    if (result.code == 404 || result.code == 409) {
                        refresh()
                    }
                }
            }
        }
    }

    fun consumeMessage() {
        _state.update { it.copy(message = null) }
    }

    fun dismissError() {
        _state.update { it.copy(error = null) }
    }
}
