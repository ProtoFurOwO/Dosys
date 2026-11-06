from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class AiSummary(Base):
    """Resumen del expediente generado por un modelo de lenguaje.

    Guarda la entrada exacta (por su hash) para no volver a llamar al modelo si
    nada cambió. El contenido es solo texto de apoyo: no entra al expediente ni
    se muestra al paciente.
    """

    __tablename__ = "ai_summaries"
    __table_args__ = (
        UniqueConstraint("patient_id", "input_hash", "model", name="uq_ai_summaries_patient_input_model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    records_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    patient: Mapped[Patient] = relationship()
    created_by: Mapped[User | None] = relationship()
