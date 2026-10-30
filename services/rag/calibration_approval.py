"""Create and verify review records binding approved calibration baselines to provenance."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from services.rag.calibration_baseline import sha256_json, validate_manifest
from services.rag.calibration_provenance import validate_attestation

APPROVAL_SCHEMA_VERSION = 1


def _validate_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("reviewed_at must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("reviewed_at must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("reviewed_at must include a timezone offset")
    return value


def _approval_payload(
    manifest: dict[str, Any],
    attestation: dict[str, Any],
    *,
    reviewer_id: str,
    review_reason: str,
    reviewed_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "decision": "approved",
        "baseline_version": manifest["baseline_version"],
        "baseline_manifest_sha256": sha256_json(manifest),
        "report_sha256": manifest["report_sha256"],
        "provenance_attestation_sha256": sha256_json(attestation),
        "source_revision": attestation["source_revision"],
        "evaluator": attestation["evaluator"],
        "reviewer_id": reviewer_id.strip(),
        "review_reason": review_reason.strip(),
        "reviewed_at": _validate_timestamp(reviewed_at),
    }


def build_approval_record(
    manifest: Any,
    attestation: Any,
    *,
    reviewer_id: str,
    review_reason: str,
    reviewed_at: str,
) -> dict[str, Any]:
    """Bind a reviewed baseline to provenance; reviewer identity is caller-asserted."""
    checked_manifest = validate_manifest(manifest)
    checked_attestation = validate_attestation(attestation, checked_manifest["report"])
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise ValueError("reviewer_id must be a non-empty identifier")
    if not isinstance(review_reason, str) or not review_reason.strip():
        raise ValueError("review_reason must be a non-empty explanation")
    payload = _approval_payload(
        checked_manifest,
        checked_attestation,
        reviewer_id=reviewer_id,
        review_reason=review_reason,
        reviewed_at=reviewed_at,
    )
    return {**payload, "approval_record_sha256": sha256_json(payload)}


def validate_approval_record(
    record: Any,
    manifest: Any,
    attestation: Any,
) -> dict[str, Any]:
    """Verify record integrity and its links to the exact manifest and attestation."""
    if not isinstance(record, dict):
        raise TypeError("approval record must be a JSON object")
    checked_manifest = validate_manifest(manifest)
    checked_attestation = validate_attestation(attestation, checked_manifest["report"])
    required = ("reviewer_id", "review_reason", "reviewed_at")
    for field in required:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"approval record {field} must be a non-empty string")
    expected = _approval_payload(
        checked_manifest,
        checked_attestation,
        reviewer_id=record["reviewer_id"],
        review_reason=record["review_reason"],
        reviewed_at=record["reviewed_at"],
    )
    if record.get("schema_version") != APPROVAL_SCHEMA_VERSION:
        raise ValueError("unsupported approval record schema_version")
    if record.get("decision") != "approved":
        raise ValueError("approval record decision must be approved")
    if record.get("approval_record_sha256") != sha256_json(expected):
        raise ValueError("approval record SHA-256 does not match its contents")
    if record != {**expected, "approval_record_sha256": sha256_json(expected)}:
        raise ValueError("approval record does not match supplied manifest and attestation")
    return record
