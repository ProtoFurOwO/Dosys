package mx.unach.dosys.ui.components

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import java.io.File

/**
 * Guarda el archivo en el caché privado de la app y lo entrega al visor que el
 * paciente elija (visor de PDF, galería…) sin exponerlo a otras apps.
 */
fun openBytesWithDevice(context: Context, bytes: ByteArray, name: String, mime: String): Boolean {
    val directory = File(context.cacheDir, "documentos").apply { mkdirs() }
    val file = File(directory, name)
    file.writeBytes(bytes)
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    val intent = Intent(Intent.ACTION_VIEW).apply {
        setDataAndType(uri, mime)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    return runCatching { context.startActivity(intent) }.isSuccess
}
