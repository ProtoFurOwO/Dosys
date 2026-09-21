package mx.unach.dosys.ui.checkin

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.components.StatusChip
import mx.unach.dosys.ui.components.appointmentStatusColor
import mx.unach.dosys.ui.components.appointmentStatusLabel
import mx.unach.dosys.ui.format.formatClinicalDateTime
import kotlin.coroutines.resume

/** Coordenadas del Hospital General usadas en la demostración académica. */
private const val HOSPITAL_LAT = 16.7569
private const val HOSPITAL_LON = -93.1292

@Composable
fun CheckInScreen(
    onBack: () -> Unit,
    viewModel: CheckInViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        result.contents?.let(viewModel::onCodeScanned)
    }

    ScreenScaffold(title = "Check-in", onBack = onBack) { padding ->
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
                        Text(
                            text = "Confirma tu llegada",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                        )
                        Spacer(Modifier.height(6.dp))
                        Text(
                            text = "Escanea el código QR que recepción muestra en pantalla. Si no puedes escanear, escribe el código de respaldo.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(14.dp))
                        Button(
                            onClick = {
                                scanner.launch(
                                    ScanOptions().apply {
                                        setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                                        setPrompt("Apunta al código de recepción")
                                        setBeepEnabled(false)
                                        setOrientationLocked(false)
                                    }
                                )
                            },
                            enabled = !state.isSubmitting,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Icon(Icons.Filled.QrCodeScanner, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.size(8.dp))
                            Text("Abrir cámara")
                        }
                        Spacer(Modifier.height(12.dp))
                        OutlinedTextField(
                            value = state.codeInput,
                            onValueChange = viewModel::onCodeChange,
                            label = { Text("Código de respaldo") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Spacer(Modifier.height(8.dp))
                        OutlinedButton(
                            onClick = viewModel::submitManualCode,
                            enabled = !state.isSubmitting && state.codeInput.isNotBlank(),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("Confirmar con el código")
                        }
                    }
                }
            }

            item { LocationCard() }

            state.error?.let { message ->
                item {
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }

            state.confirmed?.let { appointment ->
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
                    ) {
                        Column(Modifier.padding(16.dp)) {
                            Text(
                                text = "Llegada confirmada",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                            )
                            Spacer(Modifier.height(6.dp))
                            Text(appointment.specialty, style = MaterialTheme.typography.bodyMedium)
                            Text(
                                text = "${appointment.location} · ${appointment.checkedInAt?.let(::formatClinicalDateTime) ?: ""}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }

            item {
                Text(
                    text = "Mis citas",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }

            items(state.appointments, key = { it.id }) { appointment ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text(
                            text = appointment.specialty,
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            text = formatClinicalDateTime(appointment.scheduledAt),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(8.dp))
                        androidx.compose.foundation.layout.Row(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            StatusChip(
                                text = appointmentStatusLabel(appointment.status),
                                color = appointmentStatusColor(appointment.status),
                            )
                            appointment.checkedInAt?.let { checkedIn ->
                                StatusChip(text = "Llegaste ${formatClinicalDateTime(checkedIn)}", color = MaterialTheme.colorScheme.primary)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun LocationCard() {
    val context = LocalContext.current
    var granted by remember { mutableStateOf(hasLocationPermission(context)) }
    var loading by remember { mutableStateOf(false) }
    var distance by remember { mutableStateOf<Float?>(null) }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { result ->
        granted = result.values.any { it }
    }

    LaunchedEffect(granted) {
        if (granted && distance == null && !loading) {
            loading = true
            distance = readDistanceMeters(context)
            loading = false
        }
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            androidx.compose.foundation.layout.Row(
                verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
            ) {
                Icon(
                    imageVector = Icons.Filled.LocationOn,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.size(8.dp))
                Text(
                    text = "Ubicación del hospital",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            Spacer(Modifier.height(8.dp))
            when {
                !granted -> {
                    Text(
                        text = "Activa la ubicación para ver qué tan cerca estás del hospital.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Spacer(Modifier.height(10.dp))
                    OutlinedButton(
                        onClick = {
                            permissionLauncher.launch(
                                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
                            )
                        },
                    ) {
                        Text("Permitir ubicación")
                    }
                }
                loading -> Text("Buscando tu ubicación…", style = MaterialTheme.typography.bodyMedium)
                distance == null -> Text(
                    text = "Sin señal de GPS por ahora. Puedes confirmar tu llegada de todos modos.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                else -> Text(
                    text = "Estás a ${formatDistance(distance!!)} del Hospital General.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

private fun hasLocationPermission(context: Context): Boolean =
    ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED

private fun formatDistance(meters: Float): String =
    if (meters < 1000f) "${meters.toInt()} m" else String.format("%.1f km", meters / 1000f)

private suspend fun readDistanceMeters(context: Context): Float? {
    val manager = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return null
    val location = try {
        manager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
            ?: manager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            ?: awaitSingleLocation(manager)
    } catch (security: SecurityException) {
        null
    }

    if (location == null) return null
    val results = FloatArray(1)
    Location.distanceBetween(location.latitude, location.longitude, HOSPITAL_LAT, HOSPITAL_LON, results)
    return results[0]
}

@Suppress("DEPRECATION")
private suspend fun awaitSingleLocation(manager: LocationManager): Location? = withTimeoutOrNull(10_000) {
    suspendCancellableCoroutine { continuation ->
        val listener = object : LocationListener {
            override fun onLocationChanged(location: Location) {
                manager.removeUpdates(this)
                if (continuation.isActive) continuation.resume(location)
            }

            override fun onProviderEnabled(provider: String) = Unit

            override fun onProviderDisabled(provider: String) = Unit

            @Deprecated("Deprecated in Java")
            override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit
        }

        try {
            manager.requestSingleUpdate(LocationManager.GPS_PROVIDER, listener, Looper.getMainLooper())
        } catch (security: SecurityException) {
            if (continuation.isActive) continuation.resume(null)
        }

        continuation.invokeOnCancellation { manager.removeUpdates(listener) }
    }
}
