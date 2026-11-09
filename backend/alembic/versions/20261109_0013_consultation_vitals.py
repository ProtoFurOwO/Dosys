"""Signos vitales y exploración física en la consulta.

Completa el expediente clínico con el bloque objetivo del SOAP: presión
arterial, frecuencia cardiaca y respiratoria, temperatura, saturación de
oxígeno, peso, talla y exploración física.

Revision ID: 20261109_0013
Revises: 20261105_0012
Create Date: 2026-11-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261109_0013"
down_revision: Union[str, Sequence[str], None] = "20261105_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_COLUMNS = {
    "blood_pressure": sa.Column("blood_pressure", sa.String(20), nullable=True),
    "heart_rate": sa.Column("heart_rate", sa.Integer(), nullable=True),
    "respiratory_rate": sa.Column("respiratory_rate", sa.Integer(), nullable=True),
    "temperature_c": sa.Column("temperature_c", sa.Float(), nullable=True),
    "oxygen_saturation": sa.Column("oxygen_saturation", sa.Integer(), nullable=True),
    "weight_kg": sa.Column("weight_kg", sa.Float(), nullable=True),
    "height_cm": sa.Column("height_cm", sa.Float(), nullable=True),
    "physical_exam": sa.Column("physical_exam", sa.Text(), nullable=True),
}


def _columns(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    existing = _columns(bind, "consultations")
    for name, column in NEW_COLUMNS.items():
        if name not in existing:
            op.add_column("consultations", column)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _columns(bind, "consultations")
    for name in reversed(tuple(NEW_COLUMNS)):
        if name in existing:
            op.drop_column("consultations", name)
