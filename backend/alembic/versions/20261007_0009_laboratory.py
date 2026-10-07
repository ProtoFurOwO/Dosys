"""Laboratorio (catálogo, órdenes), recetas, consultorio y vínculo consulta-cita.

Revision ID: 20261007_0009
Revises: 20261005_0008
Create Date: 2026-10-07

Nota: escrita a prueba de reintentos — cada objeto se crea solo si no existe,
y el tipo ENUM se maneja con ``create_type=False`` para no chocar cuando una
ejecución anterior lo dejó creado.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20261007_0009"
down_revision: Union[str, Sequence[str], None] = "20261005_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Consultorio asignado por recepción al confirmar la llegada.
    appointment_columns = {column["name"] for column in sa.inspect(bind).get_columns("appointments")}
    if "room" not in appointment_columns:
        op.add_column("appointments", sa.Column("room", sa.String(length=40), nullable=True))

    # La consulta puede quedar ligada a la cita que la originó.
    consultation_columns = {column["name"] for column in sa.inspect(bind).get_columns("consultations")}
    if "appointment_id" not in consultation_columns:
        op.add_column("consultations", sa.Column("appointment_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_consultations_appointment_id",
            "consultations",
            "appointments",
            ["appointment_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_consultations_appointment_id", "consultations", ["appointment_id"])

    tables = set(sa.inspect(bind).get_table_names())
    if "lab_studies" not in tables:
        op.create_table(
            "lab_studies",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=40), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("category", sa.String(length=40), nullable=False),
            sa.Column("description", sa.String(length=200), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        op.create_index("ix_lab_studies_code", "lab_studies", ["code"], unique=True)

    study_order_status = postgresql.ENUM(
        "requested",
        "in_progress",
        "completed",
        "cancelled",
        name="study_order_status",
        create_type=False,
    )
    study_order_status.create(bind, checkfirst=True)

    if "study_orders" not in tables:
        op.create_table(
            "study_orders",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("patient_id", sa.Integer(), nullable=False),
            sa.Column("study_id", sa.Integer(), nullable=False),
            sa.Column("doctor_id", sa.Integer(), nullable=False),
            sa.Column("consultation_id", sa.Integer(), nullable=True),
            sa.Column("status", study_order_status, nullable=False),
            sa.Column("indications", sa.String(length=200), nullable=True),
            sa.Column("result_text", sa.Text(), nullable=True),
            sa.Column("performed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("document_id", sa.Integer(), nullable=True),
            sa.Column(
                "requested_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("performed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["study_id"], ["lab_studies.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["performed_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_study_orders_patient_id", "study_orders", ["patient_id"])
        op.create_index("ix_study_orders_study_id", "study_orders", ["study_id"])
        op.create_index("ix_study_orders_doctor_id", "study_orders", ["doctor_id"])
        op.create_index("ix_study_orders_consultation_id", "study_orders", ["consultation_id"])
        op.create_index("ix_study_orders_performed_by_user_id", "study_orders", ["performed_by_user_id"])

    if "prescriptions" not in tables:
        op.create_table(
            "prescriptions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("patient_id", sa.Integer(), nullable=False),
            sa.Column("doctor_id", sa.Integer(), nullable=False),
            sa.Column("consultation_id", sa.Integer(), nullable=True),
            sa.Column("notes", sa.String(length=300), nullable=True),
            sa.Column("document_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
            ),
            sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_prescriptions_patient_id", "prescriptions", ["patient_id"])
        op.create_index("ix_prescriptions_doctor_id", "prescriptions", ["doctor_id"])
        op.create_index("ix_prescriptions_consultation_id", "prescriptions", ["consultation_id"])

    if "prescription_items" not in tables:
        op.create_table(
            "prescription_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("prescription_id", sa.Integer(), nullable=False),
            sa.Column("medication", sa.String(length=120), nullable=False),
            sa.Column("dose", sa.String(length=80), nullable=False),
            sa.Column("frequency", sa.String(length=80), nullable=False),
            sa.Column("duration", sa.String(length=80), nullable=True),
            sa.ForeignKeyConstraint(["prescription_id"], ["prescriptions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_prescription_items_prescription_id", "prescription_items", ["prescription_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "prescription_items" in tables:
        op.drop_index("ix_prescription_items_prescription_id", table_name="prescription_items")
        op.drop_table("prescription_items")
    if "prescriptions" in tables:
        op.drop_index("ix_prescriptions_consultation_id", table_name="prescriptions")
        op.drop_index("ix_prescriptions_doctor_id", table_name="prescriptions")
        op.drop_index("ix_prescriptions_patient_id", table_name="prescriptions")
        op.drop_table("prescriptions")
    if "study_orders" in tables:
        op.drop_index("ix_study_orders_performed_by_user_id", table_name="study_orders")
        op.drop_index("ix_study_orders_consultation_id", table_name="study_orders")
        op.drop_index("ix_study_orders_doctor_id", table_name="study_orders")
        op.drop_index("ix_study_orders_study_id", table_name="study_orders")
        op.drop_index("ix_study_orders_patient_id", table_name="study_orders")
        op.drop_table("study_orders")
    postgresql.ENUM(name="study_order_status", create_type=False).drop(bind, checkfirst=True)

    if "lab_studies" in tables:
        op.drop_index("ix_lab_studies_code", table_name="lab_studies")
        op.drop_table("lab_studies")

    consultation_columns = {column["name"] for column in sa.inspect(bind).get_columns("consultations")}
    if "appointment_id" in consultation_columns:
        op.drop_index("ix_consultations_appointment_id", table_name="consultations")
        op.drop_constraint("fk_consultations_appointment_id", "consultations", type_="foreignkey")
        op.drop_column("consultations", "appointment_id")

    appointment_columns = {column["name"] for column in sa.inspect(bind).get_columns("appointments")}
    if "room" in appointment_columns:
        op.drop_column("appointments", "room")
