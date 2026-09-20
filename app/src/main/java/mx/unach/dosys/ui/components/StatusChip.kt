package mx.unach.dosys.ui.components

import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import mx.unach.dosys.data.mock.MockData

@Composable
fun StatusChip(text: String, color: Color, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        color = color.copy(alpha = 0.15f),
        contentColor = color,
        shape = RoundedCornerShape(50),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
        )
    }
}

fun studyStatusLabel(status: MockData.StudyStatus): String = when (status) {
    MockData.StudyStatus.SOLICITADO -> "Solicitado"
    MockData.StudyStatus.EN_PROCESO -> "En proceso"
    MockData.StudyStatus.LISTO -> "Listo"
}

fun studyStatusColor(status: MockData.StudyStatus): Color = when (status) {
    MockData.StudyStatus.SOLICITADO -> Color(0xFF6B7280)
    MockData.StudyStatus.EN_PROCESO -> Color(0xFFB45309)
    MockData.StudyStatus.LISTO -> Color(0xFF13653F)
}

fun appointmentStatusLabel(status: MockData.AppointmentStatus): String = when (status) {
    MockData.AppointmentStatus.AGENDADA -> "Agendada"
    MockData.AppointmentStatus.CONFIRMADA -> "Confirmada"
    MockData.AppointmentStatus.ATENDIDA -> "Atendida"
    MockData.AppointmentStatus.CANCELADA -> "Cancelada"
}

fun appointmentStatusColor(status: MockData.AppointmentStatus): Color = when (status) {
    MockData.AppointmentStatus.AGENDADA -> Color(0xFFB45309)
    MockData.AppointmentStatus.CONFIRMADA -> Color(0xFF13653F)
    MockData.AppointmentStatus.ATENDIDA -> Color(0xFF6B7280)
    MockData.AppointmentStatus.CANCELADA -> Color(0xFFB3261E)
}
