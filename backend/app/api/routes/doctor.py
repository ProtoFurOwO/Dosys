from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.consultation import ConsultationCreateRequest, ConsultationResponse
from app.schemas.patient import DoctorPatientSummary
from app.services.audit import write_audit_event
from app.services.consultations import create_consultation as create_consultation_record


router = APIRouter(prefix="/doctor", tags=["Médico"])


async def get_doctor_for_user(db: AsyncSession, user: User) -> Doctor:
    doctor = await db.scalar(select(Doctor).where(Doctor.user_id == user.id))
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de médico no encontrado")
    return doctor


@router.get("/patients", response_model=list[DoctorPatientSummary])
async def list_patients(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("patients:read")),
) -> list[DoctorPatientSummary]:
    patients = (await db.scalars(select(Patient).order_by(Patient.full_name.asc()))).all()
    await write_audit_event(
        db,
        user=current_user,
        action="list_patients",
        entity_type="patient",
        entity_id=None,
        request=request,
    )
    await db.commit()
    return [
        DoctorPatientSummary(
            id=patient.id,
            full_name=patient.full_name,
            curp=patient.curp,
            blood_type=patient.blood_type,
        )
        for patient in patients
    ]


@router.post("/consultations", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED)
async def create_consultation(
    payload: ConsultationCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("consultations:write")),
) -> ConsultationResponse:
    """Primer flujo médico funcional: registra una consulta para un paciente."""
    doctor = await get_doctor_for_user(db, current_user)
    patient = await db.get(Patient, payload.patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")

    consultation = await create_consultation_record(
        db,
        doctor=doctor,
        patient=patient,
        reason=payload.reason,
        diagnosis=payload.diagnosis,
        notes=payload.notes,
    )
    await write_audit_event(
        db,
        user=current_user,
        action="create_consultation",
        entity_type="consultation",
        entity_id=consultation.id,
        request=request,
        detail=f"patient_id={patient.id}",
    )
    await db.commit()
    await db.refresh(consultation)

    return ConsultationResponse(
        id=consultation.id,
        patient_id=consultation.patient_id,
        doctor_name=doctor.full_name,
        specialty=doctor.specialty,
        reason=consultation.reason,
        diagnosis=consultation.diagnosis,
        notes=consultation.notes,
        created_at=consultation.created_at,
    )
