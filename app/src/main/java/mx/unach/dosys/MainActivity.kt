package mx.unach.dosys

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import mx.unach.dosys.ui.navigation.DosysNavHost
import mx.unach.dosys.ui.theme.DosysTheme

/**
 * Única Activity de la app (patrón single-activity + Compose Navigation).
 */
class MainActivity : ComponentActivity() {
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
