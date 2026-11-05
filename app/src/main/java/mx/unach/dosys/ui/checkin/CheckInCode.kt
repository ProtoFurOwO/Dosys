package mx.unach.dosys.ui.checkin

import mx.unach.dosys.data.model.AppointmentStatus
import mx.unach.dosys.data.model.PatientAppointment
import mx.unach.dosys.ui.appointments.AppointmentFilters
import java.time.OffsetDateTime

/** Utilidades del QR de recepción, aisladas para probarlas sin Android. */
object CheckInCode {

    const val PREFIX = "DOSYS-CHECKIN|"

    /**
     * Acepta el contenido completo del QR (``DOSYS-CHECKIN|12|A7K9M2``) o un
     * código escrito a mano. Devuelve ``null`` si no hay nada utilizable.
     */
    fun extract(raw: String): String? {
        val clean = raw.trim()
        if (clean.startsWith(PREFIX)) {
            return clean.split("|").getOrNull(2)?.trim()?.uppercase()?.takeIf { it.isNotBlank() }
        }
        val candidate = clean.uppercase().filter { it.isLetterOrDigit() }
        return candidate.takeIf { it.length in 4..32 }
    }
}

/** Citas que la pantalla de check-in debe mostrar. */
object CheckInAppointments {

    fun eligible(
        appointments: List<PatientAppointment>,
        now: OffsetDateTime = OffsetDateTime.now(),
    ): List<PatientAppointment> = AppointmentFilters.split(appointments, now).first
        .filter { it.status != AppointmentStatus.CANCELLED && it.status != AppointmentStatus.ATTENDED }
}
