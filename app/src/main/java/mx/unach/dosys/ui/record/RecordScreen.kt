package mx.unach.dosys.ui.record

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import mx.unach.dosys.data.mock.MockData
import mx.unach.dosys.ui.components.ScreenScaffold

/**
 * Expediente clínico del paciente (solo lectura).
 * Alergias, crónicas, antecedentes y consultas anteriores.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun RecordScreen(onBack: () -> Unit) {
    ScreenScaffold(title = "Mi expediente", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text("Datos del paciente", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.height(8.dp))
                        InfoRow("Nombre", MockData.PATIENT_NAME)
                        InfoRow("CURP", MockData.PATIENT_CURP)
                        InfoRow("Nacimiento", "${MockData.BIRTH_DATE} (${MockData.AGE} años)")
                        InfoRow("Tipo de sangre", MockData.BLOOD_TYPE)
                        InfoRow("Contacto de emergencia", MockData.EMERGENCY_CONTACT)
                    }
                }
            }
            item {
                ChipSection(
                    title = "Alergias",
                    empty = "Sin alergias registradas",
                    items = MockData.allergies,
                )
            }
            item {
                ChipSection(
                    title = "Enfermedades crónicas",
                    empty = "Sin enfermedades crónicas registradas",
                    items = MockData.chronicConditions,
                )
            }
            item {
                ChipSection(
                    title = "Antecedentes",
                    empty = "Sin antecedentes",
                    items = MockData.antecedents,
                )
            }
            item {
                Text(
                    text = "Historial de consultas",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
            items(MockData.consultations.reversed()) { consultation ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text(consultation.date, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                        Text(consultation.specialty, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                        Text(consultation.doctor, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(8.dp))
                        InfoRow("Motivo", consultation.reason)
                        InfoRow("Diagnóstico", consultation.diagnosis)
                    }
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

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChipSection(title: String, empty: String, items: List<String>) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(8.dp))
            if (items.isEmpty()) {
                Text(empty, style = MaterialTheme.typography.bodyMedium)
            } else {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    items.forEach { SuggestionChip(onClick = {}, label = { Text(it) }) }
                }
            }
        }
    }
}
