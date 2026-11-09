package mx.unach.dosys.ui.appointments

import mx.unach.dosys.data.model.AppointmentStatus
import mx.unach.dosys.data.model.PatientAppointment
import java.time.OffsetDateTime

/**
 * Reglas de presentación de citas, separadas del ViewModel para poder probarlas.
 * El backend ya envía ``is_upcoming``; la fecha se vuelve a validar en el
 * teléfono para que un servidor viejo o un reloj desfasado no muestre una cita
 * pasada como si fuera la próxima.
 */
object AppointmentFilters {

    fun isUpcoming(appointment: PatientAppointment, now: OffsetDateTime = OffsetDateTime.now()): Boolean {
        if (appointment.status == AppointmentStatus.CANCELLED ||
            appointment.status == AppointmentStatus.ATTENDED
        ) {
            return false
        }
        val parsed = runCatching { OffsetDateTime.parse(appointment.scheduledAt) }.getOrNull()
        return if (parsed != null) parsed.isAfter(now) else appointment.isUpcoming
    }

    fun split(
        appointments: List<PatientAppointment>,
        now: OffsetDateTime = OffsetDateTime.now(),
    ): Pair<List<PatientAppointment>, List<PatientAppointment>> {
        val upcoming = appointments
            .filter { isUpcoming(it, now) }
            .sortedBy { it.scheduledAt }
        val upcomingIds = upcoming.map(PatientAppointment::id).toSet()
        val past = appointments
            .filterNot { it.id in upcomingIds }
            .sortedByDescending { it.scheduledAt }
        return upcoming to past
    }

    fun nextUpcoming(
        appointments: List<PatientAppointment>,
        now: OffsetDateTime = OffsetDateTime.now(),
    ): PatientAppointment? = split(appointments, now).first.firstOrNull()

    /** El check-in solo aplica a citas ya agendadas/confirmadas, no a solicitudes. */
    fun canCheckIn(appointments: List<PatientAppointment>): Boolean = appointments.any {
        it.status == AppointmentStatus.SCHEDULED || it.status == AppointmentStatus.CONFIRMED
    }
}
