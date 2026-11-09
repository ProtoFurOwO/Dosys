package mx.unach.dosys.data.model

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ConsultationSerializationTest {

    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun `una respuesta antigua sin signos vitales sigue parseando`() {
        val parsed = json.decodeFromString<PatientConsultation>(
            """
            {
              "id": 1,
              "patient_id": 7,
              "doctor_name": "Dra. López",
              "specialty": "Medicina General",
              "reason": "Dolor abdominal",
              "diagnosis": "Gastroenteritis aguda",
              "created_at": "2026-11-08T10:00:00Z"
            }
            """.trimIndent()
        )

        assertEquals(1, parsed.id)
        assertNull(parsed.notes)
        assertNull(parsed.bloodPressure)
        assertNull(parsed.heartRate)
        assertNull(parsed.respiratoryRate)
        assertNull(parsed.temperatureC)
        assertNull(parsed.oxygenSaturation)
        assertNull(parsed.weightKg)
        assertNull(parsed.heightCm)
        assertNull(parsed.physicalExam)
    }

    @Test
    fun `tolera null explicito en los campos nuevos`() {
        val parsed = json.decodeFromString<PatientConsultation>(
            """
            {
              "id": 2,
              "patient_id": 7,
              "doctor_name": "Dra. López",
              "specialty": "Medicina General",
              "reason": "Control",
              "diagnosis": "Sano",
              "notes": null,
              "created_at": "2026-11-08T10:00:00Z",
              "blood_pressure": null,
              "heart_rate": null,
              "respiratory_rate": null,
              "temperature_c": null,
              "oxygen_saturation": null,
              "weight_kg": null,
              "height_cm": null,
              "physical_exam": null
            }
            """.trimIndent()
        )

        assertNull(parsed.notes)
        assertNull(parsed.bloodPressure)
        assertNull(parsed.heartRate)
        assertNull(parsed.temperatureC)
        assertNull(parsed.weightKg)
        assertNull(parsed.heightCm)
        assertNull(parsed.physicalExam)
    }

    @Test
    fun `parsea los signos vitales y la exploracion fisica`() {
        val parsed = json.decodeFromString<PatientConsultation>(
            """
            {
              "id": 4,
              "patient_id": 7,
              "doctor_name": "Dra. López",
              "specialty": "Medicina General",
              "reason": "Dolor abdominal",
              "diagnosis": "Gastroenteritis aguda",
              "notes": "Hidratación y control en 48 horas",
              "created_at": "2026-11-08T10:00:00Z",
              "updated_at": null,
              "blood_pressure": "118/76",
              "heart_rate": 88,
              "respiratory_rate": 18,
              "temperature_c": 38.1,
              "oxygen_saturation": 97,
              "weight_kg": 68.5,
              "height_cm": 168,
              "physical_exam": "Paciente consciente, abdomen con dolor a la palpación."
            }
            """.trimIndent()
        )

        assertEquals("118/76", parsed.bloodPressure)
        assertEquals(88, parsed.heartRate)
        assertEquals(18, parsed.respiratoryRate)
        assertEquals(38.1, parsed.temperatureC ?: 0.0, 0.001)
        assertEquals(97, parsed.oxygenSaturation)
        assertEquals(68.5, parsed.weightKg ?: 0.0, 0.001)
        assertEquals(168.0, parsed.heightCm ?: 0.0, 0.001)
        assertEquals("Paciente consciente, abdomen con dolor a la palpación.", parsed.physicalExam)
    }

    @Test
    fun `ignora campos desconocidos de versiones futuras`() {
        val parsed = json.decodeFromString<PatientConsultation>(
            """
            {
              "id": 5,
              "patient_id": 7,
              "doctor_name": "Dra. López",
              "specialty": "Medicina General",
              "reason": "Control",
              "diagnosis": "Sano",
              "created_at": "2026-11-08T10:00:00Z",
              "campo_futuro": "se ignora"
            }
            """.trimIndent()
        )

        assertEquals(5, parsed.id)
        assertNull(parsed.heartRate)
    }
}
