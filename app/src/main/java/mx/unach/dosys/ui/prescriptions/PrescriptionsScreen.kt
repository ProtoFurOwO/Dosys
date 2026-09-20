package mx.unach.dosys.ui.prescriptions

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
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import mx.unach.dosys.data.mock.MockData
import mx.unach.dosys.ui.components.ScreenScaffold

/**
 * Recetas del médico + seguimiento de tomas.
 * El paciente NO edita la receta: solo marca "ya la tomé".
 */
@Composable
fun PrescriptionsScreen(onBack: () -> Unit) {
    var takenIds by remember {
        mutableStateOf(MockData.prescriptions.flatMap { it.doses }.filter { it.taken }.map { it.id }.toSet())
    }

    ScreenScaffold(title = "Mis recetas", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Text(
                    text = "Tu médico envía la receta. Tú solo registras cada toma — no puedes cambiar dosis ni medicamento.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            items(MockData.prescriptions, key = { it.id }) { prescription ->
                val extraTaken = prescription.doses.count { it.id in takenIds && !it.taken }
                val currentTaken = prescription.taken + extraTaken
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text(prescription.medication, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                        Text(prescription.dose, style = MaterialTheme.typography.bodyMedium)
                        Text(
                            text = "${prescription.prescribedBy} · ${prescription.period}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(6.dp))
                        Text(prescription.instructions, style = MaterialTheme.typography.bodySmall)
                        Spacer(Modifier.height(10.dp))
                        LinearProgressIndicator(
                            progress = { currentTaken.toFloat() / prescription.total.toFloat() },
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Text(
                            text = "$currentTaken de ${prescription.total} tomas",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(12.dp))
                        prescription.doses.forEach { dose ->
                            val already = dose.id in takenIds
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Text(
                                    text = if (already) "✓  ${dose.label}" else dose.label,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = if (already) {
                                        MaterialTheme.colorScheme.primary
                                    } else {
                                        MaterialTheme.colorScheme.onSurface
                                    },
                                )
                                if (!already) {
                                    Button(onClick = { takenIds = takenIds + dose.id }) {
                                        Text("Ya la tomé")
                                    }
                                } else {
                                    Text("Registrada", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
