package mx.unach.dosys.core.device

import android.content.Context
import android.os.Build
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.util.UUID

// Almacenamiento propio: SessionManager.clear() borra su DataStore al cerrar
// sesión o recibir 401, y la identidad del teléfono debe sobrevivir a eso.
private val Context.deviceDataStore by preferencesDataStore(name = "dosys_device")

/**
 * Identidad estable del teléfono para agregar dispositivos de confianza.
 *
 * El identificador es un UUID aleatorio que nunca se muestra; el servidor solo
 * guarda su hash SHA-256. El token FCM también vive aquí, no en la sesión.
 */
class DeviceIdentity(private val context: Context) {

    private val deviceIdKey = stringPreferencesKey("device_id")
    private val fcmTokenKey = stringPreferencesKey("fcm_token")
    private val notificationsPromptedKey = stringPreferencesKey("notifications_prompted")

    suspend fun deviceId(): String {
        val stored = context.deviceDataStore.data.map { it[deviceIdKey] }.first()
        if (!stored.isNullOrBlank()) return stored

        context.deviceDataStore.edit { preferences ->
            if (preferences[deviceIdKey].isNullOrBlank()) {
                preferences[deviceIdKey] = UUID.randomUUID().toString()
            }
        }
        return context.deviceDataStore.data.map { it[deviceIdKey] }.first()
            ?: UUID.randomUUID().toString()
    }

    suspend fun fcmToken(): String? =
        context.deviceDataStore.data.map { it[fcmTokenKey] }.first()

    suspend fun saveFcmToken(token: String) {
        context.deviceDataStore.edit { preferences ->
            preferences[fcmTokenKey] = token
        }
    }

    suspend fun notificationsPrompted(): Boolean =
        context.deviceDataStore.data.map { it[notificationsPromptedKey] == "true" }.first()

    suspend fun markNotificationsPrompted() {
        context.deviceDataStore.edit { preferences ->
            preferences[notificationsPromptedKey] = "true"
        }
    }

    companion object {
        /** Nombre legible del teléfono, sin datos personales. */
        fun localDeviceName(): String {
            val manufacturer = Build.MANUFACTURER
                .lowercase()
                .replaceFirstChar { it.uppercase() }
            val name = "$manufacturer ${Build.MODEL}".trim()
            return name.take(120).ifBlank { "Teléfono Android" }
        }
    }
}
