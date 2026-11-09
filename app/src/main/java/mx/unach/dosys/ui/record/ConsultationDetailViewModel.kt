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
import mx.unach.dosys.data.repository.ClinicalResult

data class ConsultationDetailUiState(
    val consultation: PatientConsultation? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
)

class ConsultationDetailViewModel : ViewModel() {

    private val repository = ServiceLocator.patientRepository

    private val _state = MutableStateFlow(ConsultationDetailUiState())
    val state: StateFlow<ConsultationDetailUiState> = _state.asStateFlow()

    private var loadedId: Int? = null

    fun load(consultationId: Int) {
        if (loadedId == consultationId) return
        loadedId = consultationId
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.consultations()) {
                is ClinicalResult.Success -> {
                    val consultation = result.value.firstOrNull { it.id == consultationId }
                    _state.update {
                        it.copy(
                            consultation = consultation,
                            isLoading = false,
                            error = if (consultation == null) "No encontramos esa consulta." else null,
                        )
                    }
                }
                is ClinicalResult.Error -> {
                    loadedId = null
                    _state.update { it.copy(isLoading = false, error = result.message) }
                }
            }
        }
    }
}
