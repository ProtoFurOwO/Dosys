package mx.unach.dosys.ui.security

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.TwoFactorSetup
import mx.unach.dosys.data.repository.ClinicalResult

data class SecurityUiState(
    val enabled: Boolean = false,
    val recoveryCodesRemaining: Int = 0,
    val setup: TwoFactorSetup? = null,
    val recoveryCodes: List<String> = emptyList(),
    val isLoading: Boolean = false,
    val isSubmitting: Boolean = false,
    val error: String? = null,
    val message: String? = null,
)

class SecurityViewModel : ViewModel() {

    private val repository = ServiceLocator.securityRepository

    private val _state = MutableStateFlow(SecurityUiState())
    val state: StateFlow<SecurityUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        if (_state.value.isLoading) return
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.status()) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(
                        isLoading = false,
                        enabled = result.value.enabled,
                        recoveryCodesRemaining = result.value.recoveryCodesRemaining,
                    )
                }
                is ClinicalResult.Error -> _state.update { it.copy(isLoading = false, error = result.message) }
            }
        }
    }

    fun startSetup() {
        if (_state.value.isSubmitting) return
        _state.update { it.copy(isSubmitting = true, error = null, message = null) }
        viewModelScope.launch {
            when (val result = repository.setup()) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(isSubmitting = false, setup = result.value)
                }
                is ClinicalResult.Error -> _state.update { it.copy(isSubmitting = false, error = result.message) }
            }
        }
    }

    fun confirm(code: String) {
        if (_state.value.isSubmitting || code.isBlank()) return
        _state.update { it.copy(isSubmitting = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.confirm(code)) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(
                        isSubmitting = false,
                        enabled = true,
                        setup = null,
                        recoveryCodes = result.value.recoveryCodes,
                        recoveryCodesRemaining = result.value.recoveryCodes.size,
                        message = "Segundo factor activado",
                    )
                }
                is ClinicalResult.Error -> _state.update { it.copy(isSubmitting = false, error = result.message) }
            }
        }
    }

    fun disable(password: String) {
        if (_state.value.isSubmitting || password.isBlank()) return
        _state.update { it.copy(isSubmitting = true, error = null, message = null) }
        viewModelScope.launch {
            when (val result = repository.disable(password)) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(
                        isSubmitting = false,
                        enabled = false,
                        recoveryCodesRemaining = 0,
                        message = "Segundo factor desactivado",
                    )
                }
                is ClinicalResult.Error -> _state.update { it.copy(isSubmitting = false, error = result.message) }
            }
        }
    }

    fun dismissRecoveryCodes() {
        _state.update { it.copy(recoveryCodes = emptyList()) }
    }
}
