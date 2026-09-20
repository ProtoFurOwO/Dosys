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
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import mx.unach.dosys.data.mock.MockData
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.components.StatusChip
import mx.unach.dosys.ui.components.studyStatusColor
import mx.unach.dosys.ui.components.studyStatusLabel

@Composable
fun StudyDetailScreen(studyId: Int, onBack: () -> Unit) {
    val study = MockData.studies.firstOrNull { it.id == studyId }

    ScreenScaffold(title = study?.name ?: "Estudio", onBack = onBack) { padding ->
        if (study == null) {
            Text("No se encontró el estudio.", modifier = Modifier.padding(padding).padding(16.dp))
            return@ScreenScaffold
        }

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
                        StatusChip(studyStatusLabel(study.status), studyStatusColor(study.status))
                        Spacer(Modifier.height(12.dp))
                        Info("Área", study.area)
                        Info("Solicitó", study.requestedBy)
                        Info("Fecha de solicitud", study.requestedAt)
                        study.resultDate?.let { Info("Resultado el", it) }
                    }
                }
            }
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text("Resultado", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.height(8.dp))
                        when (study.status) {
                            MockData.StudyStatus.SOLICITADO ->
                                Text("El médico ya envió la solicitud. Aún no hay muestra ni imagen.")
                            MockData.StudyStatus.EN_PROCESO ->
                                Text("El área correspondiente ya recibió tu solicitud y está procesándola.")
                            MockData.StudyStatus.LISTO -> {
                                Text(study.resultSummary.orEmpty(), style = MaterialTheme.typography.bodyMedium)
                                if (study.findings.isNotEmpty()) {
                                    Spacer(Modifier.height(12.dp))
                                    study.findings.forEachIndexed { index, (label, value) ->
                                        Row(
                                            modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                        ) {
                                            Text(label, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                                            Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                                        }
                                        if (index < study.findings.lastIndex) HorizontalDivider()
                                    }
                                }
                            }
                        }
                    }
                }
            }
            item {
                Text(
                    text = "No puedes modificar ni ocultar un resultado. Si tienes dudas, consúltalas con tu médico.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun Info(label: String, value: String) {
    Column(Modifier.padding(vertical = 2.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}
