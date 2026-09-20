from enum import Enum


class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    LABORATORY = "laboratory"
    RECEPTION = "reception"


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    ATTENDED = "attended"
    CANCELLED = "cancelled"
