package mx.unach.dosys.ui.transfer

import android.os.SystemClock
import java.security.MessageDigest
import java.security.SecureRandom

/**
 * Código local del dispositivo de confianza (A).
 *
 * Vive **solo en memoria** durante 60 segundos, se genera con [SecureRandom] y
 * se compara con [MessageDigest.isEqual] para no filtrar información por el
 * tiempo de respuesta. El reloj es inyectable ([SystemClock.elapsedRealtime]
 * en producción) para poder probar la expiración sin esperar.
 */
class TransferCodeSession(
    private val clock: () -> Long = { SystemClock.elapsedRealtime() },
    private val random: SecureRandom = SecureRandom(),
) {

    private var code: String? = null
    private var startedAt: Long = 0L

    /** Genera un código nuevo de 6 dígitos (con ceros a la izquierda). */
    fun generate(): String {
        val generated = random.nextInt(1_000_000).toString().padStart(6, '0')
        code = generated
        startedAt = clock()
        return generated
    }

    fun isActive(): Boolean = code != null && remainingSeconds() > 0

    fun remainingSeconds(): Int {
        if (code == null) return 0
        val elapsed = ((clock() - startedAt) / 1_000L).toInt()
        return (LIFETIME_SECONDS - elapsed).coerceAtLeast(0)
    }

    /** Código vigente o null si ya expiró o se destruyó. */
    fun currentCode(): String? = code?.takeIf { remainingSeconds() > 0 }

    /** Agrupado para mostrarlo como "482 913". */
    fun displayCode(): String? {
        val current = currentCode() ?: return null
        return "${current.substring(0, 3)} ${current.substring(3)}"
    }

    /** Comparación en tiempo constante contra el código vigente. */
    fun matches(candidate: String): Boolean {
        val expected = currentCode() ?: return false
        val clean = candidate.filter { it.isDigit() }
        if (clean.length != CODE_LENGTH) return false
        return MessageDigest.isEqual(
            expected.toByteArray(Charsets.US_ASCII),
            clean.toByteArray(Charsets.US_ASCII),
        )
    }

    /** Destruye el código (al expirar, salir de la pantalla o aprobar). */
    fun destroy() {
        code = null
        startedAt = 0L
    }

    companion object {
        const val CODE_LENGTH = 6
        const val LIFETIME_SECONDS = 60
    }
}
