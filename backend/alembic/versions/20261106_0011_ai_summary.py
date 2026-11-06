"""Resumen del expediente con IA: tabla de resúmenes y permiso ai:summary.

Revision ID: 20261106_0011
Revises: 20261105_0010
Create Date: 2026-11-06

Nota: escrita a prueba de reintentos — la tabla se crea solo si no existe y el
permiso se inserta solo si falta, para que funcione en el VPS sin reiniciar la
base ni repetir el sembrado.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261106_0011"
down_revision: Union[str, Sequence[str], None] = "20261105_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "ai_summaries" not in tables:
        op.create_table(
            "ai_summaries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("patient_id", sa.Integer(), nullable=False),
            sa.Column("input_hash", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=80), nullable=False),
            sa.Column("content", sa.JSON(), nullable=False),
            sa.Column("records_count", sa.Integer(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("patient_id", "input_hash", "model", name="uq_ai_summaries_patient_input_model"),
        )
        op.create_index("ix_ai_summaries_patient_id", "ai_summaries", ["patient_id"])
        op.create_index("ix_ai_summaries_created_by_user_id", "ai_summaries", ["created_by_user_id"])

    # Permiso nuevo para bases ya existentes: se asigna a los roles que ya
    # podían ver el expediente clínico completo. No se toca nada si ya existe.
    op.execute(
        """
        INSERT INTO permissions (code, area, action, description)
        SELECT 'ai:summary', 'Expediente', 'lectura', 'Generar resumen del expediente con IA'
        WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'ai:summary')
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.code IN ('admin', 'doctor')
          AND p.code = 'ai:summary'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'ai:summary')
        """
    )
    op.execute("DELETE FROM permissions WHERE code = 'ai:summary'")

    if "ai_summaries" in tables:
        op.drop_index("ix_ai_summaries_created_by_user_id", table_name="ai_summaries")
        op.drop_index("ix_ai_summaries_patient_id", table_name="ai_summaries")
        op.drop_table("ai_summaries")
