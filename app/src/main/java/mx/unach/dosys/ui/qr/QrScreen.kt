package mx.unach.dosys.ui.qr

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import kotlinx.coroutines.delay
import mx.unach.dosys.data.mock.MockData
import mx.unach.dosys.ui.components.ScreenScaffold

/**
 * Check-in del paciente: QR temporal de un solo uso + código numérico de respaldo
 * (por si la cámara de recepción falla en la demo).
 */
@Composable
fun QrScreen(onBack: () -> Unit) {
    var generation by remember { mutableIntStateOf(0) }
    var remaining by remember { mutableIntStateOf(MockData.QR_TTL_SECONDS) }
    val payload = remember(generation) { "${MockData.QR_PAYLOAD}|G$generation" }
    val qrBitmap = remember(payload) { generateQrBitmap(payload) }

    LaunchedEffect(generation) {
        remaining = MockData.QR_TTL_SECONDS
        while (remaining > 0) {
            delay(1_000)
            remaining -= 1
        }
    }

    ScreenScaffold(title = "Mi QR de check-in", onBack = onBack) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Top,
        ) {
            Text(
                text = "Muéstralo en recepción. El token expira en minutos y es de un solo uso: aunque alguien lo fotografíe, no le sirve después.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(24.dp))

            Card {
                Image(
                    bitmap = qrBitmap.asImageBitmap(),
                    contentDescription = "Código QR de check-in",
                    modifier = Modifier
                        .size(240.dp)
                        .padding(16.dp),
                )
            }

            Spacer(Modifier.height(16.dp))
            if (remaining > 0) {
                Text(
                    text = "Válido por ${remaining / 60}:${(remaining % 60).toString().padStart(2, '0')}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                )
            } else {
                Text(
                    text = "El código ya expiró",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.error,
                )
                Spacer(Modifier.height(8.dp))
                Button(onClick = { generation += 1 }) { Text("Generar uno nuevo") }
            }

            Spacer(Modifier.height(24.dp))
            Text("Código de respaldo", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(
                text = MockData.QR_BACKUP_CODE,
                fontSize = 32.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                letterSpacing = 6.sp,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                text = "Si la cámara no lee el QR, recepción puede teclear este código.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
        }
    }
}

private fun generateQrBitmap(content: String, size: Int = 512): Bitmap {
    val hints = mapOf(
        EncodeHintType.MARGIN to 1,
        EncodeHintType.CHARACTER_SET to "UTF-8",
    )
    val matrix = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, size, size, hints)
    val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
    val black = android.graphics.Color.BLACK
    val white = android.graphics.Color.WHITE
    for (x in 0 until size) {
        for (y in 0 until size) {
            bitmap.setPixel(x, y, if (matrix.get(x, y)) black else white)
        }
    }
    return bitmap
}
