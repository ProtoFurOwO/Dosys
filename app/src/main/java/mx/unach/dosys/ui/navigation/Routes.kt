package mx.unach.dosys.ui.navigation

/**
 * Rutas de navegación de la aplicación del paciente.
 * Se usan strings simples mientras el grafo es pequeño.
 */
object Routes {
    const val LOGIN = "login"
    const val LOGIN_TRANSFERRED = "login_transferred"
    const val HOME = "home"
    const val RECORD = "record"
    const val STUDIES = "studies"
    const val PRESCRIPTIONS = "prescriptions"
    const val APPOINTMENTS = "appointments"
    const val APPOINTMENT_REQUEST = "appointment_request"
    const val CHECKIN = "checkin"
    const val SECURITY = "security"
    const val DOCUMENTS = "documents"
    const val DOCUMENT_DETAIL = "document/{id}"
    const val TRANSFER_APPROVAL = "transfer_approval"

    fun document(id: Int): String = "document/$id"
}
