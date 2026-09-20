from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AppointmentStatus


class AppointmentResponse(BaseModel):
    id: int
    specialty: str
    doctor_name: str | None
    scheduled_at: datetime
    location: str
    status: AppointmentStatus
    notes: str | None
