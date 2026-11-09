package mx.unach.dosys.ui.appointments

import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import mx.unach.dosys.data.model.AppointmentAvailabilitySlot
import mx.unach.dosys.data.model.DoctorOption
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.format.formatClinicalDateTime
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

private val requestDateFormatter =
    DateTimeFormatter.ofPattern("EEE d MMM", Locale.forLanguageTag("es-MX"))

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppointmentRequestScreen(
    onBack: () -> Unit,
    onDone: () -> Unit,
    viewModel: AppointmentRequestViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    ScreenScaffold(
        title = "Solicitar cita",
        onBack = {
            if (viewModel.goBack()) onBack()
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Text(
                    text = stepLabel(state),
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            state.error?.let { error ->
                item {
                    ErrorBanner(error)
                }
            }

            when (state.step) {
                AppointmentRequestStep.DOCTOR -> {
                    item {
                        Text(
                            text = "Elige al médico",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    if (state.isLoadingDoctors) {
                        item { CircularProgressIndicator() }
                    }
                    if (!state.isLoadingDoctors && state.doctors.isEmpty()) {
                        item {
                            Text(
                                text = "No hay médicos disponibles para solicitar cita.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        if (state.error != null) {
                            item {
                                OutlinedButton(
                                    onClick = viewModel::retryDoctors,
                                    modifier = Modifier.fillMaxWidth(),
                                ) {
                                    Text("Reintentar")
                                }
                            }
                        }
                    }
                    items(state.doctors, key = { it.id }) { doctor ->
                        DoctorCard(doctor = doctor, onClick = { viewModel.selectDoctor(doctor) })
                    }
                }

                AppointmentRequestStep.DATE -> {
                    item { SelectedDoctorSummary(state.selectedDoctor) }
                    item {
                        Text(
                            text = "Elige la fecha",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    item {
                        DateChips(
                            selected = state.selectedDate,
                            onSelect = viewModel::selectDate,
                        )
                    }
                    item {
                        Text(
                            text = "Se muestran los próximos 14 días.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }

                AppointmentRequestStep.SLOTS -> {
                    item { RequestSummary(state) }
                    item {
                        Text(
                            text = "Elige un horario disponible",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    if (state.isLoadingSlots) {
                        item { CircularProgressIndicator() }
                    }
                    if (!state.isLoadingSlots && state.slots.isEmpty()) {
                        item {
                            Text(
                                text = "No hay horarios para este día. Elige otra fecha.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    item {
                        SlotGrid(
                            slots = state.slots,
                            onSelect = viewModel::selectSlot,
                        )
                    }
                    item {
                        OutlinedButton(
                            onClick = viewModel::reloadSlots,
                            enabled = !state.isLoadingSlots,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("Actualizar horarios")
                        }
                    }
                }

                AppointmentRequestStep.REASON -> {
                    item { RequestSummary(state) }
                    item {
                        Text(
                            text = "Motivo de la consulta",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    item {
                        OutlinedTextField(
                            value = state.reason,
                            onValueChange = viewModel::updateReason,
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 3,
                            maxLines = 5,
                            placeholder = { Text("Ej. Dolor lumbar de una semana") },
                            supportingText = {
                                Text("${state.reason.length}/300")
                            },
                        )
                    }
                    item {
                        Button(
                            onClick = viewModel::submit,
                            enabled = !state.isSubmitting && state.reason.isNotBlank(),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            if (state.isSubmitting) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(18.dp),
                                    strokeWidth = 2.dp,
                                    color = MaterialTheme.colorScheme.onPrimary,
                                )
                                Spacer(Modifier.width(8.dp))
                            }
                            Text(if (state.isSubmitting) "Enviando…" else "Enviar solicitud")
                        }
                    }
                }

                AppointmentRequestStep.SUCCESS -> {
                    item {
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(
                                modifier = Modifier.padding(20.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                            ) {
                                Icon(
                                    imageVector = Icons.Filled.CheckCircle,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.size(48.dp),
                                )
                                Spacer(Modifier.height(12.dp))
                                Text(
                                    text = "Solicitud enviada",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                )
                                Spacer(Modifier.height(6.dp))
                                Text(
                                    text = "Quedó pendiente de confirmación por recepción.",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                                state.created?.let { created ->
                                    Spacer(Modifier.height(12.dp))
                                    Text(
                                        text = created.specialty,
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.Bold,
                                    )
                                    Text(
                                        text = formatClinicalDateTime(created.scheduledAt),
                                        style = MaterialTheme.typography.bodyMedium,
                                    )
                                }
                                Spacer(Modifier.height(20.dp))
                                Button(
                                    onClick = onDone,
                                    modifier = Modifier.fillMaxWidth(),
                                ) {
                                    Text("Volver a Mis citas")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun stepLabel(state: AppointmentRequestUiState): String = when (state.step) {
    AppointmentRequestStep.DOCTOR -> "Paso 1 de 4 · Médico"
    AppointmentRequestStep.DATE -> "Paso 2 de 4 · Fecha"
    AppointmentRequestStep.SLOTS -> "Paso 3 de 4 · Horario"
    AppointmentRequestStep.REASON -> "Paso 4 de 4 · Motivo"
    AppointmentRequestStep.SUCCESS -> "Solicitud enviada"
}

@Composable
private fun DoctorCard(doctor: DoctorOption, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = Icons.Filled.Person,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    text = doctor.fullName,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = doctor.specialty,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                text = "Elegir",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

@Composable
private fun SelectedDoctorSummary(doctor: DoctorOption?) {
    doctor ?: return
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = Icons.Filled.Person,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.width(10.dp))
            Column {
                Text(
                    text = doctor.fullName,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = doctor.specialty,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun RequestSummary(state: AppointmentRequestUiState) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Text(
                text = state.selectedDoctor?.fullName ?: "Médico",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = listOfNotNull(
                    state.selectedDoctor?.specialty,
                    state.selectedDate?.format(requestDateFormatter),
                    state.selectedSlot?.time,
                ).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DateChips(
    selected: LocalDate?,
    onSelect: (LocalDate) -> Unit,
) {
    val today = LocalDate.now()
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        (0 until 14).forEach { offset ->
            val date = today.plusDays(offset.toLong())
            FilterChip(
                selected = selected == date,
                onClick = { onSelect(date) },
                label = {
                    Text(
                        when (offset) {
                            0 -> "Hoy"
                            1 -> "Mañana"
                            else -> date.format(requestDateFormatter)
                        }
                    )
                },
            )
        }
    }
}

@Composable
private fun SlotGrid(
    slots: List<AppointmentAvailabilitySlot>,
    onSelect: (AppointmentAvailabilitySlot) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        slots.chunked(3).forEach { row ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                row.forEach { slot ->
                    if (slot.available) {
                        Button(
                            onClick = { onSelect(slot) },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text(slot.time)
                        }
                    } else {
                        OutlinedButton(
                            onClick = {},
                            enabled = false,
                            modifier = Modifier.weight(1f),
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(slot.time)
                                Text(
                                    text = "Ocupado",
                                    style = MaterialTheme.typography.labelSmall,
                                )
                            }
                        }
                    }
                }
                repeat(3 - row.size) {
                    Spacer(Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
private fun ErrorBanner(message: String) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        contentColor = MaterialTheme.colorScheme.onErrorContainer,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            text = message,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(14.dp),
        )
    }
}
