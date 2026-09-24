"""Nombres legibles de las acciones de la bitácora."""

from app.models.enums import UserRole

ACTION_LABELS = {
    # API
    "login_success": "Acceso correcto (API)",
    "login_failed": "Intento de acceso fallido (API)",
    "list_patients": "Lista de pacientes consultada (API)",
    "create_consultation": "Consulta registrada (API)",
    "read_profile": "Perfil consultado (app del paciente)",
    "read_consultations": "Consultas consultadas (app del paciente)",
    "read_appointments": "Citas consultadas (app del paciente)",
    "patient_checkin": "Llegada confirmada con QR (app del paciente)",
    "patient_checkin_failed": "Check-in rechazado por código incorrecto",
    # Portal
    "portal_login_success": "Acceso al portal",
    "portal_login_failed": "Intento de acceso fallido al portal",
    "portal_login_denied": "Acceso al portal denegado por rol",
    "portal_read_patients": "Lista de pacientes consultada",
    "portal_read_patient": "Expediente consultado",
    "portal_read_appointments": "Agenda consultada",
    "portal_create_consultation": "Consulta registrada",
    "portal_create_appointment": "Cita agendada",
    "portal_create_patient": "Paciente registrado",
    "portal_update_patient": "Datos del paciente actualizados",
    "portal_create_doctor": "Médico registrado",
    "portal_update_doctor": "Datos del médico actualizados",
    "portal_user_activated": "Usuario reactivado",
    "portal_user_deactivated": "Usuario desactivado",
    "portal_reset_password": "Contraseña restablecida",
    "portal_send_credentials": "Credenciales enviadas al paciente (simulado)",
}


def action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)


ROLE_LABELS = {
    UserRole.DOCTOR: "Médico",
    UserRole.LABORATORY: "Laboratorio",
    UserRole.RECEPTION: "Recepción",
    UserRole.PATIENT: "Paciente",
}
