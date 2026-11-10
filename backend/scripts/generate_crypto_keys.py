"""Genera las llaves de criptografía de D.O.S.Y.S.

Uso desde ``backend/``:

    py -3.12 scripts/generate_crypto_keys.py --write-env

Crea:
- una llave AES-256 aleatoria para ``DATA_ENCRYPTION_KEY``;
- un par Ed25519; la llave privada se guarda en ``.env`` codificada en base64;
- la llave pública en ``secrets/documents_signing_public.pem`` (no es secreta).

El script no sobrescribe llaves existentes: si ya hay datos cifrados, cambiarlas
los volvería ilegibles. Para rotarlas hace falta un proceso de recifrado.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"
PUBLIC_KEY_PATH = BACKEND_DIR / "secrets" / "documents_signing_public.pem"


def generate_data_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")


def generate_private_key_b64() -> tuple[str, str, str]:
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_b64 = base64.urlsafe_b64encode(private_pem).decode("ascii")
    fingerprint = hashlib.sha256(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    ).hexdigest()
    return private_b64, public_pem.decode("ascii"), fingerprint


def read_env(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def key_exists(lines: list[str], key: str) -> bool:
    prefix = f"{key}="
    return any(line.strip().startswith(prefix) and line.split("=", 1)[1].strip() for line in lines)


def upsert_env(lines: list[str], values: dict[str, str]) -> list[str]:
    result = []
    remaining = dict(values)
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0] if "=" in stripped else ""
        if key in remaining:
            result.append(f"{key}={remaining.pop(key)}")
        else:
            result.append(line)
    if remaining:
        if result and result[-1].strip():
            result.append("")
        result.extend(f"{key}={value}" for key, value in remaining.items())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera las llaves de criptografía de D.O.S.Y.S.")
    parser.add_argument("--write-env", action="store_true", help="Actualiza backend/.env con las llaves.")
    parser.add_argument(
        "--public-key-out",
        type=Path,
        default=PUBLIC_KEY_PATH,
        help="Ruta de la llave pública PEM.",
    )
    args = parser.parse_args()

    lines = read_env(ENV_PATH)
    if key_exists(lines, "DATA_ENCRYPTION_KEY") or key_exists(lines, "DOCUMENTS_SIGNING_PRIVATE_KEY_B64"):
        print(
            "Ya existen llaves en .env. No se sobrescriben para no volver ilegibles "
            "los datos cifrados ni invalidar las firmas.",
            file=sys.stderr,
        )
        return 1

    data_key = generate_data_key()
    private_b64, public_pem, fingerprint = generate_private_key_b64()

    print("Agrega estas variables a backend/.env (o usa --write-env):")
    print(f"DATA_ENCRYPTION_KEY={data_key}")
    print(f"DOCUMENTS_SIGNING_PRIVATE_KEY_B64={private_b64}")
    print()
    print("Llave pública (se puede compartir):")
    print(public_pem)
    print("Huella SHA-256 de la llave pública:", fingerprint)

    args.public_key_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_key_out.write_text(public_pem, encoding="utf-8")
    print("Llave pública escrita en:", args.public_key_out)

    if args.write_env:
        ENV_PATH.write_text(
            "\n".join(upsert_env(lines, {
                "DATA_ENCRYPTION_KEY": data_key,
                "DOCUMENTS_SIGNING_PRIVATE_KEY_B64": private_b64,
            })) + "\n",
            encoding="utf-8",
        )
        print("Variables agregadas a:", ENV_PATH)
        try:
            ENV_PATH.chmod(0o600)
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
