"""Roles y permisos dinámicos.

Revision ID: 20260929_0005
Revises: 20260928_0004
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260929_0005"
down_revision: Union[str, Sequence[str], None] = "20260928_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_roles_code", "roles", ["code"], unique=False)

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("area", sa.String(length=40), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=160), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    op.add_column("users", sa.Column("role_id", sa.Integer(), nullable=True))

    # Los roles del sistema conservan los códigos que ya usaba la aplicación.
    op.execute(
        """
        INSERT INTO roles (code, name, description, is_system) VALUES
            ('admin', 'Administrador', 'Acceso completo al sistema', true),
            ('doctor', 'Médico', 'Atención clínica y expediente del paciente', true),
            ('laboratory', 'Laboratorio', 'Resultados y documentos de estudios', true),
            ('reception', 'Recepción', 'Agenda y registro de pacientes', true),
            ('patient', 'Paciente', 'Acceso a su propia información', true)
        """
    )
    op.execute(
        """
        UPDATE users
        SET role_id = (SELECT id FROM roles WHERE roles.code = users.role::text)
        """
    )
    op.alter_column("users", "role_id", nullable=False)
    op.create_foreign_key("fk_users_role_id", "users", "roles", ["role_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_users_role_id", "users", ["role_id"], unique=False)

    op.drop_column("users", "role")
    op.execute("DROP TYPE IF EXISTS user_role")


def downgrade() -> None:
    op.execute("CREATE TYPE user_role AS ENUM ('patient', 'doctor', 'laboratory', 'reception')")
    op.add_column(
        "users",
        sa.Column("role", sa.Enum("patient", "doctor", "laboratory", "reception", name="user_role"), nullable=True),
    )
    op.execute(
        """
        UPDATE users
        SET role = (SELECT code FROM roles WHERE roles.id = users.role_id)::user_role
        """
    )
    op.alter_column("users", "role", nullable=False)
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_constraint("fk_users_role_id", "users", type_="foreignkey")
    op.drop_column("users", "role_id")

    op.drop_table("role_permissions")
    op.drop_index("ix_permissions_code", table_name="permissions")
    op.drop_table("permissions")
    op.drop_index("ix_roles_code", table_name="roles")
    op.drop_table("roles")
