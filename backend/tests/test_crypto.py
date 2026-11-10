"""Pruebas de los dos mecanismos criptográficos de D.O.S.Y.S."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select

from app.core.config import settings
from app.core.crypto import (
    CryptoConfigError,
    ENCRYPTED_PREFIX,
    decrypt_text,
    encrypt_text,
    generate_data_key,
    generate_signing_private_key_b64,
    public_key_fingerprint,
    sign_document,
    verify_document_signature,
)
from app.db.encrypted_text import EncryptedText
from app.models.document import Document
from app.services.documents import compute_seal, verify_document


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(settings, "data_encryption_key", generate_data_key())
    monkeypatch.setattr(
        settings,
        "documents_signing_private_key_b64",
        generate_signing_private_key_b64(),
    )


def test_aes_gcm_roundtrip_y_cifrado_distinto(keys):
    plaintext = "Penicilina (urticaria), polen"
    first = encrypt_text(plaintext)
    second = encrypt_text(plaintext)

    assert first is not None
    assert first.startswith(ENCRYPTED_PREFIX)
    assert plaintext not in first
    assert first != second  # nonce aleatorio por valor
    assert decrypt_text(first) == plaintext
    assert decrypt_text(second) == plaintext
    assert decrypt_text(first) == decrypt_text(first)  # idempotente


def test_aes_gcm_detecta_alteracion(keys):
    encrypted = encrypt_text("dato clínico")
    assert encrypted is not None

    payload = encrypted[len(ENCRYPTED_PREFIX) :]
    raw = bytearray(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    raw[-1] ^= 0x01
    tampered = ENCRYPTED_PREFIX + base64.urlsafe_b64encode(bytes(raw)).decode("ascii")

    with pytest.raises(ValueError):
        decrypt_text(tampered)


def test_encrypted_text_guarda_cifrado_en_la_base(keys):
    engine = create_engine("sqlite://")
    metadata = MetaData()
    table = Table(
        "secretos",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("valor", EncryptedText, nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(table.insert().values(id=1, valor="Hipertensión en control"))
        raw = connection.exec_driver_sql("SELECT valor FROM secretos").scalar_one()
        assert raw.startswith(ENCRYPTED_PREFIX)
        assert "Hipertensión" not in raw
        assert connection.execute(select(table.c.valor)).scalar_one() == "Hipertensión en control"


def test_falta_llave_simetrica_falla_claro(monkeypatch):
    monkeypatch.setattr(settings, "data_encryption_key", "")
    with pytest.raises(CryptoConfigError):
        encrypt_text("dato")


def test_ed25519_firma_y_verifica(keys):
    signature = sign_document(document_id=12, patient_id=3, sha256="a" * 64)

    assert verify_document_signature(
        document_id=12,
        patient_id=3,
        sha256="a" * 64,
        signature=signature,
    )
    assert not verify_document_signature(
        document_id=13,
        patient_id=3,
        sha256="a" * 64,
        signature=signature,
    )
    assert not verify_document_signature(
        document_id=12,
        patient_id=3,
        sha256="b" * 64,
        signature=signature,
    )
    assert not verify_document_signature(
        document_id=12,
        patient_id=3,
        sha256="a" * 64,
        signature="firma-invalida",
    )
    assert len(public_key_fingerprint()) == 64


def test_verificacion_de_documento_completa(keys, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "documents_dir", str(tmp_path))
    content = b"%PDF-1.4 documento de prueba"
    path = tmp_path / "documento.pdf"
    path.write_bytes(content)

    sha256 = __import__("hashlib").sha256(content).hexdigest()
    document = Document(
        id=7,
        patient_id=4,
        title="Biometría",
        category="estudio",
        original_name="biometria.pdf",
        content_type="application/pdf",
        size_bytes=len(content),
        sha256=sha256,
        seal=compute_seal(document_id=7, patient_id=4, sha256=sha256),
        signature=sign_document(document_id=7, patient_id=4, sha256=sha256),
        stored_name="documento.pdf",
    )

    verification = verify_document(document)
    assert verification.hash_ok
    assert verification.seal_ok
    assert verification.signature_ok
    assert verification.intact

    path.write_bytes(content + b" alterado")
    altered = verify_document(document)
    assert not altered.hash_ok
    assert not altered.intact
    assert altered.signature_ok  # la firma cubre el hash registrado, no el archivo actual

    document.signature = sign_document(document_id=8, patient_id=4, sha256=sha256)
    assert not verify_document(document).signature_ok
