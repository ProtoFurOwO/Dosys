from enum import Enum


class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    LABORATORY = "laboratory"
    RECEPTION = "reception"


class AppointmentStatus(str, Enum):
    REQUESTED = "requested"
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    ATTENDED = "attended"
    CANCELLED = "cancelled"


class StudyOrderStatus(str, Enum):
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DeviceTransferStatus(str, Enum):
    """Estados de una transferencia de sesión entre dispositivos."""

    PENDING = "pending"
    CODE_SUBMITTED = "code_submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    EXPIRED = "expired"
