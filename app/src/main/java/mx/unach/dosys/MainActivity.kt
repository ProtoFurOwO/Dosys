package mx.unach.dosys

import android.content.Intent
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.fragment.app.FragmentActivity
import mx.unach.dosys.ui.navigation.DosysNavHost
import mx.unach.dosys.ui.theme.DosysTheme

/**
 * Única Activity de la app (patrón single-activity + Compose Navigation).
 * Extiende FragmentActivity porque el desbloqueo con huella (BiometricPrompt) lo requiere.
 *
 * La notificación de seguridad abre directamente la pantalla de aprobación; la
 * pantalla consulta el servidor y no confía en datos del Intent.
 */
class MainActivity : FragmentActivity() {

    private var openTransferApproval by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        openTransferApproval = intent?.getBooleanExtra(EXTRA_TRANSFER_APPROVAL, false) == true
        // Se consume el extra: una recreación (rotación, proceso) no debe volver
        // a abrir la pantalla de aprobación por la misma notificación.
        intent?.removeExtra(EXTRA_TRANSFER_APPROVAL)
        setContent {
            DosysTheme {
                DosysNavHost(openTransferApproval = openTransferApproval)
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (intent.getBooleanExtra(EXTRA_TRANSFER_APPROVAL, false)) {
            openTransferApproval = true
            intent.removeExtra(EXTRA_TRANSFER_APPROVAL)
        }
    }

    companion object {
        const val EXTRA_TRANSFER_APPROVAL = "mx.unach.dosys.extra.TRANSFER_APPROVAL"
    }
}
