import hashlib

import pytest

from services.api.app.services.artifact_store import ArtifactStore


def test_artifact_store_round_trip(tmp_path):
    store = ArtifactStore(str(tmp_path), max_bytes=1024)
    data = b"verified plugin bytes"
    digest = hashlib.sha256(data).hexdigest()

    assert store.put_verified(data, digest) == digest
    assert store.read_verified(digest) == data
    assert store.path_for(digest).exists()


def test_artifact_store_rejects_digest_mismatch(tmp_path):
    store = ArtifactStore(str(tmp_path), max_bytes=1024)

    with pytest.raises(ValueError, match="expected SHA-256"):
        store.put_verified(b"wrong", "a" * 64)


def test_artifact_store_rejects_oversized_artifacts(tmp_path):
    store = ArtifactStore(str(tmp_path), max_bytes=4)

    with pytest.raises(ValueError, match="exceeds"):
        store.put_verified(b"12345", hashlib.sha256(b"12345").hexdigest())


def test_artifact_store_rejects_tampered_content(tmp_path):
    store = ArtifactStore(str(tmp_path), max_bytes=1024)
    data = b"verified plugin bytes"
    digest = hashlib.sha256(data).hexdigest()
    store.put_verified(data, digest)
    store.path_for(digest).write_bytes(b"tampered")

    with pytest.raises(ValueError, match="failed SHA-256"):
        store.read_verified(digest)
