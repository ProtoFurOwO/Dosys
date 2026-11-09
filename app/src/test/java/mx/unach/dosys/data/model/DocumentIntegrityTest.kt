package mx.unach.dosys.data.model

import kotlinx.serialization.json.Json
import mx.unach.dosys.ui.documents.signaturePreview
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DocumentIntegrityTest {

    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun `parsea una firma valida`() {
        val result = json.decodeFromString<DocumentIntegrityResponse>(
            """
            {
              "id": 11,
              "intact": true,
              "registered_signature": "abc123",
              "current_signature": "abc123",
              "message": "Firma electrónica válida. El archivo no ha cambiado."
            }
            """.trimIndent()
        )

        assertTrue(result.intact)
        assertEquals(11, result.id)
        assertEquals("abc123", result.registeredSignature)
    }

    @Test
    fun `parsea un documento alterado`() {
        val result = json.decodeFromString<DocumentIntegrityResponse>(
            """
            {
              "id": 12,
              "intact": false,
              "registered_signature": "abc123",
              "current_signature": "def456",
              "message": "Documento alterado. La firma electrónica no coincide."
            }
            """.trimIndent()
        )

        assertFalse(result.intact)
        assertEquals("abc123", result.registeredSignature)
        assertEquals("def456", result.currentSignature)
    }

    @Test
    fun `la firma se muestra como prefijo corto sin la palabra sha`() {
        val preview = signaturePreview("abcdef0123456789abcdef0123456789")

        assertEquals("abcdef0123456789…", preview)
        assertFalse(preview.contains("SHA", ignoreCase = true))
    }
}
