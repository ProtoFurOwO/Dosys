package mx.unach.dosys.ui.appointments

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.AppointmentAvailabilitySlot
import mx.unach.dosys.data.model.AppointmentRequest
import mx.unach.dosys.data.model.DoctorOption
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.data.repository.ClinicalResult
import java.time.LocalDate

enum class AppointmentRequestStep {
    DOCTOR,
    DATE,
    SLOTS,
    REASON,
    SUCCESS,
}

data class AppointmentRequestUiState(
    val step: AppointmentRequestStep = AppointmentRequestStep.DOCTOR,
    val doctors: List<DoctorOption> = emptyList(),
    val isLoadingDoctors: Boolean = false,
    val selectedDoctor: DoctorOption? = null,
    val selectedDate: LocalDate? = null,
    val slots: List<AppointmentAvailabilitySlot> = emptyList(),
    val isLoadingSlots: Boolean = false,
    val selectedSlot: AppointmentAvailabilitySlot? = null,
    val reason: String = "",
    val isSubmitting: Boolean = false,
    val error: String? = null,
    val created: PatientAppointment? = null,
)

class AppointmentRequestViewModel : ViewModel() {

    private val repository = ServiceLocator.patientRepository

    private val _state = MutableStateFlow(AppointmentRequestUiState())
    val state: StateFlow<AppointmentRequestUiState> = _state.asStateFlow()

    init {
        loadDoctors()
    }

    fun loadDoctors() {
        if (_state.value.isLoadingDoctors) return
        _state.update { it.copy(isLoadingDoctors = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.doctors()) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(doctors = result.value, isLoadingDoctors = false)
                }
                is ClinicalResult.Error -> _state.update {
                    it.copy(isLoadingDoctors = false, error = result.message)
                }
            }
        }
    }

    fun selectDoctor(doctor: DoctorOption) {
        _state.update {
            it.copy(
                step = AppointmentRequestStep.DATE,
                selectedDoctor = doctor,
                selectedDate = null,
                slots = emptyList(),
                selectedSlot = null,
                error = null,
            )
        }
    }

    fun selectDate(date: LocalDate) {
        _state.update {
            it.copy(
                step = AppointmentRequestStep.SLOTS,
                selectedDate = date,
                slots = emptyList(),
                selectedSlot = null,
                error = null,
            )
        }
        loadAvailability()
    }

    fun selectSlot(slot: AppointmentAvailabilitySlot) {
        if (!slot.available) return
        _state.update {
            it.copy(
                step = AppointmentRequestStep.REASON,
                selectedSlot = slot,
                error = null,
            )
        }
    }

    fun updateReason(value: String) {
        _state.update { it.copy(reason = value.take(300), error = null) }
    }

    fun submit() {
        val current = _state.value
        val doctor = current.selectedDoctor ?: return
        val date = current.selectedDate ?: return
        val slot = current.selectedSlot ?: return
        if (current.isSubmitting) return
        if (current.reason.isBlank()) {
            _state.update { it.copy(error = "Escribe el motivo de la consulta.") }
            return
        }

        _state.update { it.copy(isSubmitting = true, error = null) }
        viewModelScope.launch {
            val request = AppointmentRequest(
                doctorId = doctor.id,
                specialty = doctor.specialty,
                date = date.toString(),
                time = slot.time,
                reason = current.reason.trim(),
            )
            when (val result = repository.requestAppointment(request)) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(isSubmitting = false, step = AppointmentRequestStep.SUCCESS, created = result.value)
                }
                is ClinicalResult.Error -> {
                    _state.update {
                        it.copy(
                            isSubmitting = false,
                            error = result.message,
                            step = if (result.code == 409) {
                                AppointmentRequestStep.SLOTS
                            } else {
                                it.step
                            },
                            selectedSlot = if (result.code == 409) null else it.selectedSlot,
                        )
                    }
                    if (result.code == 409) {
                        loadAvailability()
                    }
                }
            }
        }
    }

    fun retryDoctors() {
        loadDoctors()
    }

    fun reloadSlots() {
        loadAvailability(clearError = true)
    }

    private fun loadAvailability(clearError: Boolean = false) {
        val current = _state.value
        val doctor = current.selectedDoctor ?: return
        val date = current.selectedDate ?: return
        if (current.isLoadingSlots) return
        _state.update {
            it.copy(
                isLoadingSlots = true,
                error = if (clearError) null else it.error,
            )
        }
        viewModelScope.launch {
            when (val result = repository.availability(doctor.id, date.toString())) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(slots = result.value.slots, isLoadingSlots = false)
                }
                is ClinicalResult.Error -> _state.update {
                    it.copy(isLoadingSlots = false, error = result.message)
                }
            }
        }
    }

    /** true si la pantalla debe cerrarse; false si solo retrocede un paso. */
    fun goBack(): Boolean {
        val current = _state.value
        when (current.step) {
            AppointmentRequestStep.DOCTOR,
            AppointmentRequestStep.SUCCESS,
            -> return true

            AppointmentRequestStep.DATE -> _state.update {
                it.copy(step = AppointmentRequestStep.DOCTOR, selectedDoctor = null)
            }

            AppointmentRequestStep.SLOTS -> _state.update {
                it.copy(step = AppointmentRequestStep.DATE, selectedDate = null, slots = emptyList())
            }

            AppointmentRequestStep.REASON -> _state.update {
                it.copy(step = AppointmentRequestStep.SLOTS, selectedSlot = null)
            }
        }
        return false
    }
}
