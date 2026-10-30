"""Create and verify provenance attestations for grounding calibration reports."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from services.rag.calibration_baseline import sha256_json, validate_report

ATTESTATION_SCHEMA_VERSION = 1


def file_evidence(path: str | Path) -> dict[str, Any]:
    """Return a content hash and byte length for an input file."""
    source = Path(path)
    payload = source.read_bytes()
    return {"sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}


def build_attestation(
    report: Any,
    *,
    inputs: Mapping[str, str | Path],
    source_revision: str,
    evaluator: str,
) -> dict[str, Any]:
    """Bind a validated report to exact input bytes and the source revision."""
    validate_report(report)
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise ValueError("source_revision must be a non-empty commit or revision identifier")
    if not isinstance(evaluator, str) or not evaluator.strip():
        raise ValueError("evaluator must be a non-empty command or evaluator identifier")
    if not isinstance(inputs, Mapping) or not inputs:
        raise ValueError("at least one input file is required for provenance")
    evidence: dict[str, Any] = {}
    for label, path in sorted(inputs.items()):
        if not isinstance(label, str) or not label.strip():
            raise ValueError("input labels must be non-empty strings")
        evidence[label] = file_evidence(path)
    return {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "report_sha256": sha256_json(report),
        "source_revision": source_revision.strip(),
        "evaluator": evaluator.strip(),
        "inputs": evidence,
    }


def validate_attestation(attestation: Any, report: Any) -> dict[str, Any]:
    """Validate attestation structure and ensure it refers to this exact report."""
    validate_report(report)
    if not isinstance(attestation, dict):
        raise TypeError("provenance attestation must be a JSON object")
    if attestation.get("schema_version") != ATTESTATION_SCHEMA_VERSION:
        raise ValueError("unsupported provenance attestation schema_version")
    if attestation.get("report_sha256") != sha256_json(report):
        raise ValueError("provenance report SHA-256 does not match report")
    for field in ("source_revision", "evaluator"):
        value = attestation.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"provenance {field} must be a non-empty string")
    inputs = attestation.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("provenance inputs must be a non-empty object")
    for label, item in inputs.items():
        if not isinstance(label, str) or not label.strip() or not isinstance(item, dict):
            raise ValueError("provenance input entries must be named objects")
        digest, size = item.get("sha256"), item.get("size_bytes")
        if not isinstance(digest, str) or len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            raise ValueError(f"provenance input {label} has invalid SHA-256")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError(f"provenance input {label} has invalid size_bytes")
    return attestation


def verify_input_files(attestation: Mapping[str, Any], inputs: Mapping[str, str | Path]) -> None:
    """Raise when supplied files do not match the attested input labels or bytes."""
    expected = attestation["inputs"]
    if set(inputs) != set(expected):
        raise ValueError("supplied input labels do not match provenance attestation")
    for label, path in inputs.items():
        actual = file_evidence(path)
        if actual != expected[label]:
            raise ValueError(f"provenance input mismatch: {label}")
