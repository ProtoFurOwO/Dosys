"""Reglas de negocio compartidas entre la API y el portal clínico."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.patient import Patient


async def create_consultation(
    db: AsyncSession,
    *,
    doctor: Doctor,
    patient: Patient,
    reason: str,
    diagnosis: str,
    notes: str | None,
) -> Consultation:
    """Crea la consulta con las mismas reglas, venga de la API o del portal."""
    consultation = Consultation(
        patient_id=patient.id,
        doctor_id=doctor.id,
        reason=reason.strip(),
        diagnosis=diagnosis.strip(),
        notes=notes.strip() if notes and notes.strip() else None,
    )
    db.add(consultation)
    await db.flush()
    return consultation
