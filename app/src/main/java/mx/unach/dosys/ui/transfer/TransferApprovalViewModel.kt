package mx.unach.dosys.ui.transfer

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.PendingTransfer
import mx.unach.dosys.data.repository.DeviceResult

data class TransferApprovalUiState(
    val unlocked: Boolean = false,
    val loading: Boolean = false,
    val transfer: PendingTransfer? = null,
    val code: String? = null,
    val secondsLeft: Int = 0,
    val error: String? = null,
    val message: String? = null,
    val finished: Boolean = false,
    val failed: Boolean = false,
    val sessionTransferred: Boolean = false,
)

/**
 * Lado A: muestra un código local de 60 s, sondea la propuesta del dispositivo
 * nuevo cada 2 s y la compara localmente. El servidor nunca compara el código.
 */
class TransferApprovalViewModel : ViewModel() {

    private val repository = ServiceLocator.deviceRepository
    private val session = ServiceLocator.sessionManager
    private val codeSession = TransferCodeSession()

    private val _state = MutableStateFlow(TransferApprovalUiState())
    val state: StateFlow<TransferApprovalUiState> = _state.asStateFlow()

    private var countdownJob: Job? = null
    private var pollingJob: Job? = null
    private var handledSubmission: String? = null
    private var approving = false

    /** Se llama al superar la huella; hasta entonces no se genera el código. */
    fun unlock() {
        if (_state.value.unlocked) return
        _state.update { it.copy(unlocked = true) }
        load()
    }

    fun retry() {
        if (_state.value.loading) return
        _state.update {
            it.copy(
                finished = false,
                failed = false,
                error = null,
                message = null,
                transfer = null,
                code = null,
            )
        }
        load()
    }

    private fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.pendingTransfer()) {
                is DeviceResult.Success -> {
                    val transfer = result.value
                    if (transfer == null) {
                        _state.update {
                            it.copy(
                                loading = false,
                                finished = true,
                                message = "Ya no hay solicitudes pendientes.",
                            )
                        }
                    } else {
                        begin(transfer)
                    }
                }
                is DeviceResult.Error -> {
                    if (result.message.contains("sesión", ignoreCase = true)) {
                        session.clear()
                        _state.update {
                            it.copy(
                                loading = false,
                                finished = true,
                                sessionTransferred = true,
                                message = result.message,
                            )
                        }
                    } else {
                        _state.update { it.copy(loading = false, error = result.message) }
                    }
                }
            }
        }
    }

    private fun begin(transfer: PendingTransfer) {
        if (codeSession.currentCode() == null) {
            codeSession.generate()
            handledSubmission = null
        }
        _state.update {
            it.copy(
                loading = false,
                transfer = transfer,
                code = codeSession.displayCode(),
                secondsLeft = codeSession.remainingSeconds(),
                error = null,
            )
        }
        startCountdown()
        startPolling()
    }

    private fun startCountdown() {
        countdownJob?.cancel()
        countdownJob = viewModelScope.launch {
            while (true) {
                val remaining = codeSession.remainingSeconds()
                _state.update {
                    it.copy(secondsLeft = remaining, code = codeSession.displayCode())
                }
                if (remaining <= 0) {
                    val transfer = _state.value.transfer
                    codeSession.destroy()
                    if (transfer != null) {
                        repository.reject(transfer.transferId, "expired")
                    }
                    finishWith("El código expiró. La solicitud se canceló por seguridad.")
                    break
                }
                delay(1_000)
            }
        }
    }

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (true) {
                delay(2_000)
                val current = _state.value
                if (current.finished || current.sessionTransferred || approving) break

                when (val result = repository.pendingTransfer()) {
                    is DeviceResult.Success -> {
                        val transfer = result.value
                        if (transfer == null) {
                            finishWith("La solicitud ya no está disponible. Inicia sesión otra vez.")
                            break
                        }
                        if (transfer.transferId != current.transfer?.transferId) {
                            // Una solicitud nueva sustituyó a la anterior: el código
                            // debe ser nuevo y recuperar sus 60 s completos.
                            codeSession.destroy()
                            codeSession.generate()
                            handledSubmission = null
                        }
                        _state.update {
                            it.copy(
                                transfer = transfer,
                                code = codeSession.displayCode(),
                                secondsLeft = codeSession.remainingSeconds(),
                            )
                        }
                        val submitted = transfer.submittedCode
                        if (!submitted.isNullOrBlank() &&
                            submitted != handledSubmission &&
                            !approving
                        ) {
                            handledSubmission = submitted
                            if (codeSession.matches(submitted)) {
                                approve(transfer)
                                break
                            }
                            val rejection = repository.reject(transfer.transferId, "mismatch")
                            if (rejection is DeviceResult.Error) {
                                finishWith(rejection.message, failed = true)
                                break
                            }
                            _state.update {
                                it.copy(
                                    error = "El código escrito en el otro teléfono no coincide. " +
                                        "Pídele que lo escriba de nuevo."
                                )
                            }
                        }
                    }
                    is DeviceResult.Error -> {
                        if (result.message.contains("sesión", ignoreCase = true)) {
                            session.clear()
                            finishWith(
                                "Tu sesión se transfirió a otro dispositivo.",
                                transferred = true,
                            )
                            break
                        }
                    }
                }
            }
        }
    }

    private fun approve(transfer: PendingTransfer) {
        approving = true
        viewModelScope.launch {
            when (val result = repository.approve(transfer.transferId, transfer.approvalToken)) {
                is DeviceResult.Success -> {
                    session.clear()
                    finishWith(
                        "Tu sesión se transfirió al nuevo dispositivo. Este teléfono ya no tiene acceso.",
                        transferred = true,
                    )
                }
                is DeviceResult.Error -> {
                    approving = false
                    finishWith(result.message, failed = true)
                }
            }
        }
    }

    /** Botón "No fui yo": termina la solicitud de inmediato. */
    fun rejectAsNotMe() {
        val transfer = _state.value.transfer ?: return
        viewModelScope.launch {
            val result = repository.reject(transfer.transferId, "not_me")
            if (result is DeviceResult.Error) {
                finishWith(result.message, failed = true)
            } else {
                finishWith(
                    "Rechazaste la solicitud. Si no reconoces el intento, cambia tu contraseña."
                )
            }
        }
    }

    /**
     * Al pasar a segundo plano se destruye el código y se reporta ``expired``,
     * como pide la especificación de seguridad.
     */
    fun onBackground() {
        val current = _state.value
        if (!current.unlocked || current.finished || current.sessionTransferred) return
        val transfer = current.transfer ?: return
        codeSession.destroy()
        viewModelScope.launch {
            repository.reject(transfer.transferId, "expired")
        }
        finishWith(
            "El código se destruyó al salir de la pantalla. La solicitud se canceló por seguridad."
        )
    }

    private fun finishWith(
        message: String,
        transferred: Boolean = false,
        failed: Boolean = false,
    ) {
        countdownJob?.cancel()
        pollingJob?.cancel()
        countdownJob = null
        pollingJob = null
        codeSession.destroy()
        _state.update {
            it.copy(
                code = null,
                secondsLeft = 0,
                error = null,
                message = message,
                finished = true,
                failed = failed,
                sessionTransferred = transferred,
            )
        }
    }
}
