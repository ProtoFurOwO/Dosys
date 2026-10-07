"""Importa los modelos para que Alembic descubra toda la metadata."""

from app.db.session import Base
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.document import Document
from app.models.lab_study import LabStudy
from app.models.patient import Patient
from app.models.permission import Permission
from app.models.prescription import Prescription, PrescriptionItem
from app.models.recovery_code import RecoveryCode
from app.models.role import Role, role_permissions
from app.models.session_token import PasswordResetToken, RefreshToken
from app.models.study_order import StudyOrder
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Patient",
    "Doctor",
    "Consultation",
    "Appointment",
    "AuditLog",
    "RecoveryCode",
    "Role",
    "Permission",
    "role_permissions",
    "RefreshToken",
    "PasswordResetToken",
    "LabStudy",
    "StudyOrder",
    "Prescription",
    "PrescriptionItem",
]
