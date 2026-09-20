package mx.unach.dosys.ui.record

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.PatientConsultation
import mx.unach.dosys.data.model.PatientProfile
import mx.unach.dosys.data.repository.ClinicalResult

data class RecordUiState(
    val profile: PatientProfile? = null,
    val consultations: List<PatientConsultation> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
)

class RecordViewModel : ViewModel() {

    private val repository = ServiceLocator.patientRepository

    private val _state = MutableStateFlow(RecordUiState())
    val state: StateFlow<RecordUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        if (_state.value.isLoading) return
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            val profileResult = repository.profile()
            val consultationsResult = repository.consultations()
            _state.update {
                it.copy(
                    profile = (profileResult as? ClinicalResult.Success)?.value,
                    consultations = (consultationsResult as? ClinicalResult.Success)?.value.orEmpty(),
                    isLoading = false,
                    error = listOfNotNull(
                        (profileResult as? ClinicalResult.Error)?.message,
                        (consultationsResult as? ClinicalResult.Error)?.message,
                    ).firstOrNull(),
                )
            }
        }
    }
}
