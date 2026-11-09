package mx.unach.dosys.ui.checkin

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.data.repository.ClinicalResult

data class CheckInUiState(
    val appointments: List<PatientAppointment> = emptyList(),
    val isLoading: Boolean = false,
    val isSubmitting: Boolean = false,
    val codeInput: String = "",
    val error: String? = null,
    val confirmed: PatientAppointment? = null,
)

class CheckInViewModel : ViewModel() {

    private val repository = ServiceLocator.patientRepository

    private val _state = MutableStateFlow(CheckInUiState())
    val state: StateFlow<CheckInUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        if (_state.value.isLoading) return
        _state.update { it.copy(isLoading = true) }
        viewModelScope.launch {
            when (val result = repository.appointments()) {
                is ClinicalResult.Success -> {
                    _state.update {
                        it.copy(
                            appointments = CheckInAppointments.eligible(result.value),
                            isLoading = false,
                            error = null,
                        )
                    }
                }
                is ClinicalResult.Error -> _state.update { it.copy(isLoading = false, error = result.message) }
            }
        }
    }

    fun onCodeChange(value: String) {
        val clean = value.uppercase().filter { it.isLetterOrDigit() }.take(32)
        _state.update { it.copy(codeInput = clean, error = null) }
    }

    fun onCodeScanned(raw: String) {
        val code = CheckInCode.extract(raw)
        if (code == null) {
            _state.update { it.copy(error = "El código del QR no es válido") }
            return
        }
        submit(code, CheckInCode.appointmentId(raw))
    }

    fun submitManualCode() {
        val code = _state.value.codeInput.trim()
        if (code.isEmpty()) return
        submit(code, null)
    }

    private fun submit(raw: String, appointmentId: Int?) {
        if (_state.value.isSubmitting) return
        val code = CheckInCode.extract(raw)
        if (code == null) {
            _state.update { it.copy(error = "El código del QR no es válido") }
            return
        }

        _state.update { it.copy(isSubmitting = true, error = null) }
        viewModelScope.launch {
            val result = if (appointmentId != null) {
                repository.checkIn(appointmentId, code)
            } else {
                repository.checkInWithCode(code)
            }
            when (result) {
                is ClinicalResult.Success -> _state.update { current ->
                    current.copy(
                        isSubmitting = false,
                        confirmed = result.value,
                        codeInput = "",
                        appointments = current.appointments
                            .map { appointment ->
                                if (appointment.id == result.value.id) result.value else appointment
                            }
                            .filter { it.id != result.value.id } + result.value,
                    )
                }
                is ClinicalResult.Error -> _state.update { it.copy(isSubmitting = false, error = result.message) }
            }
        }
    }

    companion object {
        const val CHECKIN_PREFIX = CheckInCode.PREFIX
    }
}
