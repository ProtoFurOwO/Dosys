package mx.unach.dosys.ui.record

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import mx.unach.dosys.data.model.PatientConsultation
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.format.formatClinicalDateTime
import java.util.Locale

/**
 * Detalle de una consulta con estructura SOAP.
 *
 * S — Subjetivo: motivo de la consulta.
 * O — Objetivo: signos vitales y exploración física.
 * A — Análisis: diagnóstico.
 * P — Plan: notas e indicaciones.
 */
@Composable
fun ConsultationDetailScreen(
    consultationId: Int,
    onBack: () -> Unit,
    viewModel: ConsultationDetailViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(consultationId) {
        viewModel.load(consultationId)
    }

    ScreenScaffold(title = "Detalle de consulta", onBack = onBack) { padding ->
        ConsultationDetailContent(
            state = state,
            modifier = Modifier.padding(padding),
        )
    }
}

@Composable
private fun ConsultationDetailContent(
    state: ConsultationDetailUiState,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (state.isLoading) {
            item { CircularProgressIndicator() }
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
        state.consultation?.let { consultation ->
            item { ConsultationHeader(consultation) }
            item {
                SoapSection(
                    letter = "S",
                    title = "Subjetivo",
                    hasData = !consultation.reason.isNullOrBlank(),
                ) {
                    Text(
                        text = consultation.reason.orEmpty(),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
            item {
                val vitals = consultation.vitalSigns()
                val hasExam = !consultation.physicalExam.isNullOrBlank()
                SoapSection(
                    letter = "O",
                    title = "Objetivo",
                    hasData = vitals.isNotEmpty() || hasExam,
                ) {
                    if (vitals.isNotEmpty()) {
                        VitalSignsGrid(vitals)
                    }
                    if (hasExam) {
                        if (vitals.isNotEmpty()) Spacer(Modifier.height(12.dp))
                        Text(
                            text = "Exploración física",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            text = consultation.physicalExam.orEmpty(),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
            item {
                SoapSection(
                    letter = "A",
                    title = "Análisis",
                    hasData = !consultation.diagnosis.isNullOrBlank(),
                ) {
                    Text(
                        text = consultation.diagnosis.orEmpty(),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
            item {
                SoapSection(
                    letter = "P",
                    title = "Plan",
                    hasData = !consultation.notes.isNullOrBlank(),
                ) {
                    Text(
                        text = consultation.notes.orEmpty(),
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
private fun ConsultationHeader(consultation: PatientConsultation) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(
                text = formatClinicalDateTime(consultation.createdAt),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            consultation.updatedAt?.let { updated ->
                Text(
                    text = "Corregida el ${formatClinicalDateTime(updated)}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(4.dp))
            Text(
                text = consultation.specialty,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = consultation.doctorName,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun SoapSection(
    letter: String,
    title: String,
    hasData: Boolean,
    content: @Composable ColumnScope.() -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    color = MaterialTheme.colorScheme.primaryContainer,
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                    shape = RoundedCornerShape(8.dp),
                ) {
                    Text(
                        text = letter,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                    )
                }
                Spacer(Modifier.width(8.dp))
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                )
            }
            Spacer(Modifier.height(10.dp))
            if (hasData) {
                content()
            } else {
                Text(
                    text = "Sin registrar",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun VitalSignsGrid(vitals: List<VitalSign>) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        vitals.chunked(2).forEach { row ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                row.forEach { vital ->
                    VitalItem(vital = vital, modifier = Modifier.weight(1f))
                }
                if (row.size == 1) {
                    Spacer(Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
private fun VitalItem(vital: VitalSign, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f),
        shape = RoundedCornerShape(10.dp),
    ) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            Text(
                text = vital.label,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = vital.value,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = vital.unit,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private data class VitalSign(
    val label: String,
    val value: String,
    val unit: String,
)

private fun PatientConsultation.vitalSigns(): List<VitalSign> = buildList {
    bloodPressure?.takeIf { it.isNotBlank() }?.let {
        add(VitalSign("TA", it, "mmHg"))
    }
    heartRate?.let { add(VitalSign("FC", it.toString(), "lpm")) }
    respiratoryRate?.let { add(VitalSign("FR", it.toString(), "rpm")) }
    temperatureC?.let { add(VitalSign("Temp", formatDecimal(it), "°C")) }
    oxygenSaturation?.let { add(VitalSign("SpO₂", it.toString(), "%")) }
    weightKg?.let { add(VitalSign("Peso", formatDecimal(it), "kg")) }
    heightCm?.let { add(VitalSign("Talla", formatDecimal(it), "cm")) }
    ClinicalMetrics.bmi(weightKg, heightCm)?.let {
        add(VitalSign("IMC", it.formatted, "kg/m² · ${it.category.label}"))
    }
}

private fun formatDecimal(value: Double): String =
    if (value % 1.0 == 0.0) {
        value.toInt().toString()
    } else {
        String.format(Locale.US, "%.1f", value)
    }
