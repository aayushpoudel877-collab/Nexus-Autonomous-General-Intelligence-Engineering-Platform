"""Govern versioned, content-addressed grounding calibration baselines."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from services.rag.calibration_report_diff import compare_reports

MANIFEST_SCHEMA_VERSION = 1


def canonical_json(value: Any) -> bytes:
    """Serialize JSON deterministically and reject non-finite numbers."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def validate_report(report: Any) -> dict[str, Any]:
    """Validate a calibration report using the same contract as report comparison."""
    compare_reports(report, report)
    return report


def build_manifest(report: Any, *, version: int, reason: str) -> dict[str, Any]:
    """Build an immutable-by-convention baseline manifest around a validated report."""
    validate_report(report)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("baseline version must be a positive integer")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("baseline approval reason must be a non-empty string")
    case_results = report.get("case_results")
    case_ids = sorted(item["case_id"] for item in case_results) if case_results is not None else None
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "baseline_version": version,
        "report_sha256": sha256_json(report),
        "case_set_sha256": sha256_json(case_ids) if case_ids is not None else None,
        "approval_reason": reason.strip(),
        "report": report,
    }


def validate_manifest(manifest: Any) -> dict[str, Any]:
    """Validate manifest shape, embedded report, content hash, and case-set hash."""
    if not isinstance(manifest, dict):
        raise TypeError("baseline manifest must be a JSON object")
    schema_version = manifest.get("manifest_schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != MANIFEST_SCHEMA_VERSION
    ):
        raise ValueError("unsupported baseline manifest schema version")
    version = manifest.get("baseline_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("baseline_version must be a positive integer")
    reason = manifest.get("approval_reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("approval_reason must be a non-empty string")
    report = validate_report(manifest.get("report"))
    expected_report_hash = sha256_json(report)
    if manifest.get("report_sha256") != expected_report_hash:
        raise ValueError("baseline report SHA-256 does not match embedded report")
    case_results = report.get("case_results")
    case_ids = sorted(item["case_id"] for item in case_results) if case_results is not None else None
    expected_case_hash = sha256_json(case_ids) if case_ids is not None else None
    if manifest.get("case_set_sha256") != expected_case_hash:
        raise ValueError("baseline case-set SHA-256 does not match embedded report")
    return manifest


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Read and validate a baseline manifest from disk."""
    source = Path(path)
    try:
        manifest = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read baseline manifest {source}: {exc}") from exc
    return validate_manifest(manifest)


def file_sha256(path: str | Path) -> str:
    """Hash the exact bytes currently stored at a path for optimistic concurrency."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
