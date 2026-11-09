"""Autoservicio de citas para pacientes.

El paciente no escribe directo en la agenda: envía una solicitud con un médico,
fecha y hora. El servidor valida reglas de negocio y la deja en estado
``requested``; recepción la confirma o la rechaza. Así se evita que un paciente
invente horarios o bloquee la agenda de otros.
"""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.api.routes.patients import appointment_response, get_patient_for_user
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus, UserRole
from app.models.user import User
from app.schemas.appointment import (
    AppointmentAvailabilityResponse,
    AppointmentAvailabilitySlot,
    AppointmentRequestCreate,
    AppointmentResponse,
    DoctorOption,
)
from app.services import rate_limit
from app.services.appointments import AppointmentError, create_appointment
from app.services.audit import write_audit_event

router = APIRouter(prefix="/appointments", tags=["Citas"])
CLINIC_TIMEZONE = ZoneInfo("America/Mexico_City")
SLOT_MINUTES = 30
MAX_DAYS_AHEAD = 30


async def _active_doctor(db: AsyncSession, doctor_id: int) -> Doctor | None:
    return await db.scalar(
        select(Doctor)
        .join(User, Doctor.user_id == User.id)
        .where(Doctor.id == doctor_id, User.is_active.is_(True))
    )


@router.get("/doctors", response_model=list[DoctorOption])
async def list_doctors(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> list[DoctorOption]:
    """Médicos activos para el selector de la app (sin datos de pacientes)."""
    rows = (
        await db.execute(
            select(Doctor)
            .join(User, Doctor.user_id == User.id)
            .where(User.is_active.is_(True))
            .order_by(Doctor.full_name.asc())
        )
    ).scalars().all()
    return [DoctorOption(id=doctor.id, full_name=doctor.full_name, specialty=doctor.specialty) for doctor in rows]


def _slot_occupied(slot: datetime, occupied: list[datetime]) -> bool:
    return any(abs((slot - moment).total_seconds()) < SLOT_MINUTES * 60 for moment in occupied)


@router.get("/availability", response_model=AppointmentAvailabilityResponse)
async def availability(
    doctor_id: int,
    date: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> AppointmentAvailabilityResponse:
    """Horarios libres del médico y del paciente para una fecha."""
    doctor = await _active_doctor(db, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Médico no disponible")

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Fecha inválida")

    patient = await get_patient_for_user(db, current_user)
    now_local = datetime.now(CLINIC_TIMEZONE)
    if target_date < now_local.date() or target_date > now_local.date() + timedelta(days=MAX_DAYS_AHEAD):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Elige una fecha entre hoy y {MAX_DAYS_AHEAD} días.",
        )
    if target_date.weekday() == 6:
        return AppointmentAvailabilityResponse(doctor_id=doctor.id, date=target_date, slots=[])

    start_local = datetime.combine(target_date, time.min, tzinfo=CLINIC_TIMEZONE)
    end_local = datetime.combine(target_date, time.max, tzinfo=CLINIC_TIMEZONE)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    rows = (
        await db.execute(
            select(Appointment).where(
                Appointment.scheduled_at >= start_utc,
                Appointment.scheduled_at <= end_utc,
                Appointment.status != AppointmentStatus.CANCELLED,
            )
        )
    ).scalars().all()
    doctor_occupied = [
        appointment.scheduled_at
        for appointment in rows
        if appointment.doctor_id == doctor.id
    ]
    patient_occupied = [
        appointment.scheduled_at
        for appointment in rows
        if appointment.patient_id == patient.id
    ]

    slots: list[AppointmentAvailabilitySlot] = []
    cursor = datetime.combine(target_date, time(8, 0), tzinfo=CLINIC_TIMEZONE)
    limit = datetime.combine(target_date, time(19, 0), tzinfo=CLINIC_TIMEZONE)
    while cursor <= limit:
        if cursor > now_local:
            doctor_busy = _slot_occupied(cursor, doctor_occupied)
            patient_busy = _slot_occupied(cursor, patient_occupied)
            slots.append(
                AppointmentAvailabilitySlot(
                    time=cursor.strftime("%H:%M"),
                    scheduled_at=cursor.astimezone(timezone.utc),
                    available=not doctor_busy and not patient_busy,
                )
            )
        cursor += timedelta(minutes=SLOT_MINUTES)

    return AppointmentAvailabilityResponse(doctor_id=doctor.id, date=target_date, slots=slots)


@router.post("/requests", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def request_appointment(
    payload: AppointmentRequestCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> AppointmentResponse:
    """Crea una solicitud de cita; recepción la confirma después."""
    if rate_limit.exceeded("api-appointment-request", request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Espera un minuto.",
            headers={"Retry-After": "60"},
        )

    patient = await get_patient_for_user(db, current_user)
    doctor = await _active_doctor(db, payload.doctor_id)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Médico no disponible")

    now_local = datetime.now(CLINIC_TIMEZONE)
    if payload.date < now_local.date() or payload.date > now_local.date() + timedelta(days=MAX_DAYS_AHEAD):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Elige una fecha entre hoy y {MAX_DAYS_AHEAD} días.",
        )
    if payload.date.weekday() == 6:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La clínica no agenda domingos.")
    if payload.time.minute not in (0, 30) or not (time(8, 0) <= payload.time <= time(19, 0)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Elige un horario entre 08:00 y 19:00, en intervalos de 30 minutos.",
        )

    scheduled_local = datetime.combine(payload.date, payload.time, tzinfo=CLINIC_TIMEZONE)
    if scheduled_local <= now_local:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Elige un horario futuro.")

    # La especialidad la manda el catálogo del médico, no el cliente: así un
    # paciente no puede etiquetar una cita con un servicio distinto.
    specialty = (doctor.specialty or payload.specialty).strip()
    if not 3 <= len(specialty) <= 120:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Especialidad inválida.")

    try:
        appointment = await create_appointment(
            db,
            patient=patient,
            doctor=doctor,
            specialty=specialty,
            scheduled_at=scheduled_local.astimezone(timezone.utc),
            location="Por asignar",
            notes=(payload.reason or "").strip() or "Solicitud enviada desde la app",
            status=AppointmentStatus.REQUESTED,
        )
    except AppointmentError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))

    await write_audit_event(
        db,
        user=current_user,
        action="patient_request_appointment",
        entity_type="appointment",
        entity_id=appointment.id,
        request=request,
        detail=f"doctor_id={doctor.id} scheduled={scheduled_local.isoformat(timespec='minutes')}",
    )
    await db.commit()
    await db.refresh(appointment)
    return appointment_response(appointment, doctor)
