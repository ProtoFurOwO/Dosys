package mx.unach.dosys.ui.record

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
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import mx.unach.dosys.ui.components.BiometricGate
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.format.formatClinicalDate
import mx.unach.dosys.ui.format.formatClinicalDateTime

/**
 * Expediente clínico del paciente (solo lectura).
 * Perfil y consultas desde la API; otros apartados se integrarán después.
 */
@Composable
fun RecordScreen(
    onBack: () -> Unit,
    viewModel: RecordViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()
    // El expediente se desbloquea con huella en cada entrada a la pantalla.
    var unlocked by remember { mutableStateOf(false) }

    if (unlocked) {
        RecordContent(state = state, onBack = onBack)
    } else {
        ScreenScaffold(title = "Mi expediente", onBack = onBack) { padding ->
            BiometricGate(
                onUnlocked = { unlocked = true },
                modifier = Modifier.padding(padding),
            )
        }
    }
}

@Composable
private fun RecordContent(state: RecordUiState, onBack: () -> Unit) {
    ScreenScaffold(title = "Mi expediente", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (state.isLoading) {
                item {
                    CircularProgressIndicator()
                }
            }
            state.error?.let { error ->
                item {
                    Text(
                        text = error,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
            state.profile?.let { profile ->
                item {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp)) {
                            Text("Datos del paciente", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                            Spacer(Modifier.height(8.dp))
                            InfoRow("Nombre", profile.fullName)
                            InfoRow("CURP", profile.curp ?: "No registrado")
                            InfoRow("Nacimiento", formatClinicalDate(profile.birthDate))
                            InfoRow("Tipo de sangre", profile.bloodType ?: "No registrado")
                            InfoRow("Contacto de emergencia", profile.emergencyContact ?: "No registrado")
                        }
                    }
                }
            }
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text("Alergias, antecedentes y diagnósticos crónicos", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "Estos apartados se integrarán en una siguiente entrega. La información mostrada abajo proviene de la API.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            item {
                Text(
                    text = "Historial de consultas",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
            items(state.consultations, key = { it.id }) { consultation ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text(formatClinicalDateTime(consultation.createdAt), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                        Text(consultation.specialty, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                        Text(consultation.doctorName, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(8.dp))
                        InfoRow("Motivo", consultation.reason)
                        InfoRow("Diagnóstico", consultation.diagnosis)
                    }
                }
            }
            if (!state.isLoading && state.error == null && state.consultations.isEmpty()) {
                item {
                    Text(
                        text = "No hay consultas registradas.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
            item {
                Text(
                    text = "Solo lectura. Si detectas un dato incorrecto, comunícalo en tu próxima consulta.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Column(Modifier.padding(vertical = 2.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}
