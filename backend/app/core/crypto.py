"""Criptografía de D.O.S.Y.S.

Dos mecanismos independientes:

1. **AES-256-GCM** para proteger datos clínicos sensibles en reposo. Se usa
   ``cryptography``; cada valor lleva un nonce aleatorio y la etiqueta de
   autenticación de GCM detecta cualquier alteración.
2. **Ed25519** para firmar digitalmente los documentos clínicos. El servidor
   firma un mensaje canónico con la llave privada y cualquier cliente puede
   verificar la firma con la llave pública.

Las llaves **no viven en el código**: se leen de variables de entorno
(``DATA_ENCRYPTION_KEY`` y ``DOCUMENTS_SIGNING_PRIVATE_KEY_B64``) que se
cargan desde ``backend/.env`` o desde el gestor de secretos del despliegue.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

ENCRYPTED_PREFIX = "enc:v1:"
SIGNATURE_CONTEXT = "DOSYS-DOC-v1"
SIGNATURE_ALGORITHM = "Ed25519"

_DATA_KEY_BYTES = 32
_NONCE_BYTES = 12
_TAG_BYTES = 16


class CryptoConfigError(RuntimeError):
    """Falta una llave o tiene un formato inválido."""


def _decode_b64(value: str, *, field: str) -> bytes:
    cleaned = "".join(value.split())
    if not cleaned:
        raise CryptoConfigError(f"Falta configurar {field}.")
    try:
        return base64.urlsafe_b64decode(cleaned + "=" * (-len(cleaned) % 4))
    except Exception as error:  # binascii.Error, ValueError
        raise CryptoConfigError(f"{field} no es base64 válido.") from error


def generate_data_key() -> str:
    """Genera una llave de 32 bytes codificada en base64url, sin relleno."""
    return base64.urlsafe_b64encode(os.urandom(_DATA_KEY_BYTES)).decode("ascii").rstrip("=")


def _data_key() -> bytes:
    key = _decode_b64(settings.data_encryption_key, field="DATA_ENCRYPTION_KEY")
    if len(key) != _DATA_KEY_BYTES:
        raise CryptoConfigError(
            "DATA_ENCRYPTION_KEY debe tener exactamente 32 bytes (AES-256)."
        )
    return key


def encrypt_text(plaintext: str | None) -> str | None:
    """Cifra un texto con AES-256-GCM y devuelve ``enc:v1:<base64>``.

    ``None`` y la cadena vacía se conservan para no inventar datos. Si el valor
    ya viene cifrado se deja intacto, lo que hace la operación idempotente.
    """
    if plaintext is None or plaintext == "":
        return plaintext
    if plaintext.startswith(ENCRYPTED_PREFIX):
        return plaintext

    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(_data_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{payload}"


def decrypt_text(value: str | None) -> str | None:
    """Descifra un valor producido por :func:`encrypt_text`.

    Los valores antiguos que aún no tienen el prefijo se devuelven tal cual para
    permitir una migración gradual. Un valor cifrado alterado lanza ``ValueError``
    (GCM no devuelve texto si la etiqueta no coincide).
    """
    if value is None or value == "" or not value.startswith(ENCRYPTED_PREFIX):
        return value

    raw = _decode_b64(value[len(ENCRYPTED_PREFIX) :], field="valor cifrado")
    if len(raw) < _NONCE_BYTES + _TAG_BYTES:
        raise ValueError("El valor cifrado está incompleto o fue alterado.")
    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    try:
        plaintext = AESGCM(_data_key()).decrypt(nonce, ciphertext, None)
    except InvalidTag as error:
        raise ValueError("No se pudo descifrar el valor: la etiqueta GCM no coincide.") from error
    return plaintext.decode("utf-8")


def generate_signing_private_key_b64() -> str:
    """Genera una llave privada Ed25519 en PEM, codificada en base64."""
    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.b64encode(pem).decode("ascii")


def _private_key() -> Ed25519PrivateKey:
    pem = _decode_b64(
        settings.documents_signing_private_key_b64,
        field="DOCUMENTS_SIGNING_PRIVATE_KEY_B64",
    )
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except Exception as error:
        raise CryptoConfigError(
            "DOCUMENTS_SIGNING_PRIVATE_KEY_B64 no contiene una llave PEM válida."
        ) from error
    if not isinstance(key, Ed25519PrivateKey):
        raise CryptoConfigError("La llave de firma debe ser Ed25519.")
    return key


def _public_key() -> Ed25519PublicKey:
    return _private_key().public_key()


def public_key_pem() -> str:
    """Llave pública en PEM; se puede distribuir sin riesgo."""
    pem = _public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem.decode("ascii")


def public_key_fingerprint() -> str:
    """Huella SHA-256 de la llave pública (DER), útil para mostrarla en la UI."""
    der = _public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()


def ensure_signing_configured() -> None:
    """Falla antes de escribir archivos si la llave privada no está configurada."""
    _private_key()


def document_signing_payload(*, document_id: int, patient_id: int, sha256: str) -> bytes:
    """Mensaje canónico que se firma; ata la firma al documento y al paciente."""
    return f"{SIGNATURE_CONTEXT}|{document_id}|{patient_id}|{sha256}".encode("utf-8")


def sign_document(*, document_id: int, patient_id: int, sha256: str) -> str:
    """Firma el documento con Ed25519 y devuelve la firma en base64url."""
    signature = _private_key().sign(
        document_signing_payload(
            document_id=document_id,
            patient_id=patient_id,
            sha256=sha256,
        )
    )
    return base64.urlsafe_b64encode(signature).decode("ascii")


def verify_document_signature(
    *, document_id: int, patient_id: int, sha256: str, signature: str | None
) -> bool:
    """Verifica una firma usando únicamente la llave pública.

    Devuelve ``False`` si falta la firma, si fue alterada o si la llave no está
    configurada; el llamador decide cómo mostrarlo.
    """
    if not signature:
        return False
    try:
        raw = _decode_b64(signature, field="firma del documento")
        _public_key().verify(
            raw,
            document_signing_payload(
                document_id=document_id,
                patient_id=patient_id,
                sha256=sha256,
            ),
        )
        return True
    except (InvalidSignature, CryptoConfigError, ValueError):
        return False
