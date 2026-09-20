package mx.unach.dosys.core.auth

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "dosys_session")

/**
 * Administra la sesión del paciente (token JWT) en el almacenamiento privado de la app.
 *
 * Pendiente para la fase de seguridad: cifrar el token con Android Keystore
 * (o migrar a EncryptedSharedPreferences) y aplicar auto-cierre de sesión por inactividad.
 */
class SessionManager(private val context: Context) {

    private val tokenKey = stringPreferencesKey("access_token")

    val tokenFlow: Flow<String?> = context.dataStore.data.map { preferences ->
        preferences[tokenKey]
    }

    suspend fun saveToken(token: String) {
        context.dataStore.edit { preferences ->
            preferences[tokenKey] = token
        }
    }

    suspend fun currentToken(): String? = tokenFlow.first()

    suspend fun clear() {
        context.dataStore.edit { preferences -> preferences.clear() }
    }
}
