"""Cryptographic plugin artifact verification helpers."""

from __future__ import annotations

import base64
import binascii
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_ARTIFACT_BYTES = 6 * 1024 * 1024
MAX_BASE64_BYTES = 8_388_608


def decode_public_key(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Trust root public key must be valid base64") from exc
    if len(decoded) != 32:
        raise ValueError("Ed25519 public keys must decode to 32 bytes")
    return decoded


def decode_signature(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Plugin signature must be valid base64") from exc
    if len(decoded) != 64:
        raise ValueError("Ed25519 signatures must decode to 64 bytes")
    return decoded


def verify_artifact_bytes(
    *,
    artifact_bytes: bytes,
    expected_sha256: str,
    signature: str,
    public_key: str,
) -> str:
    if len(artifact_bytes) > MAX_ARTIFACT_BYTES:
        raise ValueError(
            f"Artifact verification input cannot exceed {MAX_ARTIFACT_BYTES} bytes"
        )

    digest = hashlib.sha256(artifact_bytes).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError("Artifact SHA-256 does not match the release digest")

    key = Ed25519PublicKey.from_public_bytes(decode_public_key(public_key))
    signature_bytes = decode_signature(signature)
    try:
        key.verify(signature_bytes, digest.encode("ascii"))
    except InvalidSignature as exc:
        raise ValueError("Artifact signature is invalid") from exc

    return digest
