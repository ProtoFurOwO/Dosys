package mx.unach.dosys.ui.transfer

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.view.WindowManager
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewmodel.compose.viewModel
import mx.unach.dosys.ui.components.BiometricGate
import mx.unach.dosys.ui.components.ScreenScaffold
import mx.unach.dosys.ui.components.StatusChip
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter

/**
 * Lado A: el paciente confirma con huella y autoriza (o rechaza) la sesión que
 * intenta abrirse en otro teléfono. El código nunca sale de este dispositivo.
 */
@Composable
fun TransferApprovalScreen(
    onBack: () -> Unit,
    onSessionTransferred: () -> Unit,
    viewModel: TransferApprovalViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(state.sessionTransferred) {
        if (state.sessionTransferred) onSessionTransferred()
    }

    if (!state.unlocked) {
        ScreenScaffold(title = "Solicitud de acceso", onBack = onBack) { padding ->
            BiometricGate(
                onUnlocked = viewModel::unlock,
                modifier = Modifier.padding(padding),
                title = "Confirma que eres tú",
                description = "Usa tu huella para ver el código con el que autorizas el nuevo dispositivo.",
                allowFallback = false,
            )
        }
        return
    }

    // El código no debe aparecer en capturas ni en la vista de recientes.
    SecureWindow(enabled = state.code != null)
    OnStopEffect(onStop = viewModel::onBackground)
    // Al salir de la pantalla (aunque sea dentro de la misma Activity) el
    // código se destruye y la solicitud se reporta como expirada.
    DisposableEffect(Unit) {
        onDispose { viewModel.onBackground() }
    }

    ScreenScaffold(title = "Solicitud de acceso", onBack = onBack) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp, vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            when {
                state.loading -> {
                    Spacer(Modifier.height(40.dp))
                    CircularProgressIndicator()
                }

                state.transfer != null && !state.finished -> {
                    PendingContent(state = state, viewModel = viewModel, onBack = onBack)
                }

                else -> {
                    FinishedContent(
                        message = state.message ?: state.error ?: "La solicitud terminó.",
                        failed = state.failed || state.error != null,
                        onRetry = viewModel::retry,
                        onBack = onBack,
                    )
                }
            }
        }
    }
}

@Composable
private fun PendingContent(
    state: TransferApprovalUiState,
    viewModel: TransferApprovalViewModel,
    onBack: () -> Unit,
) {
    val transfer = state.transfer ?: return
    val urgent = state.secondsLeft <= 10
    val progress = (state.secondsLeft.toFloat() / 60f).coerceIn(0f, 1f)
    val codeDescription = "Código de seis dígitos: " +
        (state.code ?: "").filter { it.isDigit() }.map { it.toString() }.joinToString(" ")

    Spacer(Modifier.height(8.dp))
    Icon(
        imageVector = Icons.Filled.Shield,
        contentDescription = null,
        modifier = Modifier.size(56.dp),
        tint = MaterialTheme.colorScheme.primary,
    )
    Spacer(Modifier.height(10.dp))
    Text(
        text = "¿Eres tú quien intenta entrar?",
        fontSize = 24.sp,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.primary,
        textAlign = TextAlign.Center,
    )
    Text(
        text = "Otro teléfono pidió entrar a tu cuenta. Escribe en él este código para autorizarlo.",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )
    Spacer(Modifier.height(18.dp))

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        ),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(
                text = "Solicitud de",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = transfer.requestedDeviceName,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                text = "Hora: ${transferTime(transfer.requestedAt)}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(10.dp))
            StatusChip(
                text = if (state.secondsLeft > 0) {
                    "Expira en ${clockText(state.secondsLeft)}"
                } else {
                    "Expirado"
                },
                color = if (urgent) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
            )
        }
    }

    Spacer(Modifier.height(18.dp))
    Text(
        text = "Tu código",
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(8.dp))
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 22.dp, horizontal = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = state.code ?: "······",
                fontFamily = FontFamily.Monospace,
                fontSize = 40.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 6.sp,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
                modifier = Modifier.semantics { contentDescription = codeDescription },
            )
            Spacer(Modifier.height(6.dp))
            Text(
                text = "Solo vive en este teléfono y se borra en 60 segundos.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
                textAlign = TextAlign.Center,
            )
        }
    }

    Spacer(Modifier.height(14.dp))
    LinearProgressIndicator(
        progress = { progress },
        modifier = Modifier
            .fillMaxWidth()
            .semantics { contentDescription = "Tiempo restante ${state.secondsLeft} segundos" },
        color = if (urgent) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
        trackColor = MaterialTheme.colorScheme.surfaceVariant,
    )

    Spacer(Modifier.height(16.dp))
    if (!transfer.submittedCodeHash.isNullOrBlank()) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.primaryContainer
            ),
        ) {
            Text(
                text = if (state.error == null) {
                    "El nuevo teléfono ya escribió un código. Compáralo con el de arriba."
                } else {
                    state.error
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
                modifier = Modifier.padding(12.dp),
            )
        }
        Spacer(Modifier.height(12.dp))
    }

    state.error?.takeIf { transfer.submittedCodeHash.isNullOrBlank() }?.let { message ->
        Text(
            text = message,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.error,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(10.dp))
    }

    OutlinedButton(
        onClick = viewModel::rejectAsNotMe,
        modifier = Modifier
            .fillMaxWidth()
            .height(52.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.error),
        colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(
            contentColor = MaterialTheme.colorScheme.error
        ),
    ) {
        Text("No fui yo", fontSize = 16.sp, fontWeight = FontWeight.Bold)
    }
    Spacer(Modifier.height(8.dp))
    Text(
        text = "Si no fuiste tú, rechaza la solicitud y cambia tu contraseña.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )
    Spacer(Modifier.height(8.dp))
    TextButton(onClick = onBack) {
        Text("Cerrar")
    }
}

@Composable
private fun FinishedContent(
    message: String,
    failed: Boolean,
    onRetry: () -> Unit,
    onBack: () -> Unit,
) {
    Spacer(Modifier.height(24.dp))
    Icon(
        imageVector = Icons.Filled.Shield,
        contentDescription = null,
        modifier = Modifier.size(56.dp),
        tint = if (failed) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
    )
    Spacer(Modifier.height(12.dp))
    Text(
        text = if (failed) "No se pudo completar" else "Solicitud resuelta",
        style = MaterialTheme.typography.titleLarge,
        fontWeight = FontWeight.Bold,
        textAlign = TextAlign.Center,
    )
    Spacer(Modifier.height(10.dp))
    Card(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = message,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(16.dp),
            textAlign = TextAlign.Center,
        )
    }
    Spacer(Modifier.height(18.dp))
    if (failed) {
        Button(onClick = onRetry, modifier = Modifier.fillMaxWidth()) {
            Text("Intentar de nuevo")
        }
        Spacer(Modifier.height(6.dp))
    }
    TextButton(onClick = onBack) {
        Text("Volver")
    }
}

@Composable
private fun SecureWindow(enabled: Boolean) {
    val context = LocalContext.current
    DisposableEffect(enabled) {
        val window = context.findActivity()?.window
        if (enabled) {
            window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
        onDispose {
            window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
    }
}

@Composable
private fun OnStopEffect(onStop: () -> Unit) {
    val lifecycleOwner = LocalLifecycleOwner.current
    val currentOnStop by rememberUpdatedState(onStop)
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) currentOnStop()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

private fun transferTime(raw: String): String = try {
    OffsetDateTime.parse(raw).format(DateTimeFormatter.ofPattern("HH:mm"))
} catch (_: Exception) {
    raw.take(5)
}

private fun clockText(seconds: Int): String =
    "%d:%02d".format(seconds / 60, seconds % 60)
