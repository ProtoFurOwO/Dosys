package mx.unach.dosys.ui.studies

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.PatientStudy
import mx.unach.dosys.data.repository.ClinicalResult

/** Archivo listo para abrirse con la app que el paciente elija. */
data class PendingFile(val bytes: ByteArray, val name: String)

data class StudiesUiState(
    val studies: List<PatientStudy> = emptyList(),
    val isLoading: Boolean = true,
    val error: String? = null,
    val message: String? = null,
    val pending: PendingFile? = null,
)

/** Estudios solicitados al paciente y descarga de sus resultados. */
class StudiesViewModel : ViewModel() {

    private val repository = ServiceLocator.patientRepository
    private val _state = MutableStateFlow(StudiesUiState())
    val state: StateFlow<StudiesUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.studies()) {
                is ClinicalResult.Success -> _state.update { it.copy(isLoading = false, studies = result.value) }
                is ClinicalResult.Error -> _state.update { it.copy(isLoading = false, error = result.message) }
            }
        }
    }

    fun openResult(study: PatientStudy) {
        val documentId = study.documentId ?: return
        viewModelScope.launch {
            when (val result = repository.documentFile(documentId)) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(pending = PendingFile(result.value, "resultado-estudio-${study.id}.pdf"), error = null)
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

    fun dismissMessage() {
        _state.update { it.copy(message = null) }
    }
}
