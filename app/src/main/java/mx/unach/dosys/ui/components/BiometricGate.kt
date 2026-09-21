package mx.unach.dosys.ui.components

import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity

/**
 * Módulo de biometría: pide huella (o el bloqueo del teléfono) antes de mostrar
 * datos clínicos. Si el dispositivo no tiene biometría configurada, deja
 * continuar para no bloquear la demostración.
 */
@Composable
fun BiometricGate(
    onUnlocked: () -> Unit,
    modifier: Modifier = Modifier,
    title: String = "Desbloquea tu expediente",
    description: String = "Usa tu huella o el bloqueo del teléfono para ver tu información clínica.",
) {
    val context = LocalContext.current
    val activity = context as? FragmentActivity
    val currentOnUnlocked by rememberUpdatedState(onUnlocked)

    val canAuthenticate = remember {
        BiometricManager.from(context)
            .canAuthenticate(
                BiometricManager.Authenticators.BIOMETRIC_WEAK or
                    BiometricManager.Authenticators.DEVICE_CREDENTIAL
            ) == BiometricManager.BIOMETRIC_SUCCESS
    }
    var error by remember { mutableStateOf<String?>(null) }

    val prompt = remember(activity) {
        activity?.let { host ->
            BiometricPrompt(
                host,
                ContextCompat.getMainExecutor(context),
                object : BiometricPrompt.AuthenticationCallback() {
                    override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                        currentOnUnlocked()
                    }

                    override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                        error = errString.toString()
                    }
                },
            )
        }
    }

    val promptInfo = remember(title, description) {
        BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .setSubtitle(description)
            .setAllowedAuthenticators(
                BiometricManager.Authenticators.BIOMETRIC_WEAK or
                    BiometricManager.Authenticators.DEVICE_CREDENTIAL
            )
            .build()
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            imageVector = Icons.Filled.Fingerprint,
            contentDescription = null,
            modifier = Modifier.size(56.dp),
            tint = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.height(16.dp))
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            text = description,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(20.dp))

        if (canAuthenticate && prompt != null) {
            Button(
                onClick = { prompt.authenticate(promptInfo) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Desbloquear con huella")
            }
        } else {
            Text(
                text = "Este teléfono no tiene huella configurada.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(10.dp))
            Button(
                onClick = currentOnUnlocked,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Continuar")
            }
        }

        error?.let { message ->
            Spacer(Modifier.height(12.dp))
            Text(
                text = message,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
                textAlign = TextAlign.Center,
            )
        }
    }
}
