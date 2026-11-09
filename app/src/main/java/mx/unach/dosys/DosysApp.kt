package mx.unach.dosys

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import mx.unach.dosys.core.di.ServiceLocator

/**
 * Punto de entrada de la aplicación.
 * Inicializa el contenedor de dependencias y el canal de avisos de seguridad.
 */
class DosysApp : Application() {
    override fun onCreate() {
        super.onCreate()
        ServiceLocator.init(this)
        createSecurityChannel()
    }

    private fun createSecurityChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            SECURITY_CHANNEL_ID,
            "Seguridad",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Solicitudes para agregar dispositivos de confianza"
            setShowBadge(true)
        }
        manager.createNotificationChannel(channel)
    }

    companion object {
        const val SECURITY_CHANNEL_ID = "security"
    }
}
