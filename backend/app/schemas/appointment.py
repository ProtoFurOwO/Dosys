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
    # Calculados en el servidor para que la app no tenga que adivinar la
    # ventana de check-in ni si la cita ya pasó.
    is_upcoming: bool = False
    checkin_available: bool = False
    checkin_opens_at: datetime | None = None
    checkin_closes_at: datetime | None = None
    checkin_reason: str | None = None


class AppointmentCheckInRequest(BaseModel):
    """Código que el paciente escanea del QR de recepción (o escribe de respaldo)."""

    code: str = Field(min_length=4, max_length=32, examples=["A7K9M2"])


class AppointmentCheckInByCodeRequest(BaseModel):
    """Check-in con solo el código: el servidor busca la cita que corresponde."""

    code: str = Field(min_length=4, max_length=32, examples=["A7K9M2"])
