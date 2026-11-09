package mx.unach.dosys.data.model

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import mx.unach.dosys.data.repository.DeviceResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TrustedDeviceModelsTest {

    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun `parsea la lista de dispositivos y marca el actual`() {
        val devices = json.decodeFromString<List<TrustedDevice>>(
            """
            [
              {
                "id": 123,
                "name": "Xiaomi 2510DPC44G",
                "is_current": true,
                "last_seen_at": "2026-11-09T07:47:46Z",
                "created_at": "2026-11-09T07:00:00Z"
              },
              {
                "id": 124,
                "name": "Pixel 8",
                "is_current": false,
                "last_seen_at": null,
                "created_at": "2026-11-09T08:00:00Z"
              }
            ]
            """.trimIndent()
        )

        assertEquals(2, devices.size)
        assertTrue(devices.first().isCurrent)
        assertEquals("Xiaomi 2510DPC44G", devices.first().name)
        assertEquals("2026-11-09T07:47:46Z", devices.first().lastSeenAt)
        assertEquals(false, devices.last().isCurrent)
        assertNull(devices.last().lastSeenAt)
    }

    @Test
    fun `serializa el registro del dispositivo actual`() {
        val body = json.encodeToString(
            DeviceRegisterRequest(
                deviceId = "a1b2c3d4-0000-0000-0000-000000000000",
                deviceName = "Xiaomi 2510DPC44G",
                fcmToken = "token-fcm",
            )
        )

        assertTrue(body.contains("\"device_id\":\"a1b2c3d4"))
        assertTrue(body.contains("\"device_name\":\"Xiaomi 2510DPC44G\""))
        assertTrue(body.contains("\"fcm_token\":\"token-fcm\""))
    }

    @Test
    fun `omite el token fcm cuando no esta disponible`() {
        val body = json.encodeToString(
            DeviceRegisterRequest(
                deviceId = "a1b2c3d4-0000-0000-0000-000000000000",
                deviceName = "Xiaomi 2510DPC44G",
            )
        )

        assertTrue(body.contains("\"device_id\""))
        assertTrue(!body.contains("fcm_token"))
    }

    @Test
    fun `el error de dispositivo conserva el codigo http`() {
        assertEquals(409, DeviceResult.Error("límite alcanzado", 409).code)
        assertEquals(401, DeviceResult.Error("no autorizado", 401).code)
        assertNull(DeviceResult.Error("sin conexión").code)
        assertEquals("detalle", DeviceResult.Success("detalle").value)
    }
}
