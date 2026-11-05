from datetime import date

from pydantic import BaseModel, ConfigDict


class PatientProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    curp: str
    blood_type: str | None
    birth_date: date | None
    emergency_contact: str | None
    allergies: str | None = None
    medical_history: str | None = None
    chronic_conditions: str | None = None


class DoctorPatientSummary(BaseModel):
    id: int
    full_name: str
    curp: str
    blood_type: str | None
