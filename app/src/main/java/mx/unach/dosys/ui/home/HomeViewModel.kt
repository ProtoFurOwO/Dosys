package mx.unach.dosys.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.AppointmentStatus
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.data.repository.ClinicalResult

data class HomeUiState(
    val patientName: String = "Paciente",
    val nextAppointment: PatientAppointment? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
)

class HomeViewModel : ViewModel() {

    private val repository = ServiceLocator.patientRepository
    private val sessionManager = ServiceLocator.sessionManager

    private val _state = MutableStateFlow(HomeUiState())
    val state: StateFlow<HomeUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        if (_state.value.isLoading) return
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            val profileResult = repository.profile()
            val appointmentsResult = repository.appointments()
            val profile = (profileResult as? ClinicalResult.Success)?.value
            val appointments = (appointmentsResult as? ClinicalResult.Success)?.value.orEmpty()
            val error = listOfNotNull(
                (profileResult as? ClinicalResult.Error)?.message,
                (appointmentsResult as? ClinicalResult.Error)?.message,
            ).firstOrNull()

            _state.update {
                it.copy(
                    patientName = profile?.fullName ?: it.patientName,
                    nextAppointment = appointments.firstOrNull {
                        it.status == AppointmentStatus.SCHEDULED || it.status == AppointmentStatus.CONFIRMED
                    },
                    isLoading = false,
                    error = error,
                )
            }
        }
    }

    fun logout(onComplete: () -> Unit) {
        viewModelScope.launch {
            ServiceLocator.authRepository.logout()
            onComplete()
        }
    }
}
