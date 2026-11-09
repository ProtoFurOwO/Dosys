"""Solicitudes de cita enviadas desde la app del paciente.

Agrega el estado ``requested`` al enum de citas. Una solicitud no genera QR ni
permite check-in hasta que recepción la confirma.

Revision ID: 20261109_0014
Revises: 20261109_0013
Create Date: 2026-11-09
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20261109_0014"
down_revision: Union[str, Sequence[str], None] = "20261109_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE appointment_status ADD VALUE IF NOT EXISTS 'requested'")


def downgrade() -> None:
    # PostgreSQL no elimina valores de un enum: se recrea el tipo. Las
    # solicitudes pendientes se convierten en canceladas para no perder filas.
    op.execute("UPDATE appointments SET status = 'cancelled' WHERE status = 'requested'")
    op.execute("ALTER TABLE appointments ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE appointment_status RENAME TO appointment_status_old")
    op.execute(
        "CREATE TYPE appointment_status AS ENUM "
        "('scheduled', 'confirmed', 'attended', 'cancelled')"
    )
    op.execute(
        "ALTER TABLE appointments ALTER COLUMN status TYPE appointment_status "
        "USING status::text::appointment_status"
    )
    op.execute("ALTER TABLE appointments ALTER COLUMN status SET DEFAULT 'scheduled'")
    op.execute("DROP TYPE appointment_status_old")
