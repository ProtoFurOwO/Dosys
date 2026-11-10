package mx.unach.dosys.ui.documents

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import mx.unach.dosys.data.model.DocumentIntegrityResponse
import mx.unach.dosys.data.model.PatientDocument
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.format.formatClinicalDateTime

/**
 * Detalle de un documento clínico: solo lectura, descarga y verificación de la
 * firma electrónica. No permite modificar ni reemplazar el archivo.
 */
@Composable
fun DocumentDetailScreen(
    documentId: Int,
    onBack: () -> Unit,
    viewModel: DocumentDetailViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    LaunchedEffect(documentId) {
        viewModel.load(documentId)
    }
    LaunchedEffect(state.pending) {
        state.pending?.let { document ->
            val opened = openWithDevice(context, document)
            if (!opened) {
                viewModel.report("No hay una aplicación para abrir este archivo")
            }
            viewModel.clearPending()
        }
    }

    ScreenScaffold(title = "Documento", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (state.isLoading) {
                item { CircularProgressIndicator() }
            }
            state.error?.let { message ->
                item {
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
            state.document?.let { document ->
                item { DocumentHeader(document) }
                item {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Button(
                            onClick = viewModel::open,
                            enabled = !state.isOpening,
                            modifier = Modifier.weight(1f),
                        ) {
                            Text(if (state.isOpening) "Descargando…" else "Abrir documento")
                        }
                        OutlinedButton(
                            onClick = viewModel::verify,
                            enabled = !state.isVerifying,
                            modifier = Modifier.weight(1f),
                        ) {
                            Text(if (state.isVerifying) "Verificando…" else "Verificar firma")
                        }
                    }
                }
                state.integrity?.let { integrity ->
                    item { IntegrityBanner(integrity) }
                }
                item {
                    Text(
                        text = "La app es solo lectura para documentos clínicos. No puedes modificarlos ni reemplazarlos desde aquí.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun DocumentHeader(document: PatientDocument) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Filled.Description,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                )
                Spacer(Modifier.size(8.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        text = document.title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        text = "${categoryLabel(document.category)} · ${sizeLabel(document.sizeBytes)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = formatClinicalDateTime(document.createdAt),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Spacer(Modifier.height(14.dp))
            Text(
                text = "Firma electrónica",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = signaturePreview(document.sha256),
                style = MaterialTheme.typography.bodyMedium,
                fontFamily = FontFamily.Monospace,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun IntegrityBanner(integrity: DocumentIntegrityResponse) {
    val container = if (integrity.intact) Color(0xFFE7F0E8) else Color(0xFFF8E9E9)
    val content = if (integrity.intact) Color(0xFF2C5D38) else Color(0xFF8F3434)
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = container, contentColor = content),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = if (integrity.intact) Icons.Filled.CheckCircle else Icons.Filled.Warning,
                    contentDescription = null,
                )
                Spacer(Modifier.size(8.dp))
                Text(
                    text = if (integrity.intact) {
                        "Firma electrónica válida. El archivo no ha cambiado."
                    } else {
                        "Documento alterado. La firma electrónica no coincide."
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Bold,
                )
            }
            if (integrity.message.isNotBlank()) {
                Spacer(Modifier.height(6.dp))
                Text(
                    text = integrity.message,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            if (integrity.signatureAlgorithm.isNotBlank()) {
                Spacer(Modifier.height(6.dp))
                Text(
                    text = "Firma ${integrity.signatureAlgorithm}" +
                        if (integrity.publicKeyFingerprint.isNotBlank()) {
                            " · llave ${integrity.publicKeyFingerprint.take(16)}…"
                        } else {
                            ""
                        },
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                )
            }
            if (!integrity.intact) {
                Spacer(Modifier.height(8.dp))
                Text(
                    text = "Contacta a recepción o al personal médico para reemplazarlo.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
