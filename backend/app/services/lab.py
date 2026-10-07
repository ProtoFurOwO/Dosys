"""Órdenes de estudio: solicitud del médico, realización y resultado con huella."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.models.document import Document
from app.models.enums import StudyOrderStatus
from app.models.lab_study import LabStudy
from app.models.patient import Patient
from app.models.study_order import StudyOrder
from app.models.user import User
from app.services.documents import store_document_bytes
from app.services.reports import build_study_result_pdf


class LabError(ValueError):
    """Error de negocio mostrable en el portal."""


async def create_orders(
    db: AsyncSession,
    *,
    patient: Patient,
    doctor: Doctor,
    consultation_id: int | None,
    studies: list[LabStudy],
    indications: str | None,
) -> list[StudyOrder]:
    """Crea una orden por cada estudio seleccionado."""
    if not studies:
        raise LabError("Selecciona al menos un estudio.")
    clean_indications = (indications or "").strip()[:200] or None
    orders = []
    for study in studies:
        order = StudyOrder(
            patient_id=patient.id,
            study_id=study.id,
            doctor_id=doctor.id,
            consultation_id=consultation_id,
            status=StudyOrderStatus.REQUESTED,
            indications=clean_indications,
        )
        db.add(order)
        orders.append(order)
    await db.flush()
    return orders


async def complete_order(
    db: AsyncSession,
    *,
    order: StudyOrder,
    performed_by: User,
    result_text: str,
) -> Document:
    """Marca la orden como completada y guarda el PDF del resultado con huella."""
    text = (result_text or "").strip()
    if len(text) < 5:
        raise LabError("Escribe la conclusión del estudio (mínimo 5 caracteres).")
    if order.status == StudyOrderStatus.CANCELLED:
        raise LabError("Esta orden fue cancelada.")

    patient = await db.get(Patient, order.patient_id)
    doctor = await db.get(Doctor, order.doctor_id)
    study = await db.get(LabStudy, order.study_id)
    now = datetime.now(timezone.utc)

    data = build_study_result_pdf(
        patient_name=patient.full_name if patient else "Paciente",
        patient_curp=patient.curp if patient else "",
        study_name=study.name if study else "Estudio",
        doctor_name=doctor.full_name if doctor else "Médico",
        performer_name=performed_by.username,
        result_text=text,
        requested_at=order.requested_at,
        performed_at=now,
    )
    document = await store_document_bytes(
        db,
        patient=patient,
        uploader=performed_by,
        title=f"{study.name if study else 'Estudio'} · resultado",
        category="estudio",
        data=data,
        content_type="application/pdf",
        original_name=f"resultado-estudio-{order.id}.pdf",
    )

    order.result_text = text
    order.status = StudyOrderStatus.COMPLETED
    order.performed_by_user_id = performed_by.id
    order.performed_at = now
    order.document_id = document.id
    await db.flush()
    return document
