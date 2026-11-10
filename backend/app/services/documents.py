"""Documentos clínicos.

Cada archivo se guarda en disco y su contenido se protege con dos valores:
- `sha256`: huella del archivo para detectar cualquier alteración posterior.
- `seal`: HMAC del identificador, la huella y el paciente, firmado por el servidor;
  impide que un cambio en la propia base de datos pase desapercibido.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import (
    CryptoConfigError,
    ensure_signing_configured,
    sign_document,
    verify_document_signature,
)
from app.models.document import Document
from app.models.patient import Patient
from app.models.user import User

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

CATEGORIES = (
    ("estudio", "Estudio de laboratorio o imagen"),
    ("receta", "Receta médica"),
    ("informe", "Informe o nota médica"),
    ("identificacion", "Identificación del paciente"),
    ("otro", "Otro documento"),
)


class DocumentError(ValueError):
    """Error de negocio mostrable al usuario."""


@dataclass(frozen=True)
class DocumentVerification:
    """Resultado de comprobar huella, sello HMAC y firma Ed25519."""

    hash_ok: bool
    seal_ok: bool
    signature_ok: bool
    current_sha256: str

    @property
    def intact(self) -> bool:
        return self.hash_ok and self.seal_ok and self.signature_ok


def documents_dir() -> Path:
    path = Path(settings.documents_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _signing_key() -> bytes:
    key = settings.documents_signing_key or settings.jwt_secret_key
    return key.encode("utf-8")


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_seal(*, document_id: int, patient_id: int, sha256: str) -> str:
    message = f"{document_id}:{patient_id}:{sha256}".encode("utf-8")
    return hmac.new(_signing_key(), message, hashlib.sha256).hexdigest()


async def store_document(
    db: AsyncSession,
    *,
    patient: Patient,
    uploader: User | None,
    title: str,
    category: str,
    upload: UploadFile,
) -> Document:
    content_type = (upload.content_type or "").lower()
    if content_type not in ALLOWED_TYPES:
        raise DocumentError("Solo se aceptan PDF, JPG, PNG o WEBP.")

    data = await upload.read()
    if not data:
        raise DocumentError("El archivo llegó vacío.")
    return await store_document_bytes(
        db,
        patient=patient,
        uploader=uploader,
        title=title,
        category=category,
        data=data,
        content_type=content_type,
        original_name=Path(upload.filename or "documento").name[:255],
    )


async def store_document_bytes(
    db: AsyncSession,
    *,
    patient: Patient,
    uploader: User | None,
    title: str,
    category: str,
    data: bytes,
    content_type: str,
    original_name: str,
) -> Document:
    """Guarda un archivo ya en memoria (subidas o PDF generados por el sistema).

    Devuelve el documento con su huella SHA-256 y el sello HMAC del servidor.
    """
    if content_type not in ALLOWED_TYPES:
        raise DocumentError("Solo se aceptan PDF, JPG, PNG o WEBP.")
    limit = settings.documents_max_mb * 1024 * 1024
    if not data:
        raise DocumentError("El archivo llegó vacío.")
    if len(data) > limit:
        raise DocumentError(f"El archivo supera el límite de {settings.documents_max_mb} MB.")

    try:
        ensure_signing_configured()
    except CryptoConfigError as error:
        raise DocumentError(
            "El servidor no tiene configurada la firma digital de documentos."
        ) from error

    sha256 = compute_sha256(data)
    stored_name = f"{secrets.token_hex(16)}{ALLOWED_TYPES[content_type]}"
    (documents_dir() / stored_name).write_bytes(data)

    document = Document(
        patient_id=patient.id,
        uploaded_by_user_id=uploader.id if uploader else None,
        title=title.strip(),
        category=category,
        original_name=original_name[:255],
        content_type=content_type,
        size_bytes=len(data),
        sha256=sha256,
        seal="",
        signature=None,
        stored_name=stored_name,
    )
    db.add(document)
    await db.flush()
    document.seal = compute_seal(document_id=document.id, patient_id=patient.id, sha256=sha256)
    try:
        document.signature = sign_document(
            document_id=document.id,
            patient_id=patient.id,
            sha256=sha256,
        )
    except CryptoConfigError as error:
        raise DocumentError(
            "El servidor no tiene configurada la firma digital de documentos."
        ) from error
    await db.flush()
    return document


def document_path(document: Document) -> Path:
    return documents_dir() / document.stored_name


def verify_document(document: Document) -> DocumentVerification:
    """Comprueba el archivo, el sello HMAC y la firma Ed25519."""
    path = document_path(document)
    current = compute_sha256(path.read_bytes()) if path.exists() else ""
    hash_ok = bool(current) and hmac.compare_digest(current, document.sha256)
    seal_ok = hmac.compare_digest(
        document.seal,
        compute_seal(document_id=document.id, patient_id=document.patient_id, sha256=document.sha256),
    )
    signature_ok = verify_document_signature(
        document_id=document.id,
        patient_id=document.patient_id,
        sha256=document.sha256,
        signature=document.signature,
    )
    return DocumentVerification(
        hash_ok=hash_ok,
        seal_ok=seal_ok,
        signature_ok=signature_ok,
        current_sha256=current,
    )


def check_integrity(document: Document) -> tuple[bool, str]:
    """Compatibilidad: devuelve (intacto, huella_actual)."""
    verification = verify_document(document)
    return verification.intact, verification.current_sha256


def human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / (1024 * 1024):.1f} MB"
