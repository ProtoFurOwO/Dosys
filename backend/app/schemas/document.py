from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    original_name: str
    content_type: str
    size_bytes: int
    sha256: str
    signature: str | None = None
    created_at: datetime


class DocumentIntegrityResponse(BaseModel):
    """Resultado detallado de verificar un documento en la app del paciente."""

    id: int
    intact: bool
    hash_ok: bool
    seal_ok: bool
    signature_ok: bool
    signature_algorithm: str = "Ed25519"
    public_key_fingerprint: str = ""
    registered_signature: str = ""
    current_signature: str = ""
    message: str
