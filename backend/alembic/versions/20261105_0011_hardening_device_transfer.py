"""Endurecimiento de transferencia de sesión.

- Añade ``users.device_epoch``: invalida challenges 2FA emitidos antes de un
  cambio de dispositivo (transferencia, logout, liberación desde portal).
- Sustituye ``device_transfers.submitted_code`` (texto plano) por
  ``submitted_code_hash``: el servidor ya no guarda el código de 6 dígitos.

Revision ID: 20261105_0011
Revises: 20261105_0010
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261105_0011"
down_revision: Union[str, Sequence[str], None] = "20261105_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    user_columns = _columns(bind, "users")
    if "device_epoch" not in user_columns:
        op.add_column(
            "users",
            sa.Column("device_epoch", sa.Integer(), server_default=sa.text("0"), nullable=False),
        )

    transfer_columns = _columns(bind, "device_transfers")
    if transfer_columns:
        if "submitted_code_hash" not in transfer_columns:
            op.add_column(
                "device_transfers",
                sa.Column("submitted_code_hash", sa.String(length=64), nullable=True),
            )
        if "submitted_code" in transfer_columns:
            # Se descarta la propuesta pendiente: no se conserva texto plano.
            op.drop_column("device_transfers", "submitted_code")


def downgrade() -> None:
    bind = op.get_bind()

    transfer_columns = _columns(bind, "device_transfers")
    if transfer_columns:
        if "submitted_code" not in transfer_columns:
            op.add_column(
                "device_transfers",
                sa.Column("submitted_code", sa.String(length=6), nullable=True),
            )
        if "submitted_code_hash" in transfer_columns:
            op.drop_column("device_transfers", "submitted_code_hash")

    user_columns = _columns(bind, "users")
    if "device_epoch" in user_columns:
        op.drop_column("users", "device_epoch")
