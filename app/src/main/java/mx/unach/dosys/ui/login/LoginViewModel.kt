package mx.unach.dosys.ui.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.repository.AuthResult
import mx.unach.dosys.data.repository.RecoveryResult

/** Paso actual del inicio de sesión. */
enum class LoginStep { CREDENTIALS, TWO_FACTOR }

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
                is AuthResult.Success -> _state.update { it.copy(isLoading = false, loggedIn = true) }
                is AuthResult.NeedsTwoFactor -> _state.update {
                    it.copy(
                        isLoading = false,
                        step = LoginStep.TWO_FACTOR,
                        challengeToken = result.challengeToken,
                        code = "",
                        error = null,
                    )
                }
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
                is AuthResult.Success -> _state.update { it.copy(isLoading = false, loggedIn = true) }
                is AuthResult.Error -> _state.update { it.copy(isLoading = false, error = result.message) }
                is AuthResult.NeedsTwoFactor -> _state.update { it.copy(isLoading = false) }
            }
        }
    }

    fun backToCredentials() {
        _state.update {
            it.copy(step = LoginStep.CREDENTIALS, code = "", challengeToken = null, error = null)
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
