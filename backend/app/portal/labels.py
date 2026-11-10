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
    "read_studies": "Estudios consultados (app del paciente)",
    "read_prescriptions": "Recetas consultadas (app del paciente)",
    "session_refreshed": "Sesión renovada sin credenciales",
    "password_changed": "Contraseña cambiada por el usuario",
    "password_reset_requested": "Recuperación de contraseña solicitada",
    "password_reset": "Contraseña restablecida con token",
    "account_email_updated": "Correo de la cuenta actualizado",
    "patient_checkin": "Llegada confirmada con QR (app del paciente)",
    "patient_checkin_failed": "Check-in rechazado por código incorrecto",
    "patient_checkin_out_of_window": "Check-in rechazado fuera de la ventana de la cita",
    # Portal
    "portal_login_success": "Acceso al portal",
    "portal_login_failed": "Intento de acceso fallido al portal",
    "portal_login_denied": "Acceso al portal denegado por rol",
    "portal_read_dashboard": "Panel de inicio consultado",
    "portal_read_patients": "Lista de pacientes consultada",
    "portal_read_patient": "Expediente consultado",
    "portal_read_appointments": "Agenda consultada",
    "portal_read_agenda": "Agenda visual consultada",
    "portal_update_appointment_status": "Estado de cita actualizado",
    "portal_create_consultation": "Consulta registrada",
    "portal_update_consultation": "Consulta corregida (con auditoría)",
    "portal_download_consultation": "Nota de consulta descargada",
    "portal_create_appointment": "Cita agendada",
    "portal_create_patient": "Paciente registrado",
    "portal_update_patient": "Datos del paciente actualizados",
    "portal_create_doctor": "Médico registrado",
    "portal_create_staff": "Usuario del personal registrado",
    "portal_update_doctor": "Datos del médico actualizados",
    "portal_update_staff": "Datos del usuario actualizados",
    "portal_assign_room": "Consultorio asignado en el check-in",
    "portal_create_study_orders": "Estudios solicitados al laboratorio",
    "portal_create_demo_study_order": "Estudio de demostración solicitado",
    "portal_start_study_order": "Estudio marcado en proceso",
    "portal_complete_study_order": "Resultado de estudio capturado",
    "portal_cancel_study_order": "Orden de estudio cancelada",
    "portal_read_checkin_qr": "Pantalla de QR de check-in abierta",
    "portal_revert_checkin": "Check-in revertido por recepción",
    "portal_export_activity": "Bitácora exportada a CSV",
    "portal_read_activity": "Bitácora consultada",
    "portal_create_prescription": "Receta médica emitida",
    "portal_schedule_next_appointment": "Próxima cita agendada desde la consulta",
    "portal_user_activated": "Usuario reactivado",
    "portal_user_deactivated": "Usuario desactivado",
    "portal_reset_password": "Contraseña restablecida",
    "portal_password_reset_requested": "Recuperación de contraseña solicitada desde el portal",
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
    # Dispositivos y transferencia de sesión
    "device_registered": "Dispositivo de confianza registrado",
    "device_transfer_requested": "Transferencia de sesión solicitada",
    "device_transfer_code_submitted": "Código propuesto por el dispositivo nuevo",
    "device_transfer_approved": "Transferencia de sesión aprobada",
    "device_transfer_rejected": "Transferencia de sesión rechazada",
    "device_transfer_failed": "Transferencia fallida por códigos incorrectos",
    "device_transfer_expired": "Transferencia de sesión expirada",
    "device_transfer_fallback": "Transferencia resuelta con segundo factor",
    "device_released": "Dispositivo de confianza liberado",
    # Roles y permisos
    "portal_create_role": "Rol creado",
    "portal_update_role": "Permisos del rol actualizados",
    "portal_assign_role": "Rol asignado a un usuario",
    "admin_role_updated": "Rol actualizado desde la API",
    "admin_role_deleted": "Rol eliminado desde la API",
    "admin_user_role_updated": "Rol de usuario actualizado desde la API",
    # Documentos
    "read_documents": "Documentos consultados (app del paciente)",
    "download_document": "Documento descargado (app del paciente)",
    "portal_upload_document": "Documento agregado al expediente",
    "portal_download_document": "Documento descargado del expediente",
    "portal_verify_document": "Integridad de documento verificada",
    "verify_document": "Firma de documento verificada desde la app",
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
    "study_order": "Estudio",
    "prescription": "Receta",
    "device": "Dispositivo",
    "device_transfer": "Transferencia",
    "audit": "Bitácora",
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
    "campos": "campos cambiados",
    "motivo": "motivo",
    "filas": "filas",
    "study_id": "estudio",
    "room": "consultorio",
    "dispositivo": "dispositivo",
    "pantalla": "pantalla",
    "ordenes": "órdenes",
    "para": "para",
}

DETAIL_VALUES = {
    "intacto": "correcta",
    "alterado": "alterada",
    "too_early": "demasiado temprano",
    "closed": "ventana cerrada",
    "already_checked_in": "ya confirmada",
    "attended": "cita atendida",
    "cancelled": "cita cancelada",
    "codigo_no_encontrado": "código no encontrado",
    "sin_cambios": "sin cambios",
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
