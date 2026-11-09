from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.document import Document
from app.models.enums import AppointmentStatus, UserRole
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.study_order import StudyOrder
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCheckInByCodeRequest,
    AppointmentCheckInRequest,
    AppointmentResponse,
)
from app.schemas.consultation import ConsultationResponse
from app.schemas.document import DocumentIntegrityResponse, DocumentResponse
from app.schemas.laboratory import PrescriptionItemResponse, PrescriptionResponse, StudyOrderResponse
from app.schemas.patient import PatientProfileResponse
from app.services import checkin, rate_limit
from app.services.audit import write_audit_event
from app.services.documents import check_integrity, document_path


router = APIRouter(prefix="/patients", tags=["Paciente"])


async def get_patient_for_user(db: AsyncSession, user: User) -> Patient:
    patient = await db.scalar(select(Patient).where(Patient.user_id == user.id))
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de paciente no encontrado")
    return patient


def appointment_response(appointment: Appointment, doctor: Doctor | None) -> AppointmentResponse:
    """Arma la cita con su estado de vigencia y su ventana de check-in."""
    now = datetime.now(timezone.utc)
    scheduled = appointment.scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    is_upcoming = (
        scheduled >= now
        and appointment.status
        in (
            AppointmentStatus.REQUESTED,
            AppointmentStatus.SCHEDULED,
            AppointmentStatus.CONFIRMED,
        )
    )
    return AppointmentResponse(
        id=appointment.id,
        specialty=appointment.specialty,
        doctor_name=doctor.full_name if doctor else None,
        scheduled_at=appointment.scheduled_at,
        location=appointment.location,
        status=appointment.status,
        notes=appointment.notes,
        checked_in_at=appointment.checked_in_at,
        is_upcoming=is_upcoming,
        **checkin.window_payload(appointment, now=now),
    )


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
            blood_pressure=consultation.blood_pressure,
            heart_rate=consultation.heart_rate,
            respiratory_rate=consultation.respiratory_rate,
            temperature_c=consultation.temperature_c,
            oxygen_saturation=consultation.oxygen_saturation,
            weight_kg=consultation.weight_kg,
            height_cm=consultation.height_cm,
            physical_exam=consultation.physical_exam,
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


@router.get("/me/studies", response_model=list[StudyOrderResponse])
async def get_my_studies(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> list[StudyOrderResponse]:
    """Estudios solicitados al paciente y el documento del resultado cuando está listo."""
    patient = await get_patient_for_user(db, current_user)
    orders = (
        await db.scalars(
            select(StudyOrder)
            .where(StudyOrder.patient_id == patient.id)
            .order_by(StudyOrder.requested_at.desc())
        )
    ).all()
    await write_audit_event(
        db,
        user=current_user,
        action="read_studies",
        entity_type="patient",
        entity_id=patient.id,
        request=request,
    )
    await db.commit()
    return [
        StudyOrderResponse(
            id=order.id,
            study_name=order.study.name,
            category=order.study.category,
            status=order.status.value,
            requested_at=order.requested_at,
            performed_at=order.performed_at,
            document_id=order.document_id,
        )
        for order in orders
    ]


@router.get("/me/prescriptions", response_model=list[PrescriptionResponse])
async def get_my_prescriptions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> list[PrescriptionResponse]:
    """Recetas emitidas al paciente con sus medicamentos y el PDF firmado."""
    patient = await get_patient_for_user(db, current_user)
    prescriptions = (
        await db.scalars(
            select(Prescription)
            .where(Prescription.patient_id == patient.id)
            .order_by(Prescription.created_at.desc())
        )
    ).all()
    await write_audit_event(
        db,
        user=current_user,
        action="read_prescriptions",
        entity_type="patient",
        entity_id=patient.id,
        request=request,
    )
    await db.commit()
    return [
        PrescriptionResponse(
            id=prescription.id,
            created_at=prescription.created_at,
            notes=prescription.notes,
            document_id=prescription.document_id,
            items=[
                PrescriptionItemResponse(
                    medication=item.medication,
                    dose=item.dose,
                    frequency=item.frequency,
                    duration=item.duration,
                )
                for item in prescription.items
            ],
        )
        for prescription in prescriptions
    ]


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
        appointment_response(appointment, doctor)
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


@router.get("/me/documents", response_model=list[DocumentResponse])
async def get_my_documents(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> list[DocumentResponse]:
    """Documentos del expediente visibles para el paciente (solo lectura)."""
    patient = await get_patient_for_user(db, current_user)
    documents = (
        await db.scalars(
            select(Document).where(Document.patient_id == patient.id).order_by(Document.created_at.desc())
        )
    ).all()

    await write_audit_event(
        db,
        user=current_user,
        action="read_documents",
        entity_type="patient",
        entity_id=patient.id,
        request=request,
    )
    await db.commit()
    return [DocumentResponse.model_validate(document) for document in documents]


@router.get("/me/documents/{document_id}/file")
async def download_my_document(
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
):
    patient = await get_patient_for_user(db, current_user)
    document = await db.scalar(
        select(Document).where(Document.id == document_id, Document.patient_id == patient.id)
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")

    path = document_path(document)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="El archivo ya no está disponible")

    await write_audit_event(
        db,
        user=current_user,
        action="download_document",
        entity_type="document",
        entity_id=document.id,
        request=request,
    )
    await db.commit()
    return FileResponse(path, media_type=document.content_type, filename=document.original_name)


@router.get("/me/documents/{document_id}/verify", response_model=DocumentIntegrityResponse)
async def verify_my_document(
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> DocumentIntegrityResponse:
    """Verifica la firma electrónica del documento sin exponer otros archivos."""
    patient = await get_patient_for_user(db, current_user)
    document = await db.scalar(
        select(Document).where(Document.id == document_id, Document.patient_id == patient.id)
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")

    intact, current_signature = check_integrity(document)
    await write_audit_event(
        db,
        user=current_user,
        action="verify_document",
        entity_type="document",
        entity_id=document.id,
        request=request,
        detail="resultado=intacto" if intact else "resultado=alterado",
    )
    await db.commit()
    return DocumentIntegrityResponse(
        id=document.id,
        intact=intact,
        registered_signature=document.sha256,
        current_signature=current_signature,
        message=(
            "Firma electrónica válida. El archivo no ha cambiado."
            if intact
            else "Documento alterado. La firma electrónica no coincide."
        ),
    )


async def _confirm_checkin(
    appointment: Appointment,
    patient: Patient,
    request: Request,
    db: AsyncSession,
    current_user: User,
) -> Appointment:
    """Valida la ventana y confirma la llegada una sola vez."""
    if appointment.checked_in_at is not None:
        return appointment

    error = checkin.check_in_error(appointment)
    if error:
        window = checkin.window_for(appointment)
        await write_audit_event(
            db,
            user=current_user,
            action="patient_checkin_out_of_window",
            entity_type="appointment",
            entity_id=appointment.id,
            request=request,
            detail=f"motivo={window.reason}",
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)

    appointment.checked_in_at = datetime.now(timezone.utc)
    if appointment.status == AppointmentStatus.SCHEDULED:
        appointment.status = AppointmentStatus.CONFIRMED
    await write_audit_event(
        db,
        user=current_user,
        action="patient_checkin",
        entity_type="appointment",
        entity_id=appointment.id,
        request=request,
        detail=f"patient_id={patient.id}",
    )
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.post("/me/appointments/{appointment_id}/check-in", response_model=AppointmentResponse)
async def check_in_appointment(
    appointment_id: int,
    payload: AppointmentCheckInRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> AppointmentResponse:
    """Confirma la llegada del paciente con el código del QR de recepción."""
    if rate_limit.exceeded("api-checkin", request, limit=10):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de check-in. Espera un minuto.",
            headers={"Retry-After": "60"},
        )

    patient = await get_patient_for_user(db, current_user)
    appointment = await db.scalar(
        select(Appointment).where(Appointment.id == appointment_id, Appointment.patient_id == patient.id)
    )
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada")

    if not appointment.checkin_code:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta cita todavía no tiene check-in habilitado",
        )

    if appointment.checkin_code.strip().upper() != payload.code.strip().upper():
        await write_audit_event(
            db,
            user=current_user,
            action="patient_checkin_failed",
            entity_type="appointment",
            entity_id=appointment.id,
            request=request,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código no corresponde a esta cita",
        )

    appointment = await _confirm_checkin(appointment, patient, request, db, current_user)
    doctor = await db.get(Doctor, appointment.doctor_id) if appointment.doctor_id else None
    return appointment_response(appointment, doctor)


@router.post("/me/check-in", response_model=AppointmentResponse)
async def check_in_with_code(
    payload: AppointmentCheckInByCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
) -> AppointmentResponse:
    """Check-in escribiendo solo el código: el servidor busca la cita vigente."""
    if rate_limit.exceeded("api-checkin", request, limit=10):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de check-in. Espera un minuto.",
            headers={"Retry-After": "60"},
        )

    patient = await get_patient_for_user(db, current_user)
    code = payload.code.strip().upper()
    rows = (
        await db.execute(
            select(Appointment, Doctor)
            .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
            .where(
                Appointment.patient_id == patient.id,
                Appointment.checkin_code.is_not(None),
                Appointment.status.not_in([AppointmentStatus.CANCELLED, AppointmentStatus.ATTENDED]),
            )
            .order_by(Appointment.scheduled_at.desc())
        )
    ).all()
    match = next(
        (
            (appointment, doctor)
            for appointment, doctor in rows
            if appointment.checkin_code and appointment.checkin_code.upper() == code
        ),
        None,
    )
    if match is None:
        await write_audit_event(
            db,
            user=current_user,
            action="patient_checkin_failed",
            entity_type="appointment",
            entity_id=None,
            request=request,
            detail="codigo_no_encontrado",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código no corresponde a ninguna cita vigente",
        )

    appointment, doctor = match
    appointment = await _confirm_checkin(appointment, patient, request, db, current_user)
    return appointment_response(appointment, doctor)
