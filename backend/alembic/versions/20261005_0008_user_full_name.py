"""Nombre completo de la cuenta (para el personal sin ficha de médico).

Revision ID: 20261005_0008
Revises: 20261004_0007
Create Date: 2026-10-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261005_0008"
down_revision: Union[str, Sequence[str], None] = "20261004_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=160), nullable=True))
    # Rellena el nombre desde la ficha que ya lo tenga (médicos o pacientes).
    op.execute(
        """
        UPDATE users
        SET full_name = (SELECT doctors.full_name FROM doctors WHERE doctors.user_id = users.id)
        WHERE full_name IS NULL
        """
    )
    op.execute(
        """
        UPDATE users
        SET full_name = (SELECT patients.full_name FROM patients WHERE patients.user_id = users.id)
        WHERE full_name IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("users", "full_name")
