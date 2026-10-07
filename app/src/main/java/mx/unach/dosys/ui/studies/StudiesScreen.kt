package mx.unach.dosys.ui.studies

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.lifecycle.viewmodel.compose.viewModel
import mx.unach.dosys.data.model.PatientStudy
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.components.StatusChip
import mx.unach.dosys.ui.components.openBytesWithDevice
import mx.unach.dosys.ui.format.formatClinicalDateTime

/**
 * Estudios de laboratorio e imagen del paciente: estado y descarga del
 * resultado en PDF (protegido con huella SHA-256 en el servidor).
 */
@Composable
fun StudiesScreen(
    onBack: () -> Unit,
    viewModel: StudiesViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    LaunchedEffect(state.pending) {
        val pending = state.pending ?: return@LaunchedEffect
        val opened = openBytesWithDevice(context, pending.bytes, pending.name, "application/pdf")
        if (!opened) {
            viewModel.report("No hay una aplicación instalada para ver el PDF")
        }
        viewModel.clearPending()
    }

    ScreenScaffold(title = "Mis estudios", onBack = onBack) { padding ->
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
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            state.message?.let { message ->
                item {
                    Text(
                        text = message,
                        color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }

            if (!state.isLoading && state.studies.isEmpty()) {
                item {
                    Text(
                        text = "Todavía no tienes estudios solicitados. Cuando tu médico pida uno, aparecerá aquí con su resultado.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            items(state.studies, key = { it.id }) { study ->
                StudyCard(study = study, onOpenResult = { viewModel.openResult(study) })
            }
        }
    }
}

@Composable
private fun StudyCard(study: PatientStudy, onOpenResult: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(
                text = study.studyName,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Solicitado el ${formatClinicalDateTime(study.requestedAt)}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                StatusChip(text = statusLabel(study.status), color = statusColor(study.status))
                study.performedAt?.let { moment ->
                    Spacer(Modifier.height(0.dp))
                    Text(
                        text = "  Listo el ${formatClinicalDateTime(moment)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            if (study.documentId != null) {
                Spacer(Modifier.height(10.dp))
                Button(onClick = onOpenResult, modifier = Modifier.fillMaxWidth()) {
                    Text("Ver resultado (PDF)")
                }
            }
        }
    }
}

private fun statusLabel(status: String): String = when (status) {
    "completed" -> "Listo"
    "in_progress" -> "En proceso"
    "cancelled" -> "Cancelado"
    else -> "Solicitado"
}

@Composable
private fun statusColor(status: String) = when (status) {
    "completed" -> MaterialTheme.colorScheme.primary
    "cancelled" -> MaterialTheme.colorScheme.error
    else -> MaterialTheme.colorScheme.tertiary
}
