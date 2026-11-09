package mx.unach.dosys.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.data.model.PatientPrescription
import mx.unach.dosys.data.repository.ClinicalResult
import mx.unach.dosys.ui.appointments.AppointmentFilters
import java.time.OffsetDateTime

data class HomeUiState(
    val patientName: String = "Paciente",
    val nextAppointment: PatientAppointment? = null,
    val prescriptions: List<PatientPrescription> = emptyList(),
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
            val prescriptionsResult = repository.prescriptions()
            val profile = (profileResult as? ClinicalResult.Success)?.value
            val appointments = (appointmentsResult as? ClinicalResult.Success)?.value.orEmpty()
            val prescriptions = (prescriptionsResult as? ClinicalResult.Success)?.value.orEmpty()
            val error = listOfNotNull(
                (profileResult as? ClinicalResult.Error)?.message,
                (appointmentsResult as? ClinicalResult.Error)?.message,
            ).firstOrNull()

            val now = OffsetDateTime.now()
            val next = AppointmentFilters.nextUpcoming(appointments, now)

            _state.update {
                it.copy(
                    patientName = profile?.fullName ?: it.patientName,
                    nextAppointment = next,
                    prescriptions = prescriptions.take(3),
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
