package mx.unach.dosys.core.push

import android.Manifest
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import mx.unach.dosys.DosysApp
import mx.unach.dosys.MainActivity
import mx.unach.dosys.R
import mx.unach.dosys.core.di.ServiceLocator

/**
 * Notificaciones de seguridad. El payload solo trae ``type`` y ``transfer_id``:
 * nunca datos personales ni secretos, y el transfer_id no se muestra ni se usa
 * para navegar (la pantalla consulta el servidor con la sesión local).
 */
class DosysMessagingService : FirebaseMessagingService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        scope.launch {
            ServiceLocator.deviceIdentity.saveFcmToken(token)
            if (ServiceLocator.sessionManager.currentToken() != null) {
                ServiceLocator.deviceRepository.registerDevice()
            }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        if (message.data["type"] != "device_transfer") return
        if (message.data["transfer_id"].isNullOrBlank()) return

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            // Sin permiso, el sondeo en primer plano sigue cubriendo el flujo.
            return
        }

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(MainActivity.EXTRA_TRANSFER_APPROVAL, true)
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            NOTIFICATION_ID,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(this, DosysApp.SECURITY_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle("D.O.S.Y.S · Seguridad")
            .setContentText("Hay una solicitud de acceso esperando tu aprobación.")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()
        NotificationManagerCompat.from(this).notify(NOTIFICATION_ID, notification)
    }

    companion object {
        private const val NOTIFICATION_ID = 7101
    }
}
