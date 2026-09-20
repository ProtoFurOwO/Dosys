package mx.unach.dosys.ui.studies

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
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
import mx.unach.dosys.ui.components.StatusChip
import mx.unach.dosys.ui.components.studyStatusColor
import mx.unach.dosys.ui.components.studyStatusLabel

/**
 * Bandeja de estudios del paciente (el flujo tipo IMSS, visto desde su lado).
 * Estados: Solicitado → En proceso → Listo.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun StudiesScreen(
    onBack: () -> Unit,
    onOpenStudy: (Int) -> Unit,
) {
    var filter by remember { mutableStateOf<MockData.StudyStatus?>(null) }
    val visible = remember(filter) {
        if (filter == null) MockData.studies else MockData.studies.filter { it.status == filter }
    }

    ScreenScaffold(title = "Mis estudios", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Text(
                    text = "Así viaja una solicitud: el médico la genera, llega al laboratorio o imagenología y, cuando hay resultado, aparece aquí.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            item {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(selected = filter == null, onClick = { filter = null }, label = { Text("Todos") })
                    FilterChip(
                        selected = filter == MockData.StudyStatus.SOLICITADO,
                        onClick = { filter = MockData.StudyStatus.SOLICITADO },
                        label = { Text("Solicitado") },
                    )
                    FilterChip(
                        selected = filter == MockData.StudyStatus.EN_PROCESO,
                        onClick = { filter = MockData.StudyStatus.EN_PROCESO },
                        label = { Text("En proceso") },
                    )
                    FilterChip(
                        selected = filter == MockData.StudyStatus.LISTO,
                        onClick = { filter = MockData.StudyStatus.LISTO },
                        label = { Text("Listo") },
                    )
                }
            }
            items(visible, key = { it.id }) { study ->
                Card(
                    onClick = { onOpenStudy(study.id) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Column(Modifier.padding(16.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(study.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                            StatusChip(studyStatusLabel(study.status), studyStatusColor(study.status))
                        }
                        Spacer(Modifier.height(4.dp))
                        Text("${study.area} · solicitado por ${study.requestedBy}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(study.requestedAt, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (study.status == MockData.StudyStatus.LISTO && study.resultSummary != null) {
                            Spacer(Modifier.height(8.dp))
                            Text(study.resultSummary, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
        }
    }
}
