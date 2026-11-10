"""Cifrado AES-256-GCM de datos clínicos y firma Ed25519 de documentos.

- Cifra en reposo ``allergies``, ``medical_history`` y ``chronic_conditions``
  de los pacientes existentes. Los valores nuevos se cifran en el ORM.
- Agrega ``documents.signature`` y firma los documentos ya registrados.

Las llaves se leen de ``DATA_ENCRYPTION_KEY`` y
``DOCUMENTS_SIGNING_PRIVATE_KEY_B64``. No se escriben en la migración.

Revision ID: 20261110_0014
Revises: 20261109_0013
Create Date: 2026-11-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.crypto import (
    CryptoConfigError,
    ENCRYPTED_PREFIX,
    decrypt_text,
    encrypt_text,
    sign_document,
)

revision: str = "20261110_0014"
down_revision: Union[str, Sequence[str], None] = "20261109_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PATIENT_FIELDS = ("allergies", "medical_history", "chronic_conditions")


def _columns(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _require_keys_for_rows() -> None:
    """Mensaje claro si falta configuración antes de cifrar datos existentes."""
    try:
        encrypt_text("prueba")
        sign_document(document_id=0, patient_id=0, sha256="0" * 64)
    except CryptoConfigError as error:
        raise RuntimeError(
            "Configura DATA_ENCRYPTION_KEY y DOCUMENTS_SIGNING_PRIVATE_KEY_B64 "
            "antes de ejecutar esta migración."
        ) from error


def upgrade() -> None:
    bind = op.get_bind()

    document_columns = _columns(bind, "documents")
    if "signature" not in document_columns:
        op.add_column("documents", sa.Column("signature", sa.String(128), nullable=True))

    patient_columns = _columns(bind, "patients")
    if all(field in patient_columns for field in PATIENT_FIELDS):
        rows = bind.execute(
            sa.text(
                "SELECT id, allergies, medical_history, chronic_conditions FROM patients"
            )
        ).mappings().all()
        if rows:
            _require_keys_for_rows()
        for row in rows:
            updates = {}
            for field in PATIENT_FIELDS:
                value = row[field]
                if value and not value.startswith(ENCRYPTED_PREFIX):
                    updates[field] = encrypt_text(value)
            if updates:
                assignments = ", ".join(f"{field} = :{field}" for field in updates)
                bind.execute(
                    sa.text(f"UPDATE patients SET {assignments} WHERE id = :id"),
                    {**updates, "id": row["id"]},
                )

    document_columns = _columns(bind, "documents")
    if {"id", "patient_id", "sha256", "signature"} <= document_columns:
        rows = bind.execute(
            sa.text(
                "SELECT id, patient_id, sha256 FROM documents WHERE signature IS NULL"
            )
        ).mappings().all()
        if rows:
            _require_keys_for_rows()
        for row in rows:
            signature = sign_document(
                document_id=row["id"],
                patient_id=row["patient_id"],
                sha256=row["sha256"],
            )
            bind.execute(
                sa.text("UPDATE documents SET signature = :signature WHERE id = :id"),
                {"signature": signature, "id": row["id"]},
            )


def downgrade() -> None:
    bind = op.get_bind()
    patient_columns = _columns(bind, "patients")
    if all(field in patient_columns for field in PATIENT_FIELDS):
        rows = bind.execute(
            sa.text(
                "SELECT id, allergies, medical_history, chronic_conditions FROM patients"
            )
        ).mappings().all()
        for row in rows:
            updates = {}
            for field in PATIENT_FIELDS:
                value = row[field]
                if value and value.startswith(ENCRYPTED_PREFIX):
                    updates[field] = decrypt_text(value)
            if updates:
                assignments = ", ".join(f"{field} = :{field}" for field in updates)
                bind.execute(
                    sa.text(f"UPDATE patients SET {assignments} WHERE id = :id"),
                    {**updates, "id": row["id"]},
                )

    document_columns = _columns(bind, "documents")
    if "signature" in document_columns:
        op.drop_column("documents", "signature")
