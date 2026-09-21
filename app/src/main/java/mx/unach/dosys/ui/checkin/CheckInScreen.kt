package mx.unach.dosys.ui.checkin

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.Uri
import android.os.Bundle
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewmodel.compose.viewModel
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import mx.unach.dosys.R
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.components.StatusChip
import mx.unach.dosys.ui.components.appointmentStatusColor
import mx.unach.dosys.ui.components.appointmentStatusLabel
import mx.unach.dosys.ui.format.formatClinicalDateTime
import org.osmdroid.config.Configuration
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.BoundingBox
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Marker
import kotlin.coroutines.resume

/** Sanatorio de Tuxtla Gutiérrez usado en la demostración académica. */
private const val HOSPITAL_LAT = 16.755731
private const val HOSPITAL_LON = -93.136586

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
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            StatusChip(
                                text = appointmentStatusLabel(appointment.status),
                                color = appointmentStatusColor(appointment.status),
                            )
                            appointment.checkedInAt?.let { checkedIn ->
                                StatusChip(
                                    text = "Llegaste ${formatClinicalDateTime(checkedIn)}",
                                    color = MaterialTheme.colorScheme.primary,
                                )
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
    var userLocation by remember { mutableStateOf<Location?>(null) }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { result ->
        granted = result.values.any { it }
    }

    LaunchedEffect(granted) {
        if (granted && userLocation == null && !loading) {
            loading = true
            userLocation = readCurrentLocation(context)
            loading = false
        }
    }

    val distance = userLocation?.let(::distanceToHospital)

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Filled.LocationOn,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.size(8.dp))
                Text(
                    text = "Cómo llegar al hospital",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            Spacer(Modifier.height(12.dp))

            HospitalMap(
                userLocation = userLocation,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(220.dp)
                    .clip(RoundedCornerShape(10.dp)),
            )

            Spacer(Modifier.height(10.dp))
            when {
                !granted -> {
                    Text(
                        text = "Activa la ubicación para verte en el mapa y saber qué tan cerca estás.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Spacer(Modifier.height(10.dp))
                    OutlinedButton(
                        onClick = {
                            permissionLauncher.launch(
                                arrayOf(
                                    Manifest.permission.ACCESS_FINE_LOCATION,
                                    Manifest.permission.ACCESS_COARSE_LOCATION,
                                )
                            )
                        },
                    ) {
                        Text("Permitir ubicación")
                    }
                }
                loading -> Text("Buscando tu ubicación…", style = MaterialTheme.typography.bodyMedium)
                distance == null -> Text(
                    text = "Sin señal de GPS por ahora. El mapa muestra el hospital; puedes confirmar tu llegada de todos modos.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                distance < 120f -> Text(
                    text = "Estás en el hospital (a ${distance.toInt()} m).",
                    style = MaterialTheme.typography.bodyMedium,
                )
                else -> Text(
                    text = "Estás a ${formatDistance(distance)} del hospital.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            Spacer(Modifier.height(4.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(
                    onClick = { openInMapsApp(context) },
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),
                ) {
                    Text("Abrir en la app de mapas")
                }
                Spacer(Modifier.weight(1f))
                Text(
                    text = "© OpenStreetMap",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun HospitalMap(
    userLocation: Location?,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current

    val mapView = remember {
        Configuration.getInstance().load(
            context,
            context.getSharedPreferences("osmdroid", Context.MODE_PRIVATE),
        )
        Configuration.getInstance().userAgentValue = context.packageName

        MapView(context).apply {
            setTileSource(TileSourceFactory.MAPNIK)
            setMultiTouchControls(true)
            controller.setZoom(15.0)
            controller.setCenter(GeoPoint(HOSPITAL_LAT, HOSPITAL_LON))
            overlays.add(hospitalMarker(context, this))
        }
    }

    val userMarker = remember(mapView) {
        Marker(mapView).apply {
            title = "Tu ubicación"
            icon = ContextCompat.getDrawable(context, R.drawable.ic_map_user)
            setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
        }
    }

    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner, mapView) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> mapView.onResume()
                Lifecycle.Event.ON_PAUSE -> mapView.onPause()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            mapView.onDetach()
        }
    }

    AndroidView(
        factory = { mapView },
        modifier = modifier,
        update = { view ->
            if (userLocation != null) {
                if (!view.overlays.contains(userMarker)) {
                    view.overlays.add(userMarker)
                }
                userMarker.position = GeoPoint(userLocation.latitude, userLocation.longitude)

                val separation = distanceToHospital(userLocation)
                if (separation < 150f) {
                    view.controller.setZoom(17.0)
                    view.controller.setCenter(userMarker.position)
                } else {
                    view.zoomToBoundingBox(
                        BoundingBox.fromGeoPoints(
                            listOf(GeoPoint(HOSPITAL_LAT, HOSPITAL_LON), userMarker.position)
                        ),
                        true,
                        110,
                    )
                }
            }
            view.invalidate()
        },
    )
}

private fun hospitalMarker(context: Context, map: MapView): Marker = Marker(map).apply {
    position = GeoPoint(HOSPITAL_LAT, HOSPITAL_LON)
    title = "Hospital General"
    icon = ContextCompat.getDrawable(context, R.drawable.ic_map_hospital)
    setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM)
}

private fun openInMapsApp(context: Context) {
    val uri = Uri.parse("geo:$HOSPITAL_LAT,$HOSPITAL_LON?q=$HOSPITAL_LAT,$HOSPITAL_LON(Hospital+General)")
    runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, uri)) }
}

private fun hasLocationPermission(context: Context): Boolean =
    ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED

private fun distanceToHospital(location: Location): Float {
    val results = FloatArray(1)
    Location.distanceBetween(location.latitude, location.longitude, HOSPITAL_LAT, HOSPITAL_LON, results)
    return results[0]
}

private fun formatDistance(meters: Float): String =
    if (meters < 1000f) "${meters.toInt()} m" else String.format("%.1f km", meters / 1000f)

private suspend fun readCurrentLocation(context: Context): Location? {
    val manager = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return null
    return try {
        manager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
            ?: manager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            ?: awaitSingleLocation(manager)
    } catch (security: SecurityException) {
        null
    }
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
