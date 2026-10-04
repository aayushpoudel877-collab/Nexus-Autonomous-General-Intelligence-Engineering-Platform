"""Shared content-addressed storage for already-verified plugin artifacts."""

from __future__ import annotations

import hashlib
import os
from uuid import uuid4
from pathlib import Path


class ArtifactStore:
    def __init__(self, root: str, *, max_bytes: int) -> None:
        self.root = Path(root).resolve()
        self.max_bytes = max_bytes

    def _validate_digest(self, digest: str) -> str:
        normalized = digest.lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("Artifact storage keys must be SHA-256 digests")
        return normalized

    def path_for(self, digest: str) -> Path:
        normalized = self._validate_digest(digest)
        candidate = self.root / normalized[:2] / normalized[2:4] / normalized
        resolved_parent = candidate.parent.resolve()
        try:
            resolved_parent.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Artifact storage path escaped configured root") from exc
        return candidate

    def put_verified(self, artifact_bytes: bytes, expected_sha256: str) -> str:
        digest = hashlib.sha256(artifact_bytes).hexdigest()
        normalized = self._validate_digest(expected_sha256)
        if digest != normalized:
            raise ValueError("Artifact bytes do not match the expected SHA-256")
        if len(artifact_bytes) > self.max_bytes:
            raise ValueError(f"Artifact exceeds the configured {self.max_bytes}-byte limit")

        destination = self.path_for(normalized)
        destination.parent.mkdir(parents=True, exist_ok=True)
        existing = destination
        if existing.exists():
            if existing.is_symlink():
                raise ValueError("Artifact storage entry cannot be a symlink")
            if self.digest_file(existing) != normalized:
                raise ValueError("Existing artifact storage entry failed integrity verification")
            return normalized

        temp_path = destination.with_name(f".{normalized}.tmp-{os.getpid()}-{uuid4().hex}")
        with open(temp_path, "xb") as handle:
            handle.write(artifact_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
        return normalized

    def read_verified(self, digest: str) -> bytes:
        normalized = self._validate_digest(digest)
        path = self.path_for(normalized)
        if path.is_symlink():
            raise ValueError("Artifact storage entry cannot be a symlink")
        data = path.read_bytes()
        if len(data) > self.max_bytes:
            raise ValueError("Stored artifact exceeds the configured limit")
        if hashlib.sha256(data).hexdigest() != normalized:
            raise ValueError("Stored artifact failed SHA-256 integrity verification")
        return data

    @staticmethod
    def digest_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
