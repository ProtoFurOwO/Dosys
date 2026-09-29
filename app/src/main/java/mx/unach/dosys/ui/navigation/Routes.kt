package mx.unach.dosys.ui.navigation

/**
 * Rutas de navegación de la aplicación del paciente.
 * Se usan strings simples mientras el grafo es pequeño.
 */
object Routes {
    const val LOGIN = "login"
    const val HOME = "home"
    const val RECORD = "record"
    const val STUDIES = "studies"
    const val STUDY_DETAIL = "study/{id}"
    const val PRESCRIPTIONS = "prescriptions"
    const val QR = "qr"
    const val APPOINTMENTS = "appointments"
    const val CHECKIN = "checkin"
    const val SECURITY = "security"
    const val DOCUMENTS = "documents"

    fun studyDetail(id: Int): String = "study/$id"
}
