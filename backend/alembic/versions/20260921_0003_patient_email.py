"""Correo de contacto del paciente.

Revision ID: 20260921_0003
Revises: 20260921_0002
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260921_0003"
down_revision: Union[str, Sequence[str], None] = "20260921_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("email", sa.String(length=160), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "email")
