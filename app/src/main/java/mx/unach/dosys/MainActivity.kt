package mx.unach.dosys

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.fragment.app.FragmentActivity
import mx.unach.dosys.ui.navigation.DosysNavHost
import mx.unach.dosys.ui.theme.DosysTheme

/**
 * Única Activity de la app (patrón single-activity + Compose Navigation).
 * Extiende FragmentActivity porque el desbloqueo con huella (BiometricPrompt) lo requiere.
 */
class MainActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            DosysTheme {
                DosysNavHost()
            }
        }
    }
}
