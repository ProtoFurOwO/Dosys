package mx.unach.dosys.ui.appointments

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.components.StatusChip
import mx.unach.dosys.ui.components.appointmentStatusColor
import mx.unach.dosys.ui.components.appointmentStatusLabel
import mx.unach.dosys.ui.format.formatClinicalDateTime

@Composable
fun AppointmentsScreen(
    onBack: () -> Unit,
    onOpenCheckIn: () -> Unit,
    viewModel: AppointmentsViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    AppointmentsContent(state = state, onBack = onBack, onOpenCheckIn = onOpenCheckIn)
}

@Composable
private fun AppointmentsContent(
    state: AppointmentsUiState,
    onBack: () -> Unit,
    onOpenCheckIn: () -> Unit,
) {
    ScreenScaffold(title = "Mis citas", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Button(onClick = onOpenCheckIn, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Filled.QrCodeScanner, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.size(8.dp))
                    Text("Confirmar llegada con QR")
                }
            }
            item {
                Text(
                    text = "El médico o recepción agenda la cita. Solo puedes confirmar tu llegada dentro de la ventana de la cita.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
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

            item {
                Text(
                    text = "Próximas (${state.upcoming.size})",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
            if (!state.isLoading && state.error == null && state.upcoming.isEmpty()) {
                item {
                    Text(
                        text = "No tienes citas próximas. Las citas pasadas quedan en tu historial.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            items(state.upcoming, key = { it.id }) { appointment ->
                AppointmentCard(appointment)
            }

            if (state.past.isNotEmpty()) {
                item {
                    Text(
                        text = "Historial (${state.past.size})",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(top = 12.dp),
                    )
                }
                items(state.past, key = { it.id }) { appointment ->
                    AppointmentCard(appointment)
                }
            }
        }
    }
}

@Composable
private fun AppointmentCard(appointment: PatientAppointment) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    appointment.specialty,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.weight(1f),
                )
                StatusChip(appointmentStatusLabel(appointment.status), appointmentStatusColor(appointment.status))
            }
            Spacer(Modifier.height(4.dp))
            Text(appointment.doctorName ?: "Personal hospitalario", style = MaterialTheme.typography.bodyMedium)
            Text(formatClinicalDateTime(appointment.scheduledAt), style = MaterialTheme.typography.bodyMedium)
            Text(
                appointment.location,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            appointment.notes?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, style = MaterialTheme.typography.bodySmall)
            }
            when {
                appointment.checkedInAt != null -> {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = "Llegada confirmada el ${formatClinicalDateTime(appointment.checkedInAt)}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                appointment.isUpcoming && appointment.checkinAvailable -> {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = "Check-in abierto",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                appointment.isUpcoming -> {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = checkinHint(appointment),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

private fun checkinHint(appointment: PatientAppointment): String = when (appointment.checkinReason) {
    "too_early" -> "El check-in abre 2 horas antes de la cita."
    "closed" -> "El check-in de esta cita ya cerró."
    "already_checked_in" -> "Tu llegada ya estaba confirmada."
    "attended" -> "Esta cita ya fue atendida."
    "cancelled" -> "Esta cita fue cancelada."
    else -> "Check-in disponible cerca de la hora de la cita."
}
