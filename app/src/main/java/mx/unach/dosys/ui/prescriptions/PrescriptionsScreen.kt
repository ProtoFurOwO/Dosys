package mx.unach.dosys.ui.prescriptions

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import mx.unach.dosys.data.model.PatientPrescription
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.components.openBytesWithDevice
import mx.unach.dosys.ui.format.formatClinicalDateTime

/**
 * Recetas emitidas por el médico con sus medicamentos y el PDF firmado
 * (huella SHA-256 verificable en el portal clínico).
 */
@Composable
fun PrescriptionsScreen(
    onBack: () -> Unit,
    viewModel: PrescriptionsViewModel = viewModel(),
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

    ScreenScaffold(title = "Mis recetas", onBack = onBack) { padding ->
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

            if (!state.isLoading && state.prescriptions.isEmpty()) {
                item {
                    Text(
                        text = "Todavía no tienes recetas. Cuando tu médico emita una, aparecerá aquí junto con su PDF.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            items(state.prescriptions, key = { it.id }) { prescription ->
                PrescriptionCard(prescription = prescription, onOpenPdf = { viewModel.openPdf(prescription) })
            }
        }
    }
}

@Composable
private fun PrescriptionCard(prescription: PatientPrescription, onOpenPdf: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(
                text = "Receta del ${formatClinicalDateTime(prescription.createdAt)}",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(8.dp))
            prescription.items.forEach { item ->
                val detalle = buildString {
                    append(item.medication)
                    append(" — ")
                    append(item.dose)
                    append(" · ")
                    append(item.frequency)
                    item.duration?.let {
                        append(" · ")
                        append(it)
                    }
                }
                Text(
                    text = "• $detalle",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            prescription.notes?.let { notes ->
                Spacer(Modifier.height(6.dp))
                Text(
                    text = notes,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (prescription.documentId != null) {
                Spacer(Modifier.height(10.dp))
                Button(onClick = onOpenPdf, modifier = Modifier.fillMaxWidth()) {
                    Text("Receta en PDF")
                }
            }
        }
    }
}
