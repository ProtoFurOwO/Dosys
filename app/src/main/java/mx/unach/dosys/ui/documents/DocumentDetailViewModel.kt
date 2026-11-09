package mx.unach.dosys.ui.documents

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.model.DocumentIntegrityResponse
import mx.unach.dosys.data.model.PatientDocument
import mx.unach.dosys.data.repository.ClinicalResult

data class DocumentDetailUiState(
    val document: PatientDocument? = null,
    val isLoading: Boolean = false,
    val isOpening: Boolean = false,
    val isVerifying: Boolean = false,
    val integrity: DocumentIntegrityResponse? = null,
    val error: String? = null,
    val pending: OpenedDocument? = null,
)

class DocumentDetailViewModel : ViewModel() {

    private val repository = ServiceLocator.patientRepository

    private val _state = MutableStateFlow(DocumentDetailUiState())
    val state: StateFlow<DocumentDetailUiState> = _state.asStateFlow()

    private var loadedId: Int? = null

    fun load(documentId: Int) {
        if (loadedId == documentId) return
        loadedId = documentId
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.documents()) {
                is ClinicalResult.Success -> {
                    val document = result.value.firstOrNull { it.id == documentId }
                    _state.update {
                        it.copy(
                            document = document,
                            isLoading = false,
                            error = if (document == null) "No encontramos ese documento." else null,
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

    fun open() {
        val document = _state.value.document ?: return
        if (_state.value.isOpening) return
        _state.update { it.copy(isOpening = true, error = null) }
        viewModelScope.launch {
            when (val result = repository.documentFile(document.id)) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(
                        isOpening = false,
                        pending = OpenedDocument(
                            id = document.id,
                            fileName = document.originalName,
                            contentType = document.contentType,
                            bytes = result.value,
                        ),
                    )
                }
                is ClinicalResult.Error -> _state.update {
                    it.copy(isOpening = false, error = result.message)
                }
            }
        }
    }

    fun verify() {
        val document = _state.value.document ?: return
        if (_state.value.isVerifying) return
        _state.update { it.copy(isVerifying = true, integrity = null, error = null) }
        viewModelScope.launch {
            when (val result = repository.verifyDocument(document.id)) {
                is ClinicalResult.Success -> _state.update {
                    it.copy(isVerifying = false, integrity = result.value)
                }
                is ClinicalResult.Error -> _state.update {
                    it.copy(isVerifying = false, error = result.message)
                }
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
