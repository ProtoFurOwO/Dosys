package mx.unach.dosys.ui.security

import androidx.compose.foundation.Image
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
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.compose.foundation.text.KeyboardOptions
import mx.unach.dosys.ui.components.ScreenScaffold

/**
 * Módulo de seguridad del paciente: activa o desactiva el segundo factor (TOTP)
 * y muestra los códigos de recuperación una sola vez.
 */
@Composable
fun SecurityScreen(
    onBack: () -> Unit,
    viewModel: SecurityViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    ScreenScaffold(title = "Mi seguridad", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (state.isLoading) {
                item { CircularProgressIndicator() }
            }

            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = if (state.enabled) {
                            MaterialTheme.colorScheme.primaryContainer
                        } else {
                            MaterialTheme.colorScheme.surfaceVariant
                        }
                    ),
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Filled.Shield, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.size(10.dp))
                        Column {
                            Text(
                                text = if (state.enabled) "Segundo factor activo" else "Segundo factor inactivo",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                            )
                            Text(
                                text = if (state.enabled) {
                                    "Se pedirá un código de 6 dígitos al iniciar sesión. Códigos de recuperación: ${state.recoveryCodesRemaining}."
                                } else {
                                    "Protege tu cuenta: además de la contraseña se pedirá un código temporal."
                                },
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }

            state.message?.let { message ->
                item {
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
            state.error?.let { message ->
                item {
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }

            if (state.recoveryCodes.isNotEmpty()) {
                item { RecoveryCodesCard(codes = state.recoveryCodes, onDismiss = viewModel::dismissRecoveryCodes) }
            }

            state.setup?.let { setup ->
                item {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = "Escanea este código",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                            )
                            Text(
                                text = "Abre Google Authenticator, Microsoft Authenticator o cualquier app TOTP y escanea el QR.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(Modifier.height(14.dp))
                            Image(
                                bitmap = remember(setup.otpauthUri) { qrImageBitmap(setup.otpauthUri) },
                                contentDescription = "Código QR para la app autenticadora",
                                modifier = Modifier.size(220.dp),
                            )
                            Spacer(Modifier.height(10.dp))
                            Text(
                                text = "Secreto manual: ${setup.secret}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(Modifier.height(16.dp))
                            ConfirmCodeForm(isSubmitting = state.isSubmitting, onConfirm = viewModel::confirm)
                        }
                    }
                }
            }

            if (!state.enabled && state.setup == null && !state.isLoading) {
                item {
                    Button(
                        onClick = viewModel::startSetup,
                        enabled = !state.isSubmitting,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Activar segundo factor")
                    }
                }
            }

            if (state.enabled) {
                item {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp)) {
                            Text(
                                text = "Desactivar el segundo factor",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                            )
                            Text(
                                text = "Confirma tu contraseña para apagarlo.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(Modifier.height(12.dp))
                            DisableForm(isSubmitting = state.isSubmitting, onDisable = viewModel::disable)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ConfirmCodeForm(isSubmitting: Boolean, onConfirm: (String) -> Unit) {
    var code by remember { mutableStateOf("") }
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        OutlinedTextField(
            value = code,
            onValueChange = { value -> code = value.filter { it.isDigit() }.take(6) },
            label = { Text("Código de 6 dígitos") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword, imeAction = ImeAction.Done),
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(10.dp))
        Button(
            onClick = { onConfirm(code) },
            enabled = !isSubmitting && code.length == 6,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (isSubmitting) "Verificando…" else "Activar")
        }
    }
}

@Composable
private fun DisableForm(isSubmitting: Boolean, onDisable: (String) -> Unit) {
    var password by remember { mutableStateOf("") }
    Column {
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Contraseña") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(10.dp))
        OutlinedButton(
            onClick = { onDisable(password) },
            enabled = !isSubmitting && password.isNotBlank(),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Desactivar 2FA")
        }
    }
}

@Composable
private fun RecoveryCodesCard(codes: List<String>, onDismiss: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(
                text = "Códigos de recuperación",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Guárdalos en un lugar seguro: se muestran una sola vez y cada uno sirve una vez.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))
            codes.forEach { code ->
                Text(
                    text = code,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                )
            }
            Spacer(Modifier.height(14.dp))
            Button(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) {
                Text("Ya los guardé")
            }
        }
    }
}
