package mx.unach.dosys.data.mock

/**
 * Datos de ejemplo para desarrollar la interfaz y la demo.
 * Se sustituyen por las respuestas reales de la API REST.
 */
object MockData {

    const val PATIENT_NAME = "José Antonio Matuz"
    const val PATIENT_CURP = "MAAJ010415HCSRRN09"
    const val BLOOD_TYPE = "O+"
    const val BIRTH_DATE = "15 de abril de 2001"
    const val AGE = 25
    const val EMERGENCY_CONTACT = "María Argueta · 961 123 4567"

    // ── Citas ──────────────────────────────────────────────────────────────
    data class Appointment(
        val id: Int,
        val specialty: String,
        val doctor: String,
        val date: String,
        val time: String,
        val place: String,
        val status: AppointmentStatus,
        val notes: String? = null,
    )

    enum class AppointmentStatus { AGENDADA, CONFIRMADA, ATENDIDA, CANCELADA }

    val appointments = listOf(
        Appointment(1, "Medicina General", "Dra. López Hernández", "24 de septiembre de 2026", "10:30 h", "Consultorio 3", AppointmentStatus.CONFIRMADA, "Control de hipertensión"),
        Appointment(2, "Laboratorio", "Toma de muestra", "18 de septiembre de 2026", "08:00 h", "Laboratorio central", AppointmentStatus.AGENDADA, "Biometría hemática de control"),
        Appointment(3, "Cardiología", "Dr. Ramírez Cruz", "2 de agosto de 2026", "12:00 h", "Consultorio 7", AppointmentStatus.ATENDIDA),
        Appointment(4, "Medicina General", "Dra. López Hernández", "10 de julio de 2026", "09:15 h", "Consultorio 3", AppointmentStatus.ATENDIDA),
    )

    val nextAppointment = appointments.first { it.status != AppointmentStatus.ATENDIDA && it.status != AppointmentStatus.CANCELADA }

    // ── Recetas ────────────────────────────────────────────────────────────
    data class Prescription(
        val id: Int,
        val medication: String,
        val dose: String,
        val instructions: String,
        val prescribedBy: String,
        val period: String,
        val taken: Int,
        val total: Int,
        val doses: List<DoseLog>,
    )

    data class DoseLog(
        val id: Int,
        val label: String,
        val taken: Boolean,
    )

    val prescriptions = listOf(
        Prescription(
            id = 1,
            medication = "Paracetamol 500 mg",
            dose = "1 tableta cada 8 horas",
            instructions = "Tomar con alimentos. No exceder 4 g al día.",
            prescribedBy = "Dra. López Hernández",
            period = "5 días · 12 al 16 de septiembre",
            taken = 4,
            total = 15,
            doses = listOf(
                DoseLog(1, "Hoy · 08:00", true),
                DoseLog(2, "Hoy · 16:00", false),
                DoseLog(3, "Hoy · 00:00", false),
            ),
        ),
        Prescription(
            id = 2,
            medication = "Amoxicilina 500 mg",
            dose = "1 cápsula cada 12 horas",
            instructions = "Completar el esquema aunque te sientas mejor.",
            prescribedBy = "Dra. López Hernández",
            period = "7 días · 12 al 18 de septiembre",
            taken = 2,
            total = 14,
            doses = listOf(
                DoseLog(4, "Hoy · 09:00", true),
                DoseLog(5, "Hoy · 21:00", false),
            ),
        ),
        Prescription(
            id = 3,
            medication = "Losartán 50 mg",
            dose = "1 tableta cada 24 horas",
            instructions = "Tratamiento crónico para la presión arterial. Tomar a la misma hora.",
            prescribedBy = "Dr. Ramírez Cruz",
            period = "Uso continuo",
            taken = 28,
            total = 30,
            doses = listOf(
                DoseLog(6, "Hoy · 07:00", false),
            ),
        ),
    )

    // ── Estudios ───────────────────────────────────────────────────────────
    data class StudyOrder(
        val id: Int,
        val name: String,
        val area: String,
        val requestedBy: String,
        val requestedAt: String,
        val status: StudyStatus,
        val resultSummary: String? = null,
        val resultDate: String? = null,
        val findings: List<Pair<String, String>> = emptyList(),
    )

    enum class StudyStatus { SOLICITADO, EN_PROCESO, LISTO }

    val studies = listOf(
        StudyOrder(
            id = 1,
            name = "Biometría hemática",
            area = "Laboratorio",
            requestedBy = "Dra. López Hernández",
            requestedAt = "16 de septiembre · 11:05",
            status = StudyStatus.LISTO,
            resultSummary = "Valores dentro de rango. Hemoglobina 14.2 g/dL.",
            resultDate = "16 de septiembre · 16:40",
            findings = listOf(
                "Hemoglobina" to "14.2 g/dL (13.0–17.0)",
                "Leucocitos" to "6.8 ×10³/µL (4.5–11.0)",
                "Plaquetas" to "245 ×10³/µL (150–450)",
                "Hematocrito" to "42 % (38–50)",
            ),
        ),
        StudyOrder(
            id = 2,
            name = "Rayos X de tórax",
            area = "Imagenología",
            requestedBy = "Dra. López Hernández",
            requestedAt = "16 de septiembre · 11:08",
            status = StudyStatus.EN_PROCESO,
        ),
        StudyOrder(
            id = 3,
            name = "Química sanguínea (6 elementos)",
            area = "Laboratorio",
            requestedBy = "Dra. López Hernández",
            requestedAt = "16 de septiembre · 11:10",
            status = StudyStatus.SOLICITADO,
        ),
        StudyOrder(
            id = 4,
            name = "Electrocardiograma",
            area = "Cardiología",
            requestedBy = "Dr. Ramírez Cruz",
            requestedAt = "2 de agosto · 12:20",
            status = StudyStatus.LISTO,
            resultSummary = "Ritmo sinusal. Sin alteraciones agudas.",
            resultDate = "2 de agosto · 12:45",
            findings = listOf(
                "Ritmo" to "Sinusal",
                "Frecuencia" to "72 lpm",
                "Eje" to "Normal",
                "Hallazgos" to "Sin isquemia aguda",
            ),
        ),
    )

    // ── Expediente ─────────────────────────────────────────────────────────
    val allergies = listOf("Penicilina", "Polen")
    val chronicConditions = listOf("Hipertensión arterial")
    val antecedents = listOf(
        "Apendicectomía (2018)",
        "Padre con diabetes tipo 2",
    )

    data class Consultation(
        val date: String,
        val doctor: String,
        val specialty: String,
        val reason: String,
        val diagnosis: String,
    )

    val consultations = listOf(
        Consultation("10 de julio de 2026", "Dra. López Hernández", "Medicina General", "Dolor de cabeza y mareo", "Cefalea tensional · HTA en control"),
        Consultation("2 de agosto de 2026", "Dr. Ramírez Cruz", "Cardiología", "Control de presión arterial", "HTA esencial, electrocardiograma normal"),
        Consultation("16 de septiembre de 2026", "Dra. López Hernández", "Medicina General", "Fiebre y malestar general", "Infección de vías respiratorias altas"),
    )

    // ── QR de check-in ─────────────────────────────────────────────────────
    const val QR_PAYLOAD = "DOSYS|PAC-1048|A7K9M2"
    const val QR_BACKUP_CODE = "A7K9M2"
    const val QR_TTL_SECONDS = 180
}
