"""Datos iniciales: catálogo de permisos, roles base y cuentas de demostración."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus
from app.models.patient import Patient
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.services.permissions import BASE_ROLES, DEFAULT_ROLE_PERMISSIONS, PERMISSIONS


async def ensure_roles_and_permissions(db: AsyncSession) -> dict[str, Role]:
    """Crea el catálogo de permisos y los roles base si todavía no existen.

    Los permisos de un rol solo se inicializan al crearlo: si un administrador
    los cambia desde el panel, el arranque no los sobrescribe.
    """
    permissions: dict[str, Permission] = {}
    for code, area, action, description in PERMISSIONS:
        permission = await db.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, area=area, action=action, description=description)
            db.add(permission)
        else:
            permission.area = area
            permission.action = action
            permission.description = description
        permissions[code] = permission

    roles: dict[str, Role] = {}
    edited_role_ids = {
        str(entity_id)
        for entity_id in (
            await db.scalars(
                select(AuditLog.entity_id).where(AuditLog.action == "portal_update_role")
            )
        ).all()
        if entity_id is not None
    }
    for code, name, description in BASE_ROLES:
        role = await db.scalar(select(Role).where(Role.code == code))
        if role is None:
            role = Role(code=code, name=name, description=description, is_system=True)
            db.add(role)
            await db.flush()
        else:
            role.name = name
            role.description = description
        # Los roles de sistema estrenan la matriz por defecto; si un administrador
        # ya los editó (o los personalizó), el arranque no los sobrescribe.
        if not role.permissions and str(role.id) not in edited_role_ids:
            role.permissions = [
                permissions[item] for item in DEFAULT_ROLE_PERMISSIONS.get(code, ()) if item in permissions
            ]
        roles[code] = role

    await db.flush()
    return roles


async def load_role(db: AsyncSession, code: str) -> Role:
    role = await db.scalar(select(Role).where(Role.code == code))
    if role is None:
        raise RuntimeError(f"Falta el rol base {code}")
    return role


async def seed_demo_data() -> None:
    """Inserta datos ficticios idempotentes para la demostración.

    Credenciales de demo:
    - paciente / Paciente123!   (app del paciente)
    - medico / Medico123!       (portal clínico)
    - admin / Admin123!         (panel de administración)
    """
    async with SessionLocal() as db:
        roles = await ensure_roles_and_permissions(db)

        patient_user = await db.scalar(select(User).where(User.username == "paciente"))
        if patient_user is None:
            patient_user = User(
                username="paciente",
                password_hash=hash_password("Paciente123!"),
                role_id=roles["patient"].id,
            )
            db.add(patient_user)
            await db.flush()
            db.add(
                Patient(
                    user_id=patient_user.id,
                    full_name="José Antonio Matuz",
                    curp="MAAJ010415HCSRRN09",
                    blood_type="O+",
                    emergency_contact="María Argueta · 961 123 4567",
                )
            )

        doctor_user = await db.scalar(select(User).where(User.username == "medico"))
        if doctor_user is None:
            doctor_user = User(
                username="medico",
                password_hash=hash_password("Medico123!"),
                role_id=roles["doctor"].id,
            )
            db.add(doctor_user)
            await db.flush()
            db.add(
                Doctor(
                    user_id=doctor_user.id,
                    full_name="Dra. López Hernández",
                    specialty="Medicina General",
                )
            )

        admin_user = await db.scalar(select(User).where(User.username == "admin"))
        if admin_user is None:
            db.add(
                User(
                    username="admin",
                    password_hash=hash_password("Admin123!"),
                    role_id=roles["admin"].id,
                )
            )

        await db.flush()
        patient = await db.scalar(select(Patient).where(Patient.user_id == patient_user.id))
        doctor = await db.scalar(select(Doctor).where(Doctor.user_id == doctor_user.id))
        if patient is None or doctor is None:
            raise RuntimeError("No se pudieron preparar los datos demo")

        existing_consultation = await db.scalar(
            select(Consultation).where(Consultation.patient_id == patient.id).limit(1)
        )
        if existing_consultation is None:
            db.add(
                Consultation(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    reason="Control de presión arterial",
                    diagnosis="Hipertensión arterial en control",
                    notes="Datos ficticios para la demostración académica.",
                )
            )

        existing_appointment = await db.scalar(
            select(Appointment).where(Appointment.patient_id == patient.id).limit(1)
        )
        if existing_appointment is None:
            db.add(
                Appointment(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    specialty="Medicina General",
                    scheduled_at=datetime(2026, 9, 24, 16, 30, tzinfo=timezone.utc),
                    location="Consultorio 3",
                    status=AppointmentStatus.CONFIRMED,
                    checkin_code="A7K9M2",
                    notes="Control de hipertensión",
                )
            )
        elif not existing_appointment.checkin_code:
            existing_appointment.checkin_code = "A7K9M2"

        await db.commit()
