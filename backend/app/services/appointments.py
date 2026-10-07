"""Agenda de citas del hospital."""

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus
from app.models.patient import Patient

# Sin caracteres confundibles (0/O, 1/I) porque el paciente puede escribirlo a mano.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# Dos citas separadas por menos de esta ventana se consideran empalmadas.
SLOT_MINUTES = 30


class AppointmentError(ValueError):
    """Choque de agenda mostrable en el portal."""


def generate_checkin_code() -> str:
    """Código de respaldo del QR de check-in, distinto en cada cita."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


async def ensure_available(
    db: AsyncSession,
    *,
    patient: Patient,
    doctor: Doctor | None,
    room: str | None,
    scheduled_at: datetime,
    ignore_id: int | None = None,
) -> None:
    """Bloquea empalmes de médico, paciente o consultorio en la misma ventana."""
    window = timedelta(minutes=SLOT_MINUTES)
    query = select(Appointment).where(
        Appointment.scheduled_at >= scheduled_at - window,
        Appointment.scheduled_at < scheduled_at + window,
        Appointment.status != AppointmentStatus.CANCELLED,
    )
    if ignore_id is not None:
        query = query.where(Appointment.id != ignore_id)
    clean_room = (room or "").strip() or None
    for other in (await db.scalars(query)).all():
        if other.patient_id == patient.id:
            raise AppointmentError("El paciente ya tiene otra cita en ese horario.")
        if doctor is not None and other.doctor_id == doctor.id:
            raise AppointmentError("El médico ya tiene otra cita en ese horario.")
        if clean_room and other.room == clean_room:
            raise AppointmentError(f"{clean_room} ya está ocupado en ese horario. Elige otro horario o consultorio.")


async def create_appointment(
    db: AsyncSession,
    *,
    patient: Patient,
    doctor: Doctor | None,
    specialty: str,
    scheduled_at: datetime,
    location: str,
    notes: str | None,
    room: str | None = None,
) -> Appointment:
    await ensure_available(db, patient=patient, doctor=doctor, room=room, scheduled_at=scheduled_at)
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id if doctor else None,
        specialty=specialty.strip(),
        scheduled_at=scheduled_at,
        location=location.strip(),
        room=(room or "").strip() or None,
        status=AppointmentStatus.SCHEDULED,
        checkin_code=generate_checkin_code(),
        notes=notes.strip() if notes and notes.strip() else None,
    )
    db.add(appointment)
    await db.flush()
    return appointment
