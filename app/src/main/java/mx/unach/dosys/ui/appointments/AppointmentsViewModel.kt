package mx.unach.dosys.ui.appointments

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

data class AppointmentsUiState(
    val appointments: List<PatientAppointment> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
)

class AppointmentsViewModel : ViewModel() {

    private val repository = ServiceLocator.patientRepository

    private val _state = MutableStateFlow(AppointmentsUiState())
    val state: StateFlow<AppointmentsUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        if (_state.value.isLoading) return
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.appointments()) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(appointments = result.value, isLoading = false)
                }
                is ClinicalResult.Error -> _state.update {
                    it.copy(isLoading = false, error = result.message)
                }
            }
        }
    }
}
