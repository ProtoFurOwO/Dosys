package mx.unach.dosys.ui.security

import android.graphics.Bitmap
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter

/** Genera el QR del 2FA en el propio celular (ZXing ya viene en el proyecto). */
fun qrImageBitmap(content: String, size: Int = 640): ImageBitmap {
    val matrix = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, size, size)
    val pixels = IntArray(size * size) { index ->
        val x = index % size
        val y = index / size
        if (matrix[x, y]) 0xFF101C15.toInt() else 0xFFFFFFFF.toInt()
    }
    return Bitmap.createBitmap(pixels, size, size, Bitmap.Config.ARGB_8888).asImageBitmap()
}
