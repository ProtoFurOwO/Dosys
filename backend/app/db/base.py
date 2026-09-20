"""Importa los modelos para que Alembic descubra toda la metadata."""

from app.db.session import Base
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User

__all__ = ["Base", "User", "Patient", "Doctor", "Consultation", "Appointment", "AuditLog"]
