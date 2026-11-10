from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.encrypted_text import EncryptedText
from app.db.session import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.consultation import Consultation
    from app.models.user import User


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    curp: Mapped[str] = mapped_column(String(18), unique=True, index=True, nullable=False)
    blood_type: Mapped[str | None] = mapped_column(String(3), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)

    # Datos clínicos de alerta: se muestran en el expediente y en la app del
    # paciente. Se guardan cifrados con AES-256-GCM (ver app/db/encrypted_text.py);
    # el ORM los entrega en claro a la API y al portal.
    allergies: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    medical_history: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    chronic_conditions: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)

    user: Mapped[User] = relationship(back_populates="patient")
    consultations: Mapped[list[Consultation]] = relationship(back_populates="patient")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="patient")
