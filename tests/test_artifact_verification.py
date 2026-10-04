import base64
import hashlib

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.api.app.services.artifact_verification import (
    MAX_ARTIFACT_BYTES,
    decode_public_key,
    verify_artifact_bytes,
)


def _signed_artifact() -> tuple[bytes, str, str]:
    artifact = b"nexus-plugin-artifact"
    digest = hashlib.sha256(artifact).hexdigest()
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes_raw()
    signature = private_key.sign(digest.encode("ascii"))
    return (
        artifact,
        base64.b64encode(public_key).decode("ascii"),
        base64.b64encode(signature).decode("ascii"),
    )


def test_artifact_signature_verification_succeeds():
    artifact, public_key, signature = _signed_artifact()

    digest = verify_artifact_bytes(
        artifact_bytes=artifact,
        expected_sha256=hashlib.sha256(artifact).hexdigest(),
        signature=signature,
        public_key=public_key,
    )

    assert digest == hashlib.sha256(artifact).hexdigest()


def test_artifact_signature_verification_rejects_tampering():
    artifact, public_key, signature = _signed_artifact()

    with pytest.raises(ValueError, match="SHA-256"):
        verify_artifact_bytes(
            artifact_bytes=artifact + b"-tampered",
            expected_sha256=hashlib.sha256(artifact).hexdigest(),
            signature=signature,
            public_key=public_key,
        )


def test_artifact_verification_rejects_invalid_signature():
    artifact, public_key, _signature = _signed_artifact()
    private_key = Ed25519PrivateKey.generate()
    other_signature = base64.b64encode(
        private_key.sign(hashlib.sha256(artifact).hexdigest().encode("ascii"))
    ).decode("ascii")

    with pytest.raises(ValueError, match="signature is invalid"):
        verify_artifact_bytes(
            artifact_bytes=artifact,
            expected_sha256=hashlib.sha256(artifact).hexdigest(),
            signature=other_signature,
            public_key=public_key,
        )


def test_artifact_verification_rejects_oversized_input():
    with pytest.raises(ValueError, match="cannot exceed"):
        verify_artifact_bytes(
            artifact_bytes=b"x" * (MAX_ARTIFACT_BYTES + 1),
            expected_sha256="0" * 64,
            signature="AA==",
            public_key="AA==",
        )


def test_trust_root_public_key_must_be_ed25519_length():
    with pytest.raises(ValueError, match="32 bytes"):
        decode_public_key(base64.b64encode(b"short").decode("ascii"))
