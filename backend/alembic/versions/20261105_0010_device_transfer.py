"""Dispositivos de confianza y transferencia de sesión entre dispositivos.

Revision ID: 20261105_0010
Revises: 20261007_0009
Create Date: 2026-11-05

Nota: escrita a prueba de reintentos — cada objeto se crea solo si no existe y
el ENUM se maneja con ``create_type=False`` para no chocar cuando una ejecución
anterior lo dejó creado.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20261105_0010"
down_revision: Union[str, Sequence[str], None] = "20261007_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "user_devices" not in tables:
        op.create_table(
            "user_devices",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("device_hash", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("fcm_token", sa.String(length=255), nullable=True),
            sa.Column(
                "is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False
            ),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "device_hash", name="uq_user_devices_user_device"),
        )
        op.create_index("ix_user_devices_user_id", "user_devices", ["user_id"])
        # Un solo dispositivo activo por usuario (índice único parcial).
        op.create_index(
            "uq_user_devices_active_per_user",
            "user_devices",
            ["user_id"],
            unique=True,
            postgresql_where=sa.text("is_active"),
        )

    transfer_status = postgresql.ENUM(
        "pending",
        "code_submitted",
        "approved",
        "rejected",
        "failed",
        "expired",
        name="device_transfer_status",
        create_type=False,
    )
    transfer_status.create(bind, checkfirst=True)

    if "device_transfers" not in tables:
        op.create_table(
            "device_transfers",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("new_device_hash", sa.String(length=64), nullable=True),
            sa.Column("new_device_name", sa.String(length=120), nullable=False),
            sa.Column("status", transfer_status, nullable=False),
            sa.Column("approval_token_hash", sa.String(length=64), nullable=False),
            sa.Column("submitted_code", sa.String(length=6), nullable=True),
            sa.Column("code_submissions", sa.Integer(), server_default="0", nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_device_transfers_user_id", "device_transfers", ["user_id"])

    refresh_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("refresh_tokens")
    }
    if "device_id" not in refresh_columns:
        op.add_column(
            "refresh_tokens", sa.Column("device_id", sa.Integer(), nullable=True)
        )
        op.create_foreign_key(
            "fk_refresh_tokens_device_id",
            "refresh_tokens",
            "user_devices",
            ["device_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_refresh_tokens_device_id", "refresh_tokens", ["device_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    refresh_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("refresh_tokens")
    }
    if "device_id" in refresh_columns:
        op.drop_index("ix_refresh_tokens_device_id", table_name="refresh_tokens")
        op.drop_constraint("fk_refresh_tokens_device_id", "refresh_tokens", type_="foreignkey")
        op.drop_column("refresh_tokens", "device_id")

    if "device_transfers" in tables:
        op.drop_index("ix_device_transfers_user_id", table_name="device_transfers")
        op.drop_table("device_transfers")

    if "user_devices" in tables:
        op.drop_index("uq_user_devices_active_per_user", table_name="user_devices")
        op.drop_index("ix_user_devices_user_id", table_name="user_devices")
        op.drop_table("user_devices")

    postgresql.ENUM(name="device_transfer_status", create_type=False).drop(
        bind, checkfirst=True
    )
