package mx.unach.dosys.ui.checkin

import android.os.Bundle
import android.content.pm.ActivityInfo
import com.journeyapps.barcodescanner.CaptureActivity

/**
 * Pantalla del escáner QR con la orientación del teléfono.
 *
 * La actividad por defecto de la librería ZXing viene fijada en horizontal
 * (sensorLandscape en su manifiesto), lo que volteaba la pantalla del paciente
 * al abrir la cámara. Esta variante sigue la orientación natural del teléfono.
 */
class PortraitCaptureActivity : CaptureActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR)
    }
}
