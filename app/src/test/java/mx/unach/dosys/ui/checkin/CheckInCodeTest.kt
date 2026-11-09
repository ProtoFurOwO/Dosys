package mx.unach.dosys.ui.checkin

import mx.unach.dosys.data.model.AppointmentStatus
import mx.unach.dosys.data.model.PatientAppointment
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.OffsetDateTime

class CheckInCodeTest {

    private val now = OffsetDateTime.parse("2026-11-05T12:00:00Z")

    private fun appointment(
        id: Int,
        scheduledAt: String,
        status: AppointmentStatus = AppointmentStatus.SCHEDULED,
    ) = PatientAppointment(
        id = id,
        specialty = "Medicina General",
        doctorName = null,
        scheduledAt = scheduledAt,
        location = "Consultorio 1",
        status = status,
        notes = null,
        checkedInAt = null,
    )

    @Test
    fun `extrae el codigo del contenido del QR`() {
        assertEquals("A7K9M2", CheckInCode.extract("DOSYS-CHECKIN|12|A7K9M2"))
    }

    @Test
    fun `extrae la cita del QR para compatibilidad`() {
        assertEquals(12, CheckInCode.appointmentId("DOSYS-CHECKIN|12|A7K9M2"))
        assertNull(CheckInCode.appointmentId("A7K9M2"))
        assertNull(CheckInCode.appointmentId("DOSYS-CHECKIN|x|A7K9M2"))
    }

    @Test
    fun `acepta el codigo escrito a mano`() {
        assertEquals("A7K9M2", CheckInCode.extract("a7k9m2"))
        assertEquals("A7K9M2", CheckInCode.extract(" A7K9-M2 "))
    }

    @Test
    fun `rechaza textos que no son codigos`() {
        assertNull(CheckInCode.extract(""))
        assertNull(CheckInCode.extract("ABC"))
        assertNull(CheckInCode.extract("DOSYS-CHECKIN|12|"))
    }

    @Test
    fun `solo muestra citas futuras que se pueden confirmar`() {
        val eligible = CheckInAppointments.eligible(
            listOf(
                appointment(1, "2026-11-05T14:00:00Z"),
                appointment(2, "2026-10-08T12:00:00Z"),
                appointment(3, "2026-12-01T12:00:00Z", status = AppointmentStatus.ATTENDED),
                appointment(4, "2026-12-02T12:00:00Z", status = AppointmentStatus.CANCELLED),
                appointment(5, "2026-12-03T12:00:00Z", status = AppointmentStatus.REQUESTED),
            ),
            now,
        )

        assertEquals(listOf(1), eligible.map { it.id })
        assertTrue(eligible.all { it.id != 2 && it.id != 3 && it.id != 4 && it.id != 5 })
    }
}
