"""Roles, permisos y matriz de acceso.

Los roles viven en la base de datos (tabla `roles`) para que un administrador
pueda crear roles nuevos y repartir permisos sin tocar código.
"""

from app.models.user import User

# (código, área, acción, descripción)
PERMISSIONS: tuple[tuple[str, str, str, str], ...] = (
    ("portal:access", "Portal", "acceso", "Ingresar al portal clínico"),
    ("patients:read", "Pacientes", "lectura", "Ver el listado y el expediente de pacientes"),
    ("patients:write", "Pacientes", "escritura", "Registrar y editar pacientes"),
    ("consultations:read", "Consultas", "lectura", "Consultar el historial de consultas"),
    ("consultations:write", "Consultas", "escritura", "Registrar consultas médicas"),
    ("appointments:read", "Citas", "lectura", "Ver la agenda de citas"),
    ("appointments:write", "Citas", "escritura", "Agendar y actualizar citas"),
    ("documents:read", "Documentos", "lectura", "Consultar y descargar documentos"),
    ("documents:write", "Documentos", "escritura", "Subir documentos al expediente"),
    ("documents:delete", "Documentos", "eliminación", "Eliminar documentos cargados por error"),
    ("users:manage", "Usuarios", "administración", "Gestionar cuentas y accesos"),
    ("roles:manage", "Roles", "administración", "Crear roles y asignar permisos"),
    ("audit:read", "Auditoría", "lectura", "Consultar la bitácora del sistema"),
)

BASE_ROLES: tuple[tuple[str, str, str], ...] = (
    ("admin", "Administrador", "Acceso completo al sistema"),
    ("doctor", "Médico", "Atención clínica y expediente del paciente"),
    ("laboratory", "Laboratorio", "Resultados y documentos de estudios"),
    ("reception", "Recepción", "Agenda y registro de pacientes"),
    ("patient", "Paciente", "Acceso a su propia información"),
)

DEFAULT_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "admin": tuple(code for code, *_ in PERMISSIONS),
    "doctor": (
        "portal:access",
        "patients:read",
        "patients:write",
        "consultations:read",
        "consultations:write",
        "appointments:read",
        "appointments:write",
        "documents:read",
        "documents:write",
        "documents:delete",
        "audit:read",
    ),
    "laboratory": (
        "portal:access",
        "patients:read",
        "documents:read",
        "documents:write",
    ),
    "reception": (
        "portal:access",
        "patients:read",
        "patients:write",
        "appointments:read",
        "appointments:write",
        "documents:read",
    ),
    "patient": (),
}


def permission_codes(user: User) -> set[str]:
    """Permisos efectivos del usuario según su rol (relación ya cargada)."""
    return {permission.code for permission in user.role.permissions}


def has_permission(user: User, code: str) -> bool:
    return code in permission_codes(user)


def has_any_permission(user: User, *codes: str) -> bool:
    granted = permission_codes(user)
    return any(code in granted for code in codes)
