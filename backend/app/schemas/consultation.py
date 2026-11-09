from datetime import datetime

from pydantic import BaseModel, Field


class ConsultationCreateRequest(BaseModel):
    patient_id: int = Field(gt=0, examples=[1])
    reason: str = Field(min_length=3, max_length=300, examples=["Control de presión arterial"])
    diagnosis: str = Field(min_length=3, max_length=500, examples=["Hipertensión arterial en control"])
    notes: str | None = Field(default=None, max_length=4000)


class ConsultationResponse(BaseModel):
    id: int
    patient_id: int
    doctor_name: str
    specialty: str
    reason: str
    diagnosis: str
    notes: str | None
    blood_pressure: str | None = None
    heart_rate: int | None = None
    respiratory_rate: int | None = None
    temperature_c: float | None = None
    oxygen_saturation: int | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    physical_exam: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
