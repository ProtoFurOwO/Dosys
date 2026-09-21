"""Check-in de citas con QR (módulo de cámara del celular).

Revision ID: 20260921_0002
Revises: 20260920_0001
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260921_0002"
down_revision: Union[str, Sequence[str], None] = "20260920_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("checkin_code", sa.String(length=32), nullable=True))
    op.add_column("appointments", sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "checked_in_at")
    op.drop_column("appointments", "checkin_code")
