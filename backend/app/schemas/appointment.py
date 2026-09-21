from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AppointmentStatus


class AppointmentResponse(BaseModel):
    id: int
    specialty: str
    doctor_name: str | None
    scheduled_at: datetime
    location: str
    status: AppointmentStatus
    notes: str | None
    checked_in_at: datetime | None = None


class AppointmentCheckInRequest(BaseModel):
    """Código que el paciente escanea del QR de recepción (o escribe de respaldo)."""

    code: str = Field(min_length=4, max_length=32, examples=["A7K9M2"])
