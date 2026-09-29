"""Documentos clínicos por paciente.

Revision ID: 20260929_0006
Revises: 20260929_0005
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260929_0006"
down_revision: Union[str, Sequence[str], None] = "20260929_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("seal", sa.String(length=64), nullable=False),
        sa.Column("stored_name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index("ix_documents_patient_id", "documents", ["patient_id"], unique=False)
    op.create_index("ix_documents_uploaded_by_user_id", "documents", ["uploaded_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_uploaded_by_user_id", table_name="documents")
    op.drop_index("ix_documents_patient_id", table_name="documents")
    op.drop_table("documents")
