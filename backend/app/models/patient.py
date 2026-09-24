from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    user: Mapped[User] = relationship(back_populates="patient")
    consultations: Mapped[list[Consultation]] = relationship(back_populates="patient")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="patient")
