from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.enums import UserRole
from app.models.patient import Patient
from app.models.user import User
from app.schemas.appointment import AppointmentResponse
from app.schemas.consultation import ConsultationResponse
from app.schemas.patient import PatientProfileResponse
from app.services.audit import write_audit_event


router = APIRouter(prefix="/patients", tags=["Paciente"])


async def get_patient_for_user(db: AsyncSession, user: User) -> Patient:
    patient = await db.scalar(select(Patient).where(Patient.user_id == user.id))
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de paciente no encontrado")
    return patient


@router.get("/me", response_model=PatientProfileResponse)
async def get_my_profile(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> Patient:
    patient = await get_patient_for_user(db, current_user)
    await write_audit_event(
        db,
        user=current_user,
        action="read_profile",
        entity_type="patient",
        entity_id=patient.id,
        request=request,
    )
    await db.commit()
    return patient


@router.get("/me/consultations", response_model=list[ConsultationResponse])
async def get_my_consultations(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> list[ConsultationResponse]:
    patient = await get_patient_for_user(db, current_user)
    result = await db.execute(
        select(Consultation, Doctor)
        .join(Doctor, Consultation.doctor_id == Doctor.id)
        .where(Consultation.patient_id == patient.id)
        .order_by(Consultation.created_at.desc())
    )
    consultations = [
        ConsultationResponse(
            id=consultation.id,
            patient_id=consultation.patient_id,
            doctor_name=doctor.full_name,
            specialty=doctor.specialty,
            reason=consultation.reason,
            diagnosis=consultation.diagnosis,
            notes=consultation.notes,
            created_at=consultation.created_at,
        )
        for consultation, doctor in result.all()
    ]
    await write_audit_event(
        db,
        user=current_user,
        action="read_consultations",
        entity_type="patient",
        entity_id=patient.id,
        request=request,
    )
    await db.commit()
    return consultations


@router.get("/me/appointments", response_model=list[AppointmentResponse])
async def get_my_appointments(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> list[AppointmentResponse]:
    patient = await get_patient_for_user(db, current_user)
    result = await db.execute(
        select(Appointment, Doctor)
        .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
        .where(Appointment.patient_id == patient.id)
        .order_by(Appointment.scheduled_at.asc())
    )
    appointments = [
        AppointmentResponse(
            id=appointment.id,
            specialty=appointment.specialty,
            doctor_name=doctor.full_name if doctor else None,
            scheduled_at=appointment.scheduled_at,
            location=appointment.location,
            status=appointment.status,
            notes=appointment.notes,
        )
        for appointment, doctor in result.all()
    ]
    await write_audit_event(
        db,
        user=current_user,
        action="read_appointments",
        entity_type="patient",
        entity_id=patient.id,
        request=request,
    )
    await db.commit()
    return appointments
