package mx.unach.dosys.data.model

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import mx.unach.dosys.data.repository.appointmentRequestMessage
import mx.unach.dosys.ui.components.appointmentStatusLabel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AppointmentModelsTest {

    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun `parsea el catalogo de medicos`() {
        val doctors = json.decodeFromString<List<DoctorOption>>(
            """
            [
              {"id": 3, "full_name": "Dr. Demo Médico", "specialty": "Medicina General"}
            ]
            """.trimIndent()
        )

        assertEquals(1, doctors.size)
        assertEquals(3, doctors.first().id)
        assertEquals("Dr. Demo Médico", doctors.first().fullName)
    }

    @Test
    fun `parsea disponibilidad con slots ocupados`() {
        val response = json.decodeFromString<AppointmentAvailabilityResponse>(
            """
            {
              "doctor_id": 3,
              "date": "2026-11-10",
              "slots": [
                {"time": "08:00", "scheduled_at": "2026-11-10T14:00:00Z", "available": true},
                {"time": "08:30", "scheduled_at": "2026-11-10T14:30:00Z", "available": false}
              ]
            }
            """.trimIndent()
        )

        assertEquals(3, response.doctorId)
        assertEquals("2026-11-10", response.date)
        assertEquals(2, response.slots.size)
        assertTrue(response.slots.first().available)
        assertEquals(false, response.slots.last().available)
    }

    @Test
    fun `parsea una cita recien solicitada`() {
        val appointment = json.decodeFromString<PatientAppointment>(
            """
            {
              "id": 10,
              "specialty": "Medicina General",
              "doctor_name": "Dr. Demo Médico",
              "scheduled_at": "2026-11-10T15:30:00Z",
              "location": "Consultorio 1",
              "status": "requested",
              "notes": null,
              "is_upcoming": true,
              "checkin_available": false,
              "checkin_reason": "requested"
            }
            """.trimIndent()
        )

        assertEquals(AppointmentStatus.REQUESTED, appointment.status)
        assertEquals("Solicitada", appointmentStatusLabel(appointment.status))
        assertEquals(false, appointment.checkinAvailable)
        assertEquals("requested", appointment.checkinReason)
    }

    @Test
    fun `serializa el cuerpo de la solicitud`() {
        val body = json.encodeToString(
            AppointmentRequest(
                doctorId = 3,
                specialty = "Medicina General",
                date = "2026-11-10",
                time = "09:30",
                reason = "Dolor lumbar de una semana",
            )
        )

        assertTrue(body.contains("\"doctor_id\":3"))
        assertTrue(body.contains("\"date\":\"2026-11-10\""))
        assertTrue(body.contains("\"time\":\"09:30\""))
        assertTrue(body.contains("Dolor lumbar"))
    }

    @Test
    fun `mapea los errores del flujo de solicitud`() {
        assertEquals(
            "Ese horario acaba de ocuparse. Elige otro.",
            appointmentRequestMessage(409),
        )
        assertEquals(
            "Espera un minuto antes de intentar de nuevo.",
            appointmentRequestMessage(429),
        )
        assertEquals(
            "El motivo es obligatorio.",
            appointmentRequestMessage(422, "El motivo es obligatorio."),
        )
        assertEquals(
            "Revisa los datos de la solicitud.",
            appointmentRequestMessage(422, null),
        )
    }
}
