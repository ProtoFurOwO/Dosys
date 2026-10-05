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
    "portal_create_staff": "Usuario del personal registrado",
    "portal_update_doctor": "Datos del médico actualizados",
    "portal_update_staff": "Datos del usuario actualizados",
    "portal_user_activated": "Usuario reactivado",
    "portal_user_deactivated": "Usuario desactivado",
    "portal_reset_password": "Contraseña restablecida",
    "portal_send_credentials": "Credenciales enviadas por correo",
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


ENTITY_LABELS = {
    "authentication": "Acceso",
    "patient": "Paciente",
    "consultation": "Consulta",
    "appointment": "Cita",
    "document": "Documento",
    "user": "Usuario",
    "role": "Rol",
}

DETAIL_KEYS = {
    "username": "usuario",
    "role": "rol",
    "patient_id": "paciente",
    "sha256": "huella",
    "resultado": "verificación",
    "intentos": "intentos",
    "bloqueo_min": "bloqueo (min)",
    "search": "búsqueda",
    "to": "correo",
    "code": "código",
    "permisos": "permisos",
    "specialty": "especialidad",
}

DETAIL_VALUES = {
    "intacto": "correcta",
    "alterado": "alterada",
}

DETAIL_SEPARATORS = ("·", "|")


def entity_label(entity_type: str, entity_id: str | None) -> str:
    """Nombre legible de la entidad afectada, con su identificador."""
    base = ENTITY_LABELS.get(entity_type, entity_type)
    return f"{base} #{entity_id}" if entity_id else base


def detail_pairs(detail: str | None) -> list[tuple[str, str]]:
    """Convierte 'clave=valor clave2=valor2' en pares legibles."""
    if not detail:
        return []

    raw = detail
    for separator in DETAIL_SEPARATORS:
        raw = raw.replace(separator, " ")

    pairs: list[tuple[str, str]] = []
    for chunk in raw.split():
        if "=" not in chunk:
            pairs.append(("", chunk))
            continue
        key, value = chunk.split("=", 1)
        if key == "sha256" and len(value) > 16:
            value = f"{value[:12]}…"
        pairs.append((DETAIL_KEYS.get(key, key), DETAIL_VALUES.get(value, value)))
    return pairs


ROLE_LABELS = {
    "admin": "Administrador",
    "doctor": "Médico",
    "laboratory": "Laboratorio",
    "reception": "Recepción",
    "patient": "Paciente",
}
