package mx.unach.dosys.ui.login

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
import mx.unach.dosys.data.repository.AuthResult
import mx.unach.dosys.data.repository.RecoveryResult
import mx.unach.dosys.data.repository.TransferFallbackResult
import mx.unach.dosys.data.repository.TransferStatusResult
import mx.unach.dosys.data.repository.TransferSubmitResult

/** Paso actual del inicio de sesión. */
enum class LoginStep { CREDENTIALS, TWO_FACTOR, DEVICE_TRANSFER }

/** Estado de la pantalla de inicio de sesión. */
data class LoginUiState(
    val username: String = "",
    val password: String = "",
    val code: String = "",
    val step: LoginStep = LoginStep.CREDENTIALS,
    val challengeToken: String? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
    val loggedIn: Boolean = false,
    // Alta de dispositivo de confianza entre teléfonos
    val transferId: String? = null,
    val transferSecondsLeft: Int = 0,
    val transferSubmissionsLeft: Int = 0,
    val transferHint: String? = null,
    // Recuperación de contraseña
    val showRecovery: Boolean = false,
    val recoveryIdentifier: String = "",
    val recoveryLoading: Boolean = false,
    val recoveryMessage: String? = null,
    val recoveryError: String? = null,
    val recoveryPreviewUrl: String? = null,
)

class LoginViewModel : ViewModel() {

    private val _state = MutableStateFlow(LoginUiState())
    val state: StateFlow<LoginUiState> = _state.asStateFlow()

    private val repository = ServiceLocator.authRepository
    private var transferPollingJob: Job? = null
    private var transferCountdownJob: Job? = null

    fun onUsernameChange(value: String) {
        _state.update { it.copy(username = value, error = null) }
    }

    fun onPasswordChange(value: String) {
        _state.update { it.copy(password = value, error = null) }
    }

    fun onCodeChange(value: String) {
        val clean = value.filter { it.isLetterOrDigit() || it == '-' }.uppercase().take(16)
        _state.update { it.copy(code = clean, error = null) }
    }

    fun login() {
        if (_state.value.isLoading) return
        _state.update { it.copy(isLoading = true, error = null) }

        viewModelScope.launch {
            when (val result = repository.login(_state.value.username.trim(), _state.value.password)) {
                is AuthResult.Success -> {
                    _state.update { it.copy(isLoading = false, loggedIn = true) }
                    registerDeviceInBackground()
                }
                is AuthResult.NeedsTwoFactor -> _state.update {
                    it.copy(
                        isLoading = false,
                        step = LoginStep.TWO_FACTOR,
                        challengeToken = result.challengeToken,
                        code = "",
                        error = null,
                    )
                }
                is AuthResult.NeedsDeviceTransfer -> beginTransfer(result)
                is AuthResult.Error -> _state.update { it.copy(isLoading = false, error = result.message) }
            }
        }
    }

    fun verifyCode() {
        val current = _state.value
        val challenge = current.challengeToken ?: return
        if (current.isLoading || current.code.isBlank()) return
        _state.update { it.copy(isLoading = true, error = null) }

        viewModelScope.launch {
            when (val result = repository.verifyTwoFactor(challenge, current.code)) {
                is AuthResult.Success -> {
                    _state.update { it.copy(isLoading = false, loggedIn = true) }
                    registerDeviceInBackground()
                }
                is AuthResult.Error -> _state.update { it.copy(isLoading = false, error = result.message) }
                is AuthResult.NeedsTwoFactor -> _state.update { it.copy(isLoading = false) }
                is AuthResult.NeedsDeviceTransfer -> beginTransfer(result)
            }
        }
    }

    // ── Transferencia de sesión (dispositivo nuevo) ───────────────────────────

    private fun beginTransfer(result: AuthResult.NeedsDeviceTransfer) {
        stopTransferJobs()
        _state.update {
            it.copy(
                isLoading = false,
                step = LoginStep.DEVICE_TRANSFER,
                challengeToken = result.challengeToken,
                transferId = result.transferId,
                transferSecondsLeft = result.expiresIn,
                transferSubmissionsLeft = 3,
                transferHint = result.message,
                code = "",
                error = null,
            )
        }
        startTransferCountdown()
        startTransferPolling()
    }

    fun submitTransferCode() {
        val current = _state.value
        val transferId = current.transferId ?: return
        val challenge = current.challengeToken ?: return
        if (current.isLoading || current.code.length != 6) return
        _state.update { it.copy(isLoading = true, error = null) }

        viewModelScope.launch {
            when (val result = repository.submitTransferCode(transferId, challenge, current.code)) {
                is TransferSubmitResult.Accepted -> _state.update {
                    it.copy(
                        isLoading = false,
                        transferSubmissionsLeft = result.submissionsLeft,
                        transferHint = "Código enviado. Espera a que uno de tus dispositivos de confianza lo apruebe.",
                        error = null,
                    )
                }
                is TransferSubmitResult.Error -> _state.update {
                    it.copy(isLoading = false, error = result.message)
                }
            }
        }
    }

    /** Alternativa si no puede acceder a sus dispositivos: pasa al 2FA existente. */
    fun useTransferFallback() {
        val current = _state.value
        val transferId = current.transferId ?: return
        val challenge = current.challengeToken ?: return
        if (current.isLoading) return
        _state.update { it.copy(isLoading = true, error = null) }

        viewModelScope.launch {
            when (val result = repository.transferFallback(transferId, challenge)) {
                is TransferFallbackResult.NeedsTwoFactor -> {
                    stopTransferJobs()
                    _state.update {
                        it.copy(
                            isLoading = false,
                            step = LoginStep.TWO_FACTOR,
                            challengeToken = result.challengeToken,
                            transferId = null,
                            transferSecondsLeft = 0,
                            transferHint = null,
                            code = "",
                            error = null,
                        )
                    }
                }
                is TransferFallbackResult.Error -> _state.update {
                    it.copy(isLoading = false, error = result.message)
                }
            }
        }
    }

    fun cancelTransfer() {
        val current = _state.value
        val transferId = current.transferId
        val challenge = current.challengeToken
        if (transferId != null && challenge != null) {
            viewModelScope.launch { repository.cancelTransfer(transferId, challenge) }
        }
        backToCredentials()
    }

    private fun startTransferCountdown() {
        transferCountdownJob?.cancel()
        transferCountdownJob = viewModelScope.launch {
            while (true) {
                delay(1_000)
                val left = (_state.value.transferSecondsLeft - 1).coerceAtLeast(0)
                _state.update { it.copy(transferSecondsLeft = left) }
                if (left == 0) {
                    stopTransferJobs()
                    _state.update {
                        it.copy(
                            isLoading = false,
                            error = "La solicitud expiró. Intenta de nuevo.",
                        )
                    }
                    break
                }
            }
        }
    }

    private fun startTransferPolling() {
        transferPollingJob?.cancel()
        transferPollingJob = viewModelScope.launch {
            while (true) {
                delay(2_000)
                val current = _state.value
                if (current.step != LoginStep.DEVICE_TRANSFER || current.loggedIn) break
                val transferId = current.transferId ?: break
                val challenge = current.challengeToken ?: break

                when (val result = repository.transferStatus(transferId, challenge)) {
                    is TransferStatusResult.Approved -> {
                        stopTransferJobs()
                        _state.update { it.copy(isLoading = false, loggedIn = true, error = null) }
                        registerDeviceInBackground()
                        break
                    }
                    is TransferStatusResult.Pending -> _state.update {
                        it.copy(
                            transferSecondsLeft = result.secondsLeft,
                            transferSubmissionsLeft = result.submissionsLeft,
                        )
                    }
                    is TransferStatusResult.Error -> {
                        stopTransferJobs()
                        _state.update { it.copy(isLoading = false, error = result.message) }
                        break
                    }
                }
            }
        }
    }

    private fun stopTransferJobs() {
        transferPollingJob?.cancel()
        transferCountdownJob?.cancel()
        transferPollingJob = null
        transferCountdownJob = null
    }

    fun backToCredentials() {
        stopTransferJobs()
        _state.update {
            it.copy(
                step = LoginStep.CREDENTIALS,
                code = "",
                challengeToken = null,
                transferId = null,
                transferSecondsLeft = 0,
                transferSubmissionsLeft = 0,
                transferHint = null,
                error = null,
                isLoading = false,
            )
        }
    }

    /** PUT /devices/me tras un login correcto; si falla, la app sigue funcionando. */
    private fun registerDeviceInBackground() {
        viewModelScope.launch {
            ServiceLocator.deviceRepository.registerDevice()
        }
    }

    // ── Recuperación de contraseña ────────────────────────────────────────────

    fun openRecovery() {
        _state.update {
            it.copy(
                showRecovery = true,
                recoveryIdentifier = it.username.trim(),
                recoveryMessage = null,
                recoveryError = null,
                recoveryPreviewUrl = null,
            )
        }
    }

    fun closeRecovery() {
        _state.update {
            it.copy(showRecovery = false, recoveryLoading = false, recoveryError = null)
        }
    }

    fun onRecoveryIdentifierChange(value: String) {
        _state.update { it.copy(recoveryIdentifier = value, recoveryError = null) }
    }

    fun requestPasswordReset() {
        val identifier = _state.value.recoveryIdentifier.trim()
        if (_state.value.recoveryLoading || identifier.isBlank()) return
        _state.update { it.copy(recoveryLoading = true, recoveryError = null, recoveryMessage = null) }

        viewModelScope.launch {
            when (val result = repository.requestPasswordReset(identifier)) {
                is RecoveryResult.Success -> _state.update {
                    it.copy(
                        recoveryLoading = false,
                        recoveryMessage = result.message,
                        recoveryPreviewUrl = result.previewUrl,
                    )
                }
                is RecoveryResult.Error -> _state.update {
                    it.copy(recoveryLoading = false, recoveryError = result.message)
                }
            }
        }
    }
}
