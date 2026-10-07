from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.document import Document


class Prescription(Base):
    """Receta médica emitida en una consulta."""

    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"), index=True, nullable=False)
    consultation_id: Mapped[int | None] = mapped_column(
        ForeignKey("consultations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    items: Mapped[list[PrescriptionItem]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan", lazy="selectin"
    )
    document: Mapped[Document | None] = relationship()


class PrescriptionItem(Base):
    """Medicamento de la receta con su dosis y duración."""

    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    medication: Mapped[str] = mapped_column(String(120), nullable=False)
    dose: Mapped[str] = mapped_column(String(80), nullable=False)
    frequency: Mapped[str] = mapped_column(String(80), nullable=False)
    duration: Mapped[str | None] = mapped_column(String(80), nullable=True)

    prescription: Mapped[Prescription] = relationship(back_populates="items")
