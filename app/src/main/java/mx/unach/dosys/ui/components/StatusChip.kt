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
import mx.unach.dosys.data.model.AppointmentStatus

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

fun studyStatusLabel(status: String): String = when (status) {
    "completed" -> "Listo"
    "in_progress" -> "En proceso"
    "cancelled" -> "Cancelado"
    else -> "Solicitado"
}

fun studyStatusColor(status: String): Color = when (status) {
    "completed" -> Color(0xFF13653F)
    "in_progress" -> Color(0xFFB45309)
    "cancelled" -> Color(0xFFB3261E)
    else -> Color(0xFF6B7280)
}

fun appointmentStatusLabel(status: AppointmentStatus): String = when (status) {
    AppointmentStatus.SCHEDULED -> "Agendada"
    AppointmentStatus.CONFIRMED -> "Confirmada"
    AppointmentStatus.ATTENDED -> "Atendida"
    AppointmentStatus.CANCELLED -> "Cancelada"
}

fun appointmentStatusColor(status: AppointmentStatus): Color = when (status) {
    AppointmentStatus.SCHEDULED -> Color(0xFFB45309)
    AppointmentStatus.CONFIRMED -> Color(0xFF13653F)
    AppointmentStatus.ATTENDED -> Color(0xFF6B7280)
    AppointmentStatus.CANCELLED -> Color(0xFFB3261E)
}
