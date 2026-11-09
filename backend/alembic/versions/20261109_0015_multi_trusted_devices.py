"""Permite varios dispositivos de confianza activos por paciente.

Elimina el índice único parcial que limitaba ``is_active`` a una sola fila por
usuario. El máximo de dispositivos se controla en la capa de servicio
(``MAX_TRUSTED_DEVICES``), no en la base.

Revision ID: 20261109_0015
Revises: 20261109_0014
Create Date: 2026-11-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261109_0015"
down_revision: Union[str, Sequence[str], None] = "20261109_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("uq_user_devices_active_per_user", table_name="user_devices")


def downgrade() -> None:
    # Antes de volver al modelo de un solo dispositivo, conserva el más
    # reciente activo de cada usuario y desactiva el resto.
    op.execute(
        """
        UPDATE user_devices AS d
        SET is_active = false
        WHERE d.is_active
          AND d.id NOT IN (
              SELECT DISTINCT ON (user_id) id
              FROM user_devices
              WHERE is_active
              ORDER BY user_id, created_at DESC, id DESC
          )
        """
    )
    op.create_index(
        "uq_user_devices_active_per_user",
        "user_devices",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
