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


class DoctorPatientSummary(BaseModel):
    id: int
    full_name: str
    curp: str
    blood_type: str | None
