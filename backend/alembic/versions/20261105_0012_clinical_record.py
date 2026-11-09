"""Datos clínicos del paciente y corrección de consultas.

Añade al expediente las alergias, los antecedentes y los diagnósticos
crónicos, y marca cuándo se corrigió una consulta ya registrada.

Revision ID: 20261105_0012
Revises: 20261105_0011
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261105_0012"
down_revision: Union[str, Sequence[str], None] = "20261105_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    patient_columns = _columns(bind, "patients")
    if "allergies" not in patient_columns:
        op.add_column("patients", sa.Column("allergies", sa.Text(), nullable=True))
    if "medical_history" not in patient_columns:
        op.add_column("patients", sa.Column("medical_history", sa.Text(), nullable=True))
    if "chronic_conditions" not in patient_columns:
        op.add_column("patients", sa.Column("chronic_conditions", sa.Text(), nullable=True))

    consultation_columns = _columns(bind, "consultations")
    if "updated_at" not in consultation_columns:
        op.add_column(
            "consultations",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()

    consultation_columns = _columns(bind, "consultations")
    if "updated_at" in consultation_columns:
        op.drop_column("consultations", "updated_at")

    patient_columns = _columns(bind, "patients")
    for column in ("chronic_conditions", "medical_history", "allergies"):
        if column in patient_columns:
            op.drop_column("patients", column)
