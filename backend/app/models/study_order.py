from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import StudyOrderStatus

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.lab_study import LabStudy


class StudyOrder(Base):
    """Orden de estudio: la pide un médico y la realiza el laboratorio."""

    __tablename__ = "study_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False)
    study_id: Mapped[int] = mapped_column(ForeignKey("lab_studies.id", ondelete="RESTRICT"), index=True, nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"), index=True, nullable=False)
    consultation_id: Mapped[int | None] = mapped_column(
        ForeignKey("consultations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    status: Mapped[StudyOrderStatus] = mapped_column(
        Enum(
            StudyOrderStatus,
            name="study_order_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=StudyOrderStatus.REQUESTED,
        nullable=False,
    )
    indications: Mapped[str | None] = mapped_column(String(200), nullable=True)
    result_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    study: Mapped[LabStudy] = relationship(lazy="joined")
    document: Mapped[Document | None] = relationship(lazy="joined")
