"""Nombres legibles de las acciones de la bitácora."""

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
    # Seguridad del login
    "account_locked": "Cuenta bloqueada por intentos fallidos",
    "account_unlocked": "Cuenta desbloqueada",
    "login_blocked": "Intento de acceso con cuenta bloqueada",
    "login_2fa_challenge": "Segundo factor solicitado",
    "login_2fa_success": "Segundo factor correcto",
    "login_2fa_failed": "Segundo factor incorrecto",
    "two_factor_enabled": "Segundo factor activado",
    "two_factor_disabled": "Segundo factor desactivado",
    "portal_reset_two_factor": "Segundo factor reiniciado (soporte)",
    "recovery_code_used": "Código de recuperación usado",
    # Roles y permisos
    "portal_create_role": "Rol creado",
    "portal_update_role": "Permisos del rol actualizados",
    "portal_assign_role": "Rol asignado a un usuario",
    # Documentos
    "read_documents": "Documentos consultados (app del paciente)",
    "download_document": "Documento descargado (app del paciente)",
    "portal_upload_document": "Documento agregado al expediente",
    "portal_download_document": "Documento descargado del expediente",
    "portal_verify_document": "Integridad de documento verificada",
    "portal_delete_document": "Documento eliminado del expediente",
}


def action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)


ROLE_LABELS = {
    "admin": "Administrador",
    "doctor": "Médico",
    "laboratory": "Laboratorio",
    "reception": "Recepción",
    "patient": "Paciente",
}
