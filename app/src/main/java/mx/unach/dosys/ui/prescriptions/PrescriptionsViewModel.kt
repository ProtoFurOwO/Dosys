package mx.unach.dosys.ui.prescriptions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.PatientPrescription
import mx.unach.dosys.data.repository.ClinicalResult
import mx.unach.dosys.ui.studies.PendingFile

data class PrescriptionsUiState(
    val prescriptions: List<PatientPrescription> = emptyList(),
    val isLoading: Boolean = true,
    val error: String? = null,
    val message: String? = null,
    val pending: PendingFile? = null,
)

/** Recetas emitidas al paciente y descarga de su PDF firmado. */
class PrescriptionsViewModel : ViewModel() {

    private val repository = ServiceLocator.patientRepository
    private val _state = MutableStateFlow(PrescriptionsUiState())
    val state: StateFlow<PrescriptionsUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.prescriptions()) {
                is ClinicalResult.Success -> _state.update { it.copy(isLoading = false, prescriptions = result.value) }
                is ClinicalResult.Error -> _state.update { it.copy(isLoading = false, error = result.message) }
            }
        }
    }

    fun openPdf(prescription: PatientPrescription) {
        val documentId = prescription.documentId ?: return
        viewModelScope.launch {
            when (val result = repository.documentFile(documentId)) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(pending = PendingFile(result.value, "receta-${prescription.id}.pdf"), error = null)
                }
                is ClinicalResult.Error -> _state.update { it.copy(error = result.message) }
            }
        }
    }

    fun report(message: String) {
        _state.update { it.copy(message = message) }
    }

    fun clearPending() {
        _state.update { it.copy(pending = null) }
    }
}
