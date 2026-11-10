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
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
enum class AppointmentStatus {
    @SerialName("requested") REQUESTED,
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
    @SerialName("is_upcoming") val isUpcoming: Boolean = true,
    @SerialName("checkin_available") val checkinAvailable: Boolean = false,
    @SerialName("checkin_opens_at") val checkinOpensAt: String? = null,
    @SerialName("checkin_closes_at") val checkinClosesAt: String? = null,
    @SerialName("checkin_reason") val checkinReason: String? = null,
)

// ── Solicitud de citas ──────────────────────────────────────────────────────

@Serializable
data class DoctorOption(
    val id: Int,
    @SerialName("full_name") val fullName: String,
    val specialty: String,
)

@Serializable
data class AppointmentAvailabilitySlot(
    val time: String,
    @SerialName("scheduled_at") val scheduledAt: String,
    val available: Boolean,
)

@Serializable
data class AppointmentAvailabilityResponse(
    @SerialName("doctor_id") val doctorId: Int,
    val date: String,
    val slots: List<AppointmentAvailabilitySlot> = emptyList(),
)

@Serializable
data class AppointmentRequest(
    @SerialName("doctor_id") val doctorId: Int,
    val specialty: String,
    val date: String,
    val time: String,
    val reason: String,
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

/** Resultado de comparar la firma registrada con la del archivo actual. */
@Serializable
data class DocumentIntegrityResponse(
    val id: Int,
    val intact: Boolean,
    @SerialName("hash_ok") val hashOk: Boolean = false,
    @SerialName("seal_ok") val sealOk: Boolean = false,
    @SerialName("signature_ok") val signatureOk: Boolean = false,
    @SerialName("signature_algorithm") val signatureAlgorithm: String = "",
    @SerialName("public_key_fingerprint") val publicKeyFingerprint: String = "",
    @SerialName("registered_signature") val registeredSignature: String,
    @SerialName("current_signature") val currentSignature: String,
    val message: String = "",
)

/** Estudio de laboratorio o imagen solicitado al paciente. */
@Serializable
data class PatientStudy(
    val id: Int,
    @SerialName("study_name") val studyName: String,
    val category: String = "",
    val status: String = "",
    @SerialName("requested_at") val requestedAt: String = "",
    @SerialName("performed_at") val performedAt: String? = null,
    @SerialName("document_id") val documentId: Int? = null,
)

/** Medicamento de una receta emitida. */
@Serializable
data class PatientPrescriptionItem(
    val medication: String,
    val dose: String = "",
    val frequency: String = "",
    val duration: String? = null,
)

/** Receta médica emitida al paciente (con su PDF firmado). */
@Serializable
data class PatientPrescription(
    val id: Int,
    @SerialName("created_at") val createdAt: String = "",
    val notes: String? = null,
    @SerialName("document_id") val documentId: Int? = null,
    val items: List<PatientPrescriptionItem> = emptyList(),
)
