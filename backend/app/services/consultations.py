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
    blood_pressure: str | None = None,
    heart_rate: int | None = None,
    respiratory_rate: int | None = None,
    temperature_c: float | None = None,
    oxygen_saturation: int | None = None,
    weight_kg: float | None = None,
    height_cm: float | None = None,
    physical_exam: str | None = None,
) -> Consultation:
    """Crea la consulta con las mismas reglas, venga de la API o del portal."""
    consultation = Consultation(
        patient_id=patient.id,
        doctor_id=doctor.id,
        reason=reason.strip(),
        diagnosis=diagnosis.strip(),
        notes=notes.strip() if notes and notes.strip() else None,
        blood_pressure=blood_pressure,
        heart_rate=heart_rate,
        respiratory_rate=respiratory_rate,
        temperature_c=temperature_c,
        oxygen_saturation=oxygen_saturation,
        weight_kg=weight_kg,
        height_cm=height_cm,
        physical_exam=physical_exam.strip() if physical_exam and physical_exam.strip() else None,
    )
    db.add(consultation)
    await db.flush()
    return consultation
