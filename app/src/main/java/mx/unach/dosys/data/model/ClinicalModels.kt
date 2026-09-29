package mx.unach.dosys.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Consulta clínica de solo lectura para el paciente autenticado. */
@Serializable
data class PatientConsultation(
    val id: Int,
    @SerialName("patient_id") val patientId: Int,
    @SerialName("doctor_name") val doctorName: String,
    val specialty: String,
    val reason: String,
    val diagnosis: String,
    val notes: String? = null,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
enum class AppointmentStatus {
    @SerialName("scheduled") SCHEDULED,
    @SerialName("confirmed") CONFIRMED,
    @SerialName("attended") ATTENDED,
    @SerialName("cancelled") CANCELLED,
}

/** Cita asignada por el hospital; el paciente no la crea desde la app. */
@Serializable
data class PatientAppointment(
    val id: Int,
    val specialty: String,
    @SerialName("doctor_name") val doctorName: String? = null,
    @SerialName("scheduled_at") val scheduledAt: String,
    val location: String,
    val status: AppointmentStatus,
    val notes: String? = null,
    @SerialName("checked_in_at") val checkedInAt: String? = null,
)

/** Código del QR de recepción para confirmar la llegada. */
@Serializable
data class CheckInRequest(
    val code: String,
)

/** Documento del expediente visible para el paciente. */
@Serializable
data class PatientDocument(
    val id: Int,
    val title: String,
    val category: String,
    @SerialName("original_name") val originalName: String,
    @SerialName("content_type") val contentType: String,
    @SerialName("size_bytes") val sizeBytes: Long,
    val sha256: String,
    @SerialName("created_at") val createdAt: String,
)
