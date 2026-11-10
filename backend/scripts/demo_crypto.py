"""Demostración de los dos mecanismos criptográficos desde la base de datos.

Ejecutar dentro del contenedor de la API:

    docker compose exec api python scripts/demo_crypto.py

Muestra:
1. El dato clínico en claro que entrega el ORM.
2. El valor cifrado tal como está guardado en PostgreSQL.
3. El mismo dato descifrado correctamente.
4. La firma Ed25519 de un documento y su verificación con la llave pública.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select, text

from app.core.crypto import (
    decrypt_text,
    public_key_fingerprint,
    verify_document_signature,
)
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.patient import Patient
from app.services.documents import document_path, verify_document


async def main() -> None:
    async with SessionLocal() as db:
        patient = await db.scalar(select(Patient).order_by(Patient.id).limit(1))
        if patient is None:
            print("No hay pacientes; ejecuta el seed primero.")
            return

        raw = await db.scalar(
            text("SELECT allergies FROM patients WHERE id = :id"),
            {"id": patient.id},
        )
        print("== Mecanismo 1: AES-256-GCM ==")
        print("Texto claro que ve la app:", patient.allergies)
        print("Valor en PostgreSQL:", (raw or "")[:96], "…")
        print("Descifrado por la aplicación:", decrypt_text(raw))
        print()

        document = await db.scalar(select(Document).order_by(Document.id.desc()).limit(1))
        if document is None:
            print("No hay documentos firmados para demostrar.")
            return

        verification = verify_document(document)
        print("== Mecanismo 2: firma Ed25519 ==")
        print("Documento:", document.title, f"(id={document.id})")
        print("Archivo:", document_path(document).name)
        print("Huella SHA-256:", document.sha256)
        print("Firma registrada:", (document.signature or "")[:64], "…")
        print("¿Firma válida con la llave pública?", verification.signature_ok)
        print("¿Documento intacto?", verification.intact)
        print("Huella de la llave pública:", public_key_fingerprint())
        print(
            "Verificación independiente:",
            verify_document_signature(
                document_id=document.id,
                patient_id=document.patient_id,
                sha256=document.sha256,
                signature=document.signature,
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
