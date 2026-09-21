package mx.unach.dosys.ui.checkin

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
                is ClinicalResult.Success -> _state.update {
                    it.copy(appointments = result.value, isLoading = false, error = null)
                }
                is ClinicalResult.Error -> _state.update { it.copy(isLoading = false, error = result.message) }
            }
        }
    }

    fun onCodeChange(value: String) {
        _state.update { it.copy(codeInput = value.uppercase(), error = null) }
    }

    fun onCodeScanned(raw: String) {
        submit(raw)
    }

    fun submitManualCode() {
        val code = _state.value.codeInput.trim()
        if (code.isEmpty()) return
        submit(code)
    }

    private fun submit(raw: String) {
        if (_state.value.isSubmitting) return
        val text = raw.trim()
        val target = if (text.startsWith(CHECKIN_PREFIX)) parseQr(text) else pendingTarget(text)
        if (target == null) {
            _state.update {
                it.copy(
                    error = if (text.startsWith(CHECKIN_PREFIX)) {
                        "El código del QR no es válido"
                    } else {
                        "No tienes citas pendientes para confirmar"
                    }
                )
            }
            return
        }
        _state.update { it.copy(isSubmitting = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.checkIn(target.first, target.second)) {
                is ClinicalResult.Success -> _state.update { current ->
                    current.copy(
                        isSubmitting = false,
                        confirmed = result.value,
                        codeInput = "",
                        appointments = current.appointments.map { appointment ->
                            if (appointment.id == result.value.id) result.value else appointment
                        },
                    )
                }
                is ClinicalResult.Error -> _state.update { it.copy(isSubmitting = false, error = result.message) }
            }
        }
    }

    /** Contenido del QR del hospital: DOSYS-CHECKIN|<cita>|<código>. */
    private fun parseQr(text: String): Pair<Int, String>? {
        val parts = text.split("|")
        val id = parts.getOrNull(1)?.toIntOrNull()
        val code = parts.getOrNull(2)?.takeIf { it.isNotBlank() }
        return if (id != null && code != null) id to code else null
    }

    /** Código escrito a mano: se prueba con la próxima cita sin confirmar. */
    private fun pendingTarget(code: String): Pair<Int, String>? {
        val next = _state.value.appointments.firstOrNull { appointment ->
            appointment.checkedInAt == null &&
                appointment.status != AppointmentStatus.CANCELLED &&
                appointment.status != AppointmentStatus.ATTENDED
        } ?: return null
        return next.id to code
    }

    companion object {
        const val CHECKIN_PREFIX = "DOSYS-CHECKIN|"
    }
}
