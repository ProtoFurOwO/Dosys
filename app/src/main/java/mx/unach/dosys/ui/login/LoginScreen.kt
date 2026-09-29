package mx.unach.dosys.ui.login

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material3.Button
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
 * Pantalla de acceso en dos pasos:
 * 1) usuario y contraseña; 2) código del segundo factor si la cuenta lo tiene activo.
 * El paciente recibe sus credenciales en el hospital (no hay autorregistro).
 */
@Composable
fun LoginScreen(
    onLoggedIn: () -> Unit,
    viewModel: LoginViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(state.loggedIn) {
        if (state.loggedIn) onLoggedIn()
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
            if (state.step == LoginStep.TWO_FACTOR) {
                TwoFactorStep(state = state, viewModel = viewModel)
            } else {
                CredentialsStep(state = state, viewModel = viewModel)
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
        label = { Text("Código de 6 dígitos") },
        leadingIcon = { Icon(Icons.Filled.Shield, contentDescription = null) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.NumberPassword,
            imeAction = ImeAction.Done,
        ),
        keyboardActions = KeyboardActions(onDone = { viewModel.verifyCode() }),
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(Modifier.height(6.dp))
    Text(
        text = "Si perdiste el teléfono, escribe uno de tus códigos de recuperación (XXXX-XXXX).",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
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
