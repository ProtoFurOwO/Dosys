package mx.unach.dosys.ui.login

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
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocalHospital
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

/**
 * Pantalla de acceso en pasos:
 * 1) usuario y contraseña; 2) código del segundo factor si la cuenta lo tiene
 * activo; o transferencia de sesión si la cuenta ya vive en otro teléfono.
 * El paciente recibe sus credenciales en el hospital (no hay autorregistro).
 */
@Composable
fun LoginScreen(
    onLoggedIn: () -> Unit,
    notice: String? = null,
    viewModel: LoginViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(state.loggedIn) {
        if (state.loggedIn) onLoggedIn()
    }

    if (state.showRecovery) {
        RecoveryDialog(state = state, viewModel = viewModel)
    }

    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            if (notice != null && state.step == LoginStep.CREDENTIALS) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer
                    ),
                ) {
                    Text(
                        text = notice,
                        modifier = Modifier.padding(14.dp),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                        textAlign = TextAlign.Center,
                    )
                }
                Spacer(Modifier.height(20.dp))
            }

            when (state.step) {
                LoginStep.TWO_FACTOR -> TwoFactorStep(state = state, viewModel = viewModel)
                LoginStep.DEVICE_TRANSFER -> DeviceTransferStep(state = state, viewModel = viewModel)
                LoginStep.CREDENTIALS -> CredentialsStep(state = state, viewModel = viewModel)
            }
        }
    }
}

@Composable
private fun CredentialsStep(state: LoginUiState, viewModel: LoginViewModel) {
    Icon(
        imageVector = Icons.Filled.LocalHospital,
        contentDescription = null,
        modifier = Modifier.size(72.dp),
        tint = MaterialTheme.colorScheme.primary,
    )
    Spacer(Modifier.height(12.dp))
    Text(
        text = "D.O.S.Y.S",
        fontSize = 34.sp,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.primary,
    )
    Text(
        text = "Tu expediente clínico, en tus manos",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(36.dp))

    OutlinedTextField(
        value = state.username,
        onValueChange = viewModel::onUsernameChange,
        label = { Text("Usuario o CURP") },
        leadingIcon = { Icon(Icons.Filled.Person, contentDescription = null) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(Modifier.height(12.dp))
    OutlinedTextField(
        value = state.password,
        onValueChange = viewModel::onPasswordChange,
        label = { Text("Contraseña") },
        leadingIcon = { Icon(Icons.Filled.Lock, contentDescription = null) },
        singleLine = true,
        visualTransformation = PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Password,
            imeAction = ImeAction.Done,
        ),
        keyboardActions = KeyboardActions(onDone = { viewModel.login() }),
        modifier = Modifier.fillMaxWidth(),
    )

    state.error?.let { message ->
        Spacer(Modifier.height(10.dp))
        Text(
            text = message,
            color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
        )
    }

    Spacer(Modifier.height(24.dp))
    Button(
        onClick = viewModel::login,
        enabled = !state.isLoading,
        modifier = Modifier
            .fillMaxWidth()
            .height(52.dp),
    ) {
        if (state.isLoading) {
            CircularProgressIndicator(
                modifier = Modifier.size(22.dp),
                strokeWidth = 2.dp,
                color = MaterialTheme.colorScheme.onPrimary,
            )
        } else {
            Text("Iniciar sesión", fontSize = 16.sp)
        }
    }

    Spacer(Modifier.height(8.dp))
    TextButton(onClick = viewModel::openRecovery) {
        Text("¿Olvidaste tu contraseña?")
    }

    Spacer(Modifier.height(20.dp))
    Text(
        text = "Demo local: usa paciente / Paciente123!. El acceso médico se realiza desde el portal clínico.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )
}

@Composable
private fun TwoFactorStep(state: LoginUiState, viewModel: LoginViewModel) {
    var recoveryMode by remember { mutableStateOf(false) }

    Icon(
        imageVector = Icons.Filled.Shield,
        contentDescription = null,
        modifier = Modifier.size(72.dp),
        tint = MaterialTheme.colorScheme.primary,
    )
    Spacer(Modifier.height(12.dp))
    Text(
        text = "Verificación en dos pasos",
        fontSize = 26.sp,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.primary,
        textAlign = TextAlign.Center,
    )
    Text(
        text = "Tu contraseña es correcta. Falta el código de tu app autenticadora.",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )
    Spacer(Modifier.height(28.dp))

    OutlinedTextField(
        value = state.code,
        onValueChange = viewModel::onCodeChange,
        label = { Text(if (recoveryMode) "Código de recuperación" else "Código de 6 dígitos") },
        leadingIcon = { Icon(Icons.Filled.Shield, contentDescription = null) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(
            keyboardType = if (recoveryMode) KeyboardType.Text else KeyboardType.NumberPassword,
            imeAction = ImeAction.Done,
        ),
        keyboardActions = KeyboardActions(onDone = { viewModel.verifyCode() }),
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(Modifier.height(6.dp))
    Text(
        text = if (recoveryMode) {
            "Escribe uno de tus códigos de recuperación, con guion (XXXX-XXXX)."
        } else {
            "Abre tu app autenticadora y escribe el código de 6 dígitos."
        },
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )
    TextButton(onClick = {
        recoveryMode = !recoveryMode
        viewModel.onCodeChange("")
    }) {
        Text(if (recoveryMode) "Usar el código de la app" else "Usar un código de recuperación")
    }

    state.error?.let { message ->
        Spacer(Modifier.height(10.dp))
        Text(
            text = message,
            color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
        )
    }

    Spacer(Modifier.height(24.dp))
    Button(
        onClick = viewModel::verifyCode,
        enabled = !state.isLoading && state.code.isNotBlank(),
        modifier = Modifier
            .fillMaxWidth()
            .height(52.dp),
    ) {
        if (state.isLoading) {
            CircularProgressIndicator(
                modifier = Modifier.size(22.dp),
                strokeWidth = 2.dp,
                color = MaterialTheme.colorScheme.onPrimary,
            )
        } else {
            Text("Verificar", fontSize = 16.sp)
        }
    }

    Spacer(Modifier.height(12.dp))
    TextButton(onClick = viewModel::backToCredentials) {
        Text("Volver a escribir usuario y contraseña")
    }
}

/**
 * Paso B: la cuenta está activa en otro teléfono. El usuario escribe el código
 * que aparece en el dispositivo de confianza y espera la aprobación.
 */
@Composable
private fun DeviceTransferStep(state: LoginUiState, viewModel: LoginViewModel) {
    Icon(
        imageVector = Icons.Filled.Shield,
        contentDescription = null,
        modifier = Modifier.size(72.dp),
        tint = MaterialTheme.colorScheme.primary,
    )
    Spacer(Modifier.height(12.dp))
    Text(
        text = "Autoriza este dispositivo",
        fontSize = 26.sp,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.primary,
        textAlign = TextAlign.Center,
    )
    Text(
        text = "Tu cuenta ya está activa en tu teléfono de confianza. Ahí verás un código de " +
            "6 dígitos: escríbelo aquí para transferir la sesión.",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )
    Spacer(Modifier.height(20.dp))

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        ),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "Tiempo restante",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = clockText(state.transferSecondsLeft),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = if (state.transferSecondsLeft <= 20) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.primary
                    },
                )
            }
            Spacer(Modifier.height(6.dp))
            Text(
                text = "Intentos restantes: ${state.transferSubmissionsLeft}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            state.transferHint?.let { hint ->
                Spacer(Modifier.height(6.dp))
                Text(
                    text = hint,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }

    Spacer(Modifier.height(18.dp))
    OutlinedTextField(
        value = state.code,
        onValueChange = { value ->
            viewModel.onCodeChange(value.filter { it.isDigit() }.take(6))
        },
        label = { Text("Código de 6 dígitos") },
        leadingIcon = { Icon(Icons.Filled.Shield, contentDescription = null) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Number,
            imeAction = ImeAction.Done,
        ),
        keyboardActions = KeyboardActions(onDone = { viewModel.submitTransferCode() }),
        modifier = Modifier.fillMaxWidth(),
    )

    state.error?.let { message ->
        Spacer(Modifier.height(10.dp))
        Text(
            text = message,
            color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
        )
    }

    Spacer(Modifier.height(20.dp))
    Button(
        onClick = viewModel::submitTransferCode,
        enabled = !state.isLoading && state.code.length == 6,
        modifier = Modifier
            .fillMaxWidth()
            .height(52.dp),
    ) {
        if (state.isLoading) {
            CircularProgressIndicator(
                modifier = Modifier.size(22.dp),
                strokeWidth = 2.dp,
                color = MaterialTheme.colorScheme.onPrimary,
            )
        } else {
            Text("Enviar código", fontSize = 16.sp)
        }
    }

    Spacer(Modifier.height(10.dp))
    Text(
        text = "Si no ves el código en tu otro teléfono, revisa que tenga la app abierta o espera la notificación.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )

    TextButton(onClick = viewModel::useTransferFallback) {
        Text("No tengo mi dispositivo anterior")
    }
    TextButton(onClick = viewModel::cancelTransfer) {
        Text("Cancelar")
    }
    if (state.error != null) {
        TextButton(onClick = viewModel::backToCredentials) {
            Text("Intentar de nuevo")
        }
    }
}

@Composable
private fun RecoveryDialog(state: LoginUiState, viewModel: LoginViewModel) {
    AlertDialog(
        onDismissRequest = viewModel::closeRecovery,
        title = { Text("Recuperar contraseña") },
        text = {
            Column {
                if (state.recoveryMessage == null) {
                    Text(
                        "Escribe tu usuario o el correo de tu cuenta. Si existe, enviaremos un enlace " +
                            "para crear una contraseña nueva.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = state.recoveryIdentifier,
                        onValueChange = viewModel::onRecoveryIdentifierChange,
                        label = { Text("Usuario o correo") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    state.recoveryError?.let { message ->
                        Spacer(Modifier.height(8.dp))
                        Text(
                            text = message,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                } else {
                    Text(state.recoveryMessage, style = MaterialTheme.typography.bodyMedium)
                    state.recoveryPreviewUrl?.let { url ->
                        Spacer(Modifier.height(10.dp))
                        Text(
                            text = "Enlace de prueba (modo demo): $url",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
            }
        },
        confirmButton = {
            if (state.recoveryMessage == null) {
                TextButton(onClick = viewModel::requestPasswordReset, enabled = !state.recoveryLoading) {
                    Text(if (state.recoveryLoading) "Enviando…" else "Enviar enlace")
                }
            } else {
                TextButton(onClick = viewModel::closeRecovery) { Text("Entendido") }
            }
        },
        dismissButton = {
            if (state.recoveryMessage == null) {
                TextButton(onClick = viewModel::closeRecovery) { Text("Cancelar") }
            }
        },
    )
}

private fun clockText(seconds: Int): String = "%d:%02d".format(seconds / 60, seconds % 60)
