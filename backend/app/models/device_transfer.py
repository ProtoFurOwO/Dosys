from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import DeviceTransferStatus

if TYPE_CHECKING:
    from app.models.user import User


def _values(enum_class: type[DeviceTransferStatus]) -> list[str]:
    return [item.value for item in enum_class]


class DeviceTransfer(Base):
    """Solicitud de transferencia de sesión hacia un dispositivo nuevo.

    El servidor actúa solo como enrutador: nunca genera, compara ni conoce el
    código de 6 dígitos. ``submitted_code_hash`` es el hash SHA-256 de la
    propuesta que escribió el dispositivo nuevo; el dispositivo activo compara
    ese hash con el hash de su código local. Se borra al resolver la propuesta
    y al terminar la transferencia.
    """

    __tablename__ = "device_transfers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Nulo cuando el cliente nuevo no envió device_id (cliente antiguo).
    new_device_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_device_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[DeviceTransferStatus] = mapped_column(
        Enum(
            DeviceTransferStatus,
            name="device_transfer_status",
            values_callable=_values,
        ),
        nullable=False,
    )
    approval_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code_submissions: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()
