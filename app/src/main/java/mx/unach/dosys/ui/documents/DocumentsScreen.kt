package mx.unach.dosys.ui.documents

import android.content.Context
import android.content.Intent
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
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Description
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import mx.unach.dosys.data.model.PatientDocument
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.format.formatClinicalDateTime
import java.io.File

/**
 * Documentos que el hospital subió al expediente: solo lectura y descarga.
 */
@Composable
fun DocumentsScreen(
    onBack: () -> Unit,
    viewModel: DocumentsViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    LaunchedEffect(state.pending) {
        state.pending?.let { document ->
            val opened = openWithDevice(context, document)
            if (!opened) {
                viewModel.report("No hay una aplicación para abrir este archivo")
            }
            viewModel.clearPending()
        }
    }

    ScreenScaffold(title = "Mis documentos", onBack = onBack) { padding ->
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
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }

            if (!state.isLoading && state.documents.isEmpty() && state.error == null) {
                item {
                    Text(
                        text = "Todavía no hay documentos en tu expediente.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            items(state.documents, key = { it.id }) { document ->
                DocumentCard(
                    document = document,
                    isOpening = state.openingId == document.id,
                    onOpen = { viewModel.open(document) },
                )
            }
        }
    }
}

@Composable
private fun DocumentCard(document: PatientDocument, isOpening: Boolean, onOpen: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.Description, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.size(8.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        text = document.title,
                        style = MaterialTheme.typography.titleSmall,
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
            Spacer(Modifier.height(12.dp))
            Button(
                onClick = onOpen,
                enabled = !isOpening,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (isOpening) "Descargando…" else "Abrir documento")
            }
        }
    }
}

private fun categoryLabel(category: String): String = when (category) {
    "estudio" -> "Estudio"
    "receta" -> "Receta"
    "informe" -> "Informe"
    "identificacion" -> "Identificación"
    else -> "Documento"
}

private fun sizeLabel(bytes: Long): String = when {
    bytes < 1024 -> "$bytes B"
    bytes < 1024 * 1024 -> "${bytes / 1024} KB"
    else -> String.format("%.1f MB", bytes / (1024.0 * 1024.0))
}

/** Guarda el archivo en la caché privada y lo entrega a la app que pueda abrirlo. */
private fun openWithDevice(context: Context, document: OpenedDocument): Boolean {
    val directory = File(context.cacheDir, "documentos").apply { mkdirs() }
    val file = File(directory, document.fileName.ifBlank { "documento" })
    file.writeBytes(document.bytes)

    val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    val intent = Intent(Intent.ACTION_VIEW).apply {
        setDataAndType(uri, document.contentType)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    return runCatching { context.startActivity(intent) }.isSuccess
}
