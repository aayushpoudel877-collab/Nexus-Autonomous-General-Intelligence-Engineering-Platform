"""Bounded integrity checks for RAG source artifacts.

This module deliberately verifies bytes supplied by a trusted storage adapter; it
does not fetch files, change document lifecycle state, or infer whether a mismatch
is malicious. Callers should record failures for human review.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from collections.abc import Iterable

MAX_ARTIFACT_BYTES = 25 * 1024 * 1024
MAX_BATCH_ITEMS = 500
SHA256_HEX_LENGTH = 64


@dataclass(frozen=True, slots=True)
class IntegrityReceipt:
    """Privacy-safe result for one stored artifact."""

    artifact_id: str
    expected_sha256: str
    observed_sha256: str | None
    status: str
    size_bytes: int | None
    reason: str | None = None


def _valid_digest(value: str) -> bool:
    return (
        len(value) == SHA256_HEX_LENGTH
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def verify_artifact(
    artifact_id: str,
    expected_sha256: str,
    content: bytes | None,
    *,
    max_bytes: int = MAX_ARTIFACT_BYTES,
) -> IntegrityReceipt:
    """Compare source bytes to a known SHA-256 digest without mutating state.

    Missing/unreadable bytes and invalid input are reported explicitly. Artifact
    content is never included in the receipt.
    """
    if not artifact_id or not artifact_id.strip():
        raise ValueError("artifact_id must not be blank")
    if not _valid_digest(expected_sha256):
        raise ValueError("expected_sha256 must be a 64-character SHA-256 hex digest")
    if max_bytes < 1 or max_bytes > MAX_ARTIFACT_BYTES:
        raise ValueError(f"max_bytes must be between 1 and {MAX_ARTIFACT_BYTES}")
    if content is None:
        return IntegrityReceipt(
            artifact_id, expected_sha256.lower(), None, "unavailable", None,
            "source_bytes_unavailable",
        )
    if not isinstance(content, bytes):
        raise TypeError("content must be bytes or None")
    if len(content) > max_bytes:
        return IntegrityReceipt(
            artifact_id, expected_sha256.lower(), None, "not_checked", len(content),
            "artifact_exceeds_size_limit",
        )

    observed = sha256(content).hexdigest()
    matches = observed == expected_sha256.lower()
    return IntegrityReceipt(
        artifact_id=artifact_id,
        expected_sha256=expected_sha256.lower(),
        observed_sha256=observed,
        status="verified" if matches else "mismatch",
        size_bytes=len(content),
        reason=None if matches else "sha256_mismatch",
    )


def verify_batch(
    artifacts: Iterable[tuple[str, str, bytes | None]],
    *,
    max_items: int = MAX_BATCH_ITEMS,
    max_bytes: int = MAX_ARTIFACT_BYTES,
) -> list[IntegrityReceipt]:
    """Verify a bounded batch of (artifact id, expected digest, bytes) tuples."""
    if max_items < 1 or max_items > MAX_BATCH_ITEMS:
        raise ValueError(f"max_items must be between 1 and {MAX_BATCH_ITEMS}")
    receipts: list[IntegrityReceipt] = []
    for artifact in artifacts:
        if len(receipts) >= max_items:
            raise ValueError("artifact batch exceeds max_items")
        if not isinstance(artifact, tuple) or len(artifact) != 3:
            raise ValueError("each artifact must be a (artifact_id, digest, bytes) tuple")
        artifact_id, expected_sha256, content = artifact
        receipts.append(
            verify_artifact(
                artifact_id, expected_sha256, content, max_bytes=max_bytes
            )
        )
    return receipts
