package mx.unach.dosys.ui.documents

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.PatientDocument
import mx.unach.dosys.data.repository.ClinicalResult

/** Archivo descargado listo para abrir con la app que el paciente prefiera. */
data class OpenedDocument(
    val id: Int,
    val fileName: String,
    val contentType: String,
    val bytes: ByteArray,
) {
    override fun equals(other: Any?): Boolean = other is OpenedDocument && other.id == id

    override fun hashCode(): Int = id
}

data class DocumentsUiState(
    val documents: List<PatientDocument> = emptyList(),
    val isLoading: Boolean = false,
    val openingId: Int? = null,
    val error: String? = null,
    val pending: OpenedDocument? = null,
)

class DocumentsViewModel : ViewModel() {

    private val repository = ServiceLocator.patientRepository

    private val _state = MutableStateFlow(DocumentsUiState())
    val state: StateFlow<DocumentsUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        if (_state.value.isLoading) return
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.documents()) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(documents = result.value, isLoading = false)
                }
                is ClinicalResult.Error -> _state.update { it.copy(isLoading = false, error = result.message) }
            }
        }
    }

    fun open(document: PatientDocument) {
        if (_state.value.openingId != null) return
        _state.update { it.copy(openingId = document.id, error = null) }
        viewModelScope.launch {
            when (val result = repository.documentFile(document.id)) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(
                        openingId = null,
                        pending = OpenedDocument(
                            id = document.id,
                            fileName = document.originalName,
                            contentType = document.contentType,
                            bytes = result.value,
                        ),
                    )
                }
                is ClinicalResult.Error -> _state.update { it.copy(openingId = null, error = result.message) }
            }
        }
    }

    fun clearPending() {
        _state.update { it.copy(pending = null) }
    }

    fun report(message: String) {
        _state.update { it.copy(error = message) }
    }
}
