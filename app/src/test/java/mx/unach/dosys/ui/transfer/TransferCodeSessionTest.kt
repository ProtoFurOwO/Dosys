package mx.unach.dosys.ui.transfer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.security.MessageDigest
import java.security.SecureRandom

class TransferCodeSessionTest {

    private var now = 1_000L

    /** SecureRandom determinista para probar el formato y los ceros. */
    private class FixedRandom(private val value: Int) : SecureRandom() {
        override fun nextInt(bound: Int): Int = value
    }

    private fun session(value: Int = 482913) =
        TransferCodeSession(clock = { now }, random = FixedRandom(value))

    @Test
    fun `genera seis digitos con ceros a la izquierda`() {
        assertEquals("000042", session(42).generate())
        assertEquals("482913", session(482913).generate())
    }

    @Test
    fun `el codigo siempre queda dentro del rango`() {
        repeat(20) { index ->
            val code = session(index * 49_999).generate()
            assertEquals(6, code.length)
            assertTrue(code.all { it.isDigit() })
            assertTrue(code.toInt() in 0..999_999)
        }
    }

    @Test
    fun `expira a los 60 segundos con reloj inyectable`() {
        val codeSession = session()
        codeSession.generate()

        now += 59_000
        assertTrue(codeSession.isActive())
        assertEquals(1, codeSession.remainingSeconds())

        now += 1_000
        assertFalse(codeSession.isActive())
        assertEquals(0, codeSession.remainingSeconds())
        assertNull(codeSession.currentCode())
    }

    @Test
    fun `compara correctamente y destruye el codigo`() {
        val codeSession = session()
        codeSession.generate()

        assertTrue(codeSession.matches("482913"))
        assertTrue(codeSession.matches("482 913"))
        assertFalse(codeSession.matches("482914"))
        assertFalse(codeSession.matches("12345"))

        codeSession.destroy()
        assertFalse(codeSession.matches("482913"))
        assertNull(codeSession.displayCode())
    }

    @Test
    fun `no compara despues de expirar`() {
        val codeSession = session()
        codeSession.generate()
        now += 60_000
        assertFalse(codeSession.matches("482913"))
    }

    @Test
    fun `compara el hash sin guardar el codigo`() {
        val codeSession = session()
        codeSession.generate()
        val hash = MessageDigest.getInstance("SHA-256")
            .digest("482913".toByteArray(Charsets.US_ASCII))
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }

        assertTrue(codeSession.matchesHash(hash))
        assertFalse(codeSession.matchesHash("0".repeat(64)))

        codeSession.destroy()
        assertFalse(codeSession.matchesHash(hash))
    }
}
