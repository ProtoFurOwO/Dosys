"""Agenda de citas del hospital."""

import secrets
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus
from app.models.patient import Patient

# Sin caracteres confundibles (0/O, 1/I) porque el paciente puede escribirlo a mano.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_checkin_code() -> str:
    """Código de respaldo del QR de check-in, distinto en cada cita."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


async def create_appointment(
    db: AsyncSession,
    *,
    patient: Patient,
    doctor: Doctor | None,
    specialty: str,
    scheduled_at: datetime,
    location: str,
    notes: str | None,
) -> Appointment:
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id if doctor else None,
        specialty=specialty.strip(),
        scheduled_at=scheduled_at,
        location=location.strip(),
        status=AppointmentStatus.SCHEDULED,
        checkin_code=generate_checkin_code(),
        notes=notes.strip() if notes and notes.strip() else None,
    )
    db.add(appointment)
    await db.flush()
    return appointment
