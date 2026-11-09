package mx.unach.dosys.ui.appointments

import mx.unach.dosys.data.model.AppointmentStatus
import mx.unach.dosys.data.model.PatientAppointment
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.OffsetDateTime

class AppointmentFiltersTest {

    private val now = OffsetDateTime.parse("2026-11-05T12:00:00Z")

    private fun appointment(
        id: Int,
        scheduledAt: String,
        status: AppointmentStatus = AppointmentStatus.SCHEDULED,
        isUpcoming: Boolean = true,
    ) = PatientAppointment(
        id = id,
        specialty = "Medicina General",
        doctorName = "Dra. López",
        scheduledAt = scheduledAt,
        location = "Consultorio 1",
        status = status,
        notes = null,
        checkedInAt = null,
        isUpcoming = isUpcoming,
    )

    @Test
    fun `una cita futura es proxima`() {
        val future = appointment(1, "2026-11-06T12:00:00Z")
        assertTrue(AppointmentFilters.isUpcoming(future, now))
    }

    @Test
    fun `una cita pasada no es proxima aunque el servidor diga que si`() {
        val past = appointment(2, "2026-10-08T12:00:00Z", isUpcoming = true)
        assertFalse(AppointmentFilters.isUpcoming(past, now))
    }

    @Test
    fun `una cita atendida o cancelada va al historial`() {
        assertFalse(
            AppointmentFilters.isUpcoming(
                appointment(3, "2026-12-01T12:00:00Z", status = AppointmentStatus.ATTENDED),
                now,
            )
        )
        assertFalse(
            AppointmentFilters.isUpcoming(
                appointment(4, "2026-12-01T12:00:00Z", status = AppointmentStatus.CANCELLED),
                now,
            )
        )
    }

    @Test
    fun `separa proximas e historial y ordena cada grupo`() {
        val (upcoming, past) = AppointmentFilters.split(
            listOf(
                appointment(1, "2026-11-20T12:00:00Z"),
                appointment(2, "2026-10-08T12:00:00Z"),
                appointment(3, "2026-11-08T12:00:00Z"),
                appointment(4, "2026-09-24T12:00:00Z"),
            ),
            now,
        )

        assertEquals(listOf(3, 1), upcoming.map { it.id })
        assertEquals(listOf(2, 4), past.map { it.id })
    }

    @Test
    fun `la proxima cita es la mas cercana en el futuro`() {
        val next = AppointmentFilters.nextUpcoming(
            listOf(
                appointment(1, "2026-11-20T12:00:00Z"),
                appointment(2, "2026-11-08T12:00:00Z"),
                appointment(3, "2026-10-08T12:00:00Z"),
            ),
            now,
        )
        assertEquals(2, next?.id)
    }

    @Test
    fun `sin citas futuras no hay proxima cita`() {
        assertNull(
            AppointmentFilters.nextUpcoming(
                listOf(appointment(1, "2026-10-08T12:00:00Z")),
                now,
            )
        )
    }

    @Test
    fun `el check-in solo se habilita para citas agendadas o confirmadas`() {
        assertFalse(
            AppointmentFilters.canCheckIn(
                listOf(appointment(1, "2026-11-20T12:00:00Z", status = AppointmentStatus.REQUESTED))
            )
        )
        assertTrue(
            AppointmentFilters.canCheckIn(
                listOf(appointment(2, "2026-11-20T12:00:00Z", status = AppointmentStatus.SCHEDULED))
            )
        )
        assertTrue(
            AppointmentFilters.canCheckIn(
                listOf(appointment(3, "2026-11-20T12:00:00Z", status = AppointmentStatus.CONFIRMED))
            )
        )
        assertFalse(
            AppointmentFilters.canCheckIn(
                listOf(
                    appointment(4, "2026-11-20T12:00:00Z", status = AppointmentStatus.REQUESTED),
                    appointment(5, "2026-11-21T12:00:00Z", status = AppointmentStatus.CANCELLED),
                )
            )
        )
    }
}
