"""Safe, bounded serialization for tool-output provenance.

This module intentionally serializes metadata only. It never returns raw tool text,
and the digest is an integrity checksum—not proof of origin, truth, or safety.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
_ALLOWED_MARKERS = frozenset({
    "instruction_override",
    "prompt_or_secret_disclosure",
    "tool_misuse",
    "safety_bypass",
    "external_exfiltration",
})
MAX_PROVENANCE_RECORDS = 12
MAX_OUTPUT_CHARS = 20_000
MAX_EVIDENCE_IDS = 100


@dataclass(frozen=True, slots=True)
class ToolOutputProvenance:
    """Metadata-only representation suitable for controlled API/audit integration."""

    tool_name: str
    content_sha256: str
    detector_version: str
    injection_markers: tuple[str, ...]
    output_chars: int
    evidence_count: int
    untrusted: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly metadata object without source text or evidence IDs."""
        value = asdict(self)
        value["injection_markers"] = list(self.injection_markers)
        return value


def build_tool_output_provenance(record: Any) -> ToolOutputProvenance:
    """Validate an execution record and project it to a safe metadata-only contract."""
    tool_name = getattr(record, "tool_name", None)
    text = getattr(record, "text", None)
    digest = getattr(record, "content_sha256", None)
    detector_version = getattr(record, "detector_version", None)
    markers = getattr(record, "injection_markers", None)
    output_chars = getattr(record, "output_chars", None)
    evidence_ids = getattr(record, "evidence_ids", None)
    untrusted = getattr(record, "untrusted", None)

    if not isinstance(tool_name, str) or not _IDENTIFIER.fullmatch(tool_name):
        raise ValueError("tool_name must be a valid bounded identifier")
    if not isinstance(text, str) or len(text) > MAX_OUTPUT_CHARS:
        raise ValueError("tool output text must be a bounded string")
    expected_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest) or digest != expected_digest:
        raise ValueError("content_sha256 does not match the exact UTF-8 tool output")
    if not isinstance(detector_version, str) or not _VERSION.fullmatch(detector_version):
        raise ValueError("detector_version must be a bounded version identifier")
    if not isinstance(markers, tuple) or any(
        not isinstance(marker, str) or marker not in _ALLOWED_MARKERS for marker in markers
    ):
        raise ValueError("injection_markers contains an unsupported marker")
    if len(markers) != len(set(markers)):
        raise ValueError("injection_markers must be unique")
    if isinstance(output_chars, bool) or not isinstance(output_chars, int) or output_chars != len(text):
        raise ValueError("output_chars must match the exact tool output length")
    if not isinstance(evidence_ids, tuple) or len(evidence_ids) > MAX_EVIDENCE_IDS:
        raise ValueError("evidence_ids must be a bounded tuple")
    if any(not isinstance(item, str) or not item.strip() for item in evidence_ids):
        raise ValueError("evidence_ids must contain non-empty strings")
    if untrusted is not True:
        raise ValueError("tool output provenance must remain explicitly untrusted")

    return ToolOutputProvenance(
        tool_name=tool_name,
        content_sha256=digest,
        detector_version=detector_version,
        injection_markers=tuple(sorted(markers)),
        output_chars=output_chars,
        evidence_count=len(evidence_ids),
        untrusted=True,
    )


def build_provenance_batch(records: tuple[Any, ...]) -> tuple[ToolOutputProvenance, ...]:
    """Validate a bounded batch while preserving execution order."""
    if not isinstance(records, tuple):
        raise TypeError("records must be a tuple")
    if len(records) > MAX_PROVENANCE_RECORDS:
        raise ValueError("provenance batch exceeds the configured record limit")
    return tuple(build_tool_output_provenance(record) for record in records)
