package mx.unach.dosys.ui.home

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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Medication
import androidx.compose.material.icons.filled.QrCode
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Science
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import mx.unach.dosys.data.mock.MockData
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.ui.format.formatClinicalDateTime

/**
 * Pantalla de inicio del paciente: resumen de su próxima cita,
 * tratamiento activo y accesos rápidos a su información (solo lectura).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onLogout: () -> Unit,
    onOpenRecord: () -> Unit,
    onOpenStudies: () -> Unit,
    onOpenPrescriptions: () -> Unit,
    onOpenQr: () -> Unit,
    onOpenAppointments: () -> Unit,
    onOpenCheckIn: () -> Unit,
    onOpenSecurity: () -> Unit,
    onOpenDocuments: () -> Unit,
    viewModel: HomeViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Hola,", style = MaterialTheme.typography.labelMedium)
                        Text(
                            text = state.patientName,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.logout(onLogout) }) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ExitToApp,
                            contentDescription = "Cerrar sesión",
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                    actionIconContentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                ),
            )
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
                NextAppointmentCard(
                    appointment = state.nextAppointment,
                    isLoading = state.isLoading,
                    onClick = onOpenAppointments,
                )
            }
            state.error?.let { error ->
                item {
                    Text(
                        text = error,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
            item { ActiveTreatmentCard(onClick = onOpenPrescriptions) }
            item {
                Text(
                    text = "Mi información",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    QuickAccess(Icons.Filled.Description, "Expediente", Modifier.weight(1f), onOpenRecord)
                    QuickAccess(Icons.Filled.Science, "Estudios", Modifier.weight(1f), onOpenStudies)
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    QuickAccess(Icons.Filled.Medication, "Recetas", Modifier.weight(1f), onOpenPrescriptions)
                    QuickAccess(Icons.Filled.QrCode, "Mi QR", Modifier.weight(1f), onOpenQr)
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    QuickAccess(Icons.Filled.QrCodeScanner, "Check-in con QR", Modifier.weight(1f), onOpenCheckIn)
                    QuickAccess(Icons.Filled.Shield, "Mi seguridad", Modifier.weight(1f), onOpenSecurity)
                }
            }
            item {
                QuickAccess(Icons.Filled.FolderOpen, "Mis documentos", Modifier.fillMaxWidth(), onOpenDocuments)
            }
            item {
                Text(
                    text = "Solo lectura: tu información clínica únicamente puede modificarla tu médico.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
        }
    }
}

@Composable
private fun NextAppointmentCard(
    appointment: PatientAppointment?,
    isLoading: Boolean,
    onClick: () -> Unit,
) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Filled.CalendarMonth,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                )
                Spacer(Modifier.size(8.dp))
                Text(
                    text = "Próxima cita",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            Spacer(Modifier.height(8.dp))
            when {
                isLoading -> Text(
                    text = "Cargando cita asignada por el hospital…",
                    style = MaterialTheme.typography.bodyMedium,
                )
                appointment == null -> Text(
                    text = "No tienes citas próximas.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                else -> {
                    Text(appointment.specialty, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(appointment.doctorName ?: "Personal hospitalario", style = MaterialTheme.typography.bodyMedium)
                    Text(
                        text = formatClinicalDateTime(appointment.scheduledAt),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Text(
                text = "Toca para ver todas tus citas",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
    }
}

@Composable
private fun ActiveTreatmentCard(onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(
                text = "Tratamiento activo",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.height(8.dp))
            MockData.prescriptions.take(2).forEach { prescription ->
                Text(prescription.medication, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                Text(
                    text = prescription.dose,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(6.dp))
                LinearProgressIndicator(
                    progress = { prescription.taken.toFloat() / prescription.total.toFloat() },
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    text = "${prescription.taken} de ${prescription.total} tomas",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(12.dp))
            }
            Text(
                text = "Toca para marcar tomas",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

@Composable
private fun QuickAccess(
    icon: ImageVector,
    label: String,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    Card(
        onClick = onClick,
        modifier = modifier.height(96.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Icon(imageVector = icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(8.dp))
            Text(label, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
        }
    }
}
