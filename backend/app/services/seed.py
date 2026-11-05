"""Datos iniciales: catálogo de permisos, roles base y cuentas de demostración."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus
from app.models.lab_study import LabStudy
from app.models.patient import Patient
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.services.appointments import AppointmentError, create_appointment
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
        # ya los editó (o los personalizó), el arranque no los sobrescribe. Cuando
        # el catálogo crece (permisos nuevos) se agregan los que falten sin quitar
        # los que el hospital haya ajustado.
        if str(role.id) not in edited_role_ids:
            desired = {
                permissions[item] for item in DEFAULT_ROLE_PERMISSIONS.get(code, ()) if item in permissions
            }
            if not role.permissions:
                role.permissions = sorted(desired, key=lambda permission: permission.code)
            else:
                granted = set(role.permissions)
                missing = desired - granted
                if missing:
                    role.permissions = list(role.permissions) + sorted(missing, key=lambda permission: permission.code)
        roles[code] = role

    await db.flush()
    return roles


LAB_STUDIES: tuple[tuple[str, str, str, str | None], ...] = (
    ("tipo_sangre", "Tipo de sangre (ABO y Rh)", "laboratorio", "Una gota de sangre; resultado inmediato"),
    ("biometria", "Biometría hemática completa", "laboratorio", "Serie roja, blanca y plaquetas"),
    ("quimica", "Química sanguínea de 6 elementos", "laboratorio", "Glucosa, urea, creatinina, colesterol y más"),
    ("glucosa", "Glucosa en ayuno", "laboratorio", "Requiere 8 horas de ayuno"),
    ("ego", "Examen general de orina", "laboratorio", "Muestra de orina de la primera micción"),
    ("rx_torax", "Rayos X de tórax", "imagen", "Proyección posteroanterior y lateral"),
    ("rx_extremidad", "Rayos X de extremidad", "imagen", "Región afectada, dos proyecciones"),
    ("ultrasonido", "Ultrasonido abdominal", "imagen", "Ayuno de 6 horas y vejiga llena"),
    ("ecg", "Electrocardiograma", "imagen", "Reposo, 12 derivaciones"),
    ("cultivo", "Cultivo de exudado faríngeo", "laboratorio", "Resultado en 48 a 72 horas"),
)


async def ensure_lab_studies(db: AsyncSession) -> None:
    """Carga el catálogo de estudios de demostración (idempotente)."""
    for code, name, category, description in LAB_STUDIES:
        study = await db.scalar(select(LabStudy).where(LabStudy.code == code))
        if study is None:
            db.add(LabStudy(code=code, name=name, category=category, description=description))
        else:
            study.name = name
            study.category = category
            study.description = description
    await db.flush()


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
        await ensure_lab_studies(db)

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
                    allergies="Penicilina (urticaria), polen",
                    medical_history="Apendicectomía (2018). Padre con diabetes tipo 2.",
                    chronic_conditions="Hipertensión arterial en control",
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

        lab_user = await db.scalar(select(User).where(User.username == "laboratorio"))
        if lab_user is None:
            db.add(
                User(
                    username="laboratorio",
                    full_name="Laboratorio Central",
                    password_hash=hash_password("Lab12345!"),
                    role_id=roles["laboratory"].id,
                )
            )

        reception_user = await db.scalar(select(User).where(User.username == "recepcion"))
        if reception_user is None:
            db.add(
                User(
                    username="recepcion",
                    full_name="Recepción",
                    password_hash=hash_password("Recepcion123!"),
                    role_id=roles["reception"].id,
                )
            )

        await db.flush()
        patient = await db.scalar(select(Patient).where(Patient.user_id == patient_user.id))
        doctor = await db.scalar(select(Doctor).where(Doctor.user_id == doctor_user.id))
        if patient is None or doctor is None:
            raise RuntimeError("No se pudieron preparar los datos demo")

        # Completar la demo sin pisar datos que ya haya capturado el hospital.
        if not patient.allergies and not patient.medical_history and not patient.chronic_conditions:
            patient.allergies = "Penicilina (urticaria), polen"
            patient.medical_history = "Apendicectomía (2018). Padre con diabetes tipo 2."
            patient.chronic_conditions = "Hipertensión arterial en control"
            await db.flush()

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

        # Mantén al menos una cita futura para que la app nunca arranque vacía.
        now = datetime.now(timezone.utc)
        upcoming = await db.scalar(
            select(Appointment.id).where(
                Appointment.patient_id == patient.id,
                Appointment.scheduled_at >= now,
                Appointment.status != AppointmentStatus.CANCELLED,
            ).limit(1)
        )
        if upcoming is None:
            try:
                await create_appointment(
                    db,
                    patient=patient,
                    doctor=doctor,
                    specialty="Medicina General",
                    scheduled_at=now + timedelta(days=3, hours=1),
                    location="Consultorio 3",
                    room="Consultorio 3",
                    notes="Cita de demostración",
                )
            except AppointmentError:
                # Si el horario ya está ocupado, la demo sigue funcionando con
                # las citas que ya existan.
                pass

        await db.commit()
