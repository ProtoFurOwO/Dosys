"""Esquemas de laboratorio y recetas para la app del paciente."""

from datetime import datetime

from pydantic import BaseModel


class StudyOrderResponse(BaseModel):
    id: int
    study_name: str
    category: str
    status: str
    requested_at: datetime
    performed_at: datetime | None = None
    document_id: int | None = None


class PrescriptionItemResponse(BaseModel):
    medication: str
    dose: str
    frequency: str
    duration: str | None = None


class PrescriptionResponse(BaseModel):
    id: int
    created_at: datetime
    notes: str | None = None
    document_id: int | None = None
    items: list[PrescriptionItemResponse]
