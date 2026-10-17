"""Privacy-safe observability and governance contracts for RAG.

These pure contracts deliberately do not emit telemetry or contact external indexes.
Callers must persist events and dispatch deletion work through an explicitly configured
backend. Raw query text, retrieved text, credentials, and source contents are never
accepted by the event builder.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_ALLOWED_EVENT_TYPES = {
    "retrieval.completed",
    "retrieval.abstained",
    "ingestion.completed",
    "ingestion.rejected",
    "document.deleted",
    "index.deletion.acknowledged",
}
_ALLOWED_OUTCOMES = {"success", "failure", "abstained", "rejected", "pending"}


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field} must be a bounded opaque identifier")
    return value


@dataclass(frozen=True)
class RAGAuditEvent:
    event_id: str
    event_type: str
    occurred_at: str
    organization_id: str
    actor_id: str | None
    resource_id: str | None
    outcome: str
    duration_ms: int | None
    evidence_count: int | None
    trace_id: str | None
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_audit_event(
    *,
    event_id: str,
    event_type: str,
    occurred_at: datetime,
    organization_id: str,
    outcome: str,
    actor_id: str | None = None,
    resource_id: str | None = None,
    duration_ms: int | None = None,
    evidence_count: int | None = None,
    trace_id: str | None = None,
) -> RAGAuditEvent:
    """Create an allowlisted event with no fields for user text or source contents."""
    if event_type not in _ALLOWED_EVENT_TYPES:
        raise ValueError("unsupported RAG audit event type")
    if outcome not in _ALLOWED_OUTCOMES:
        raise ValueError("unsupported RAG audit outcome")
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError("occurred_at must be timezone-aware")
    for field, value in (
        ("event_id", event_id),
        ("organization_id", organization_id),
        ("actor_id", actor_id),
        ("resource_id", resource_id),
        ("trace_id", trace_id),
    ):
        if value is not None:
            _identifier(value, field)
    if duration_ms is not None and (not isinstance(duration_ms, int) or isinstance(duration_ms, bool) or duration_ms < 0 or duration_ms > 86_400_000):
        raise ValueError("duration_ms is outside the supported range")
    if evidence_count is not None and (not isinstance(evidence_count, int) or isinstance(evidence_count, bool) or not 0 <= evidence_count <= 1000):
        raise ValueError("evidence_count is outside the supported range")
    return RAGAuditEvent(
        event_id=event_id,
        event_type=event_type,
        occurred_at=occurred_at.astimezone(timezone.utc).isoformat(),
        organization_id=organization_id,
        actor_id=actor_id,
        resource_id=resource_id,
        outcome=outcome,
        duration_ms=duration_ms,
        evidence_count=evidence_count,
        trace_id=trace_id,
    )


@dataclass(frozen=True)
class SourceLineage:
    organization_id: str
    document_id: str
    chunk_id: str
    content_sha256: str
    source_version: str
    parser_version: str
    indexed_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def build_source_lineage(
    *,
    organization_id: str,
    document_id: str,
    chunk_id: str,
    content_sha256: str,
    source_version: str,
    parser_version: str,
    indexed_at: datetime,
) -> SourceLineage:
    """Build provenance metadata without storing document text or source URLs."""
    for field, value in (
        ("organization_id", organization_id),
        ("document_id", document_id),
        ("chunk_id", chunk_id),
        ("source_version", source_version),
        ("parser_version", parser_version),
    ):
        _identifier(value, field)
    if not isinstance(content_sha256, str) or not _SHA256.fullmatch(content_sha256):
        raise ValueError("content_sha256 must be a lowercase SHA-256 digest")
    if indexed_at.tzinfo is None or indexed_at.utcoffset() is None:
        raise ValueError("indexed_at must be timezone-aware")
    return SourceLineage(
        organization_id=organization_id,
        document_id=document_id,
        chunk_id=chunk_id,
        content_sha256=content_sha256,
        source_version=source_version,
        parser_version=parser_version,
        indexed_at=indexed_at.astimezone(timezone.utc).isoformat(),
    )


@dataclass(frozen=True)
class IndexDeletionRequest:
    request_id: str
    idempotency_key: str
    organization_id: str
    document_id: str
    content_sha256: str
    requested_at: str
    status: str = "pending"
    attempts: int = 0


def build_index_deletion_request(
    *, organization_id: str, document_id: str, content_sha256: str, requested_at: datetime
) -> IndexDeletionRequest:
    """Create a deterministic, idempotent deletion-outbox contract."""
    _identifier(organization_id, "organization_id")
    _identifier(document_id, "document_id")
    if not isinstance(content_sha256, str) or not _SHA256.fullmatch(content_sha256):
        raise ValueError("content_sha256 must be a lowercase SHA-256 digest")
    if requested_at.tzinfo is None or requested_at.utcoffset() is None:
        raise ValueError("requested_at must be timezone-aware")
    canonical = f"rag-index-delete:v1:{organization_id}:{document_id}:{content_sha256}"
    key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return IndexDeletionRequest(
        request_id=key[:32],
        idempotency_key=key,
        organization_id=organization_id,
        document_id=document_id,
        content_sha256=content_sha256,
        requested_at=requested_at.astimezone(timezone.utc).isoformat(),
    )


def acknowledge_deletion(request: IndexDeletionRequest, *, attempts: int = 1) -> IndexDeletionRequest:
    """Return a validated acknowledgement snapshot; caller persists it atomically."""
    if request.status not in {"pending", "failed"}:
        raise ValueError("only pending or failed deletion requests can be acknowledged")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or not 1 <= attempts <= 1000:
        raise ValueError("attempts must be between 1 and 1000")
    return IndexDeletionRequest(**{**asdict(request), "status": "acknowledged", "attempts": attempts})


@dataclass(frozen=True)
class RetentionPolicy:
    event_days: int = 90
    trace_days: int = 14
    lineage_days: int = 365
    delete_source_on_request: bool = True

    def __post_init__(self) -> None:
        for name in ("event_days", "trace_days", "lineage_days"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 3650:
                raise ValueError(f"{name} must be between 1 and 3650 days")
        if not isinstance(self.delete_source_on_request, bool):
            raise TypeError("delete_source_on_request must be boolean")


def retention_expired(*, created_at: datetime, now: datetime, retention_days: int) -> bool:
    """Evaluate expiry deterministically; no deletion is performed by this helper."""
    if created_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("created_at and now must be timezone-aware")
    if not isinstance(retention_days, int) or isinstance(retention_days, bool) or not 1 <= retention_days <= 3650:
        raise ValueError("retention_days must be between 1 and 3650 days")
    return now.astimezone(timezone.utc) >= created_at.astimezone(timezone.utc) + timedelta(days=retention_days)


@dataclass(frozen=True)
class RAGModelCard:
    model_name: str
    model_version: str
    intended_use: str
    limitations: str
    evaluation_dataset: str
    evaluation_date: str
    owner: str
    approval_status: str = "draft"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def validate_model_card(card: RAGModelCard) -> RAGModelCard:
    """Validate documentation completeness; approval remains a human governance action."""
    for field in ("model_name", "model_version", "intended_use", "limitations", "evaluation_dataset", "evaluation_date", "owner"):
        value = getattr(card, field)
        if not isinstance(value, str) or not value.strip() or len(value) > 2000:
            raise ValueError(f"{field} must be non-empty and at most 2000 characters")
    if card.approval_status not in {"draft", "review", "approved", "rejected"}:
        raise ValueError("unsupported model-card approval status")
    try:
        datetime.fromisoformat(card.evaluation_date)
    except ValueError as exc:
        raise ValueError("evaluation_date must be ISO-8601") from exc
    return card


def stable_json(value: Any) -> str:
    """Serialize contract objects deterministically for audit/outbox persistence."""
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def build_tool_provenance_audit_details(records: tuple[Any, ...]) -> dict[str, Any]:
    """Build a bounded, metadata-only audit detail payload from tool execution records.

    The caller remains responsible for authenticated tenant scoping, transaction handling,
    persistence, retention, and access control. Raw tool output and evidence IDs are never
    included in this payload.
    """
    from .provenance import build_provenance_batch

    provenance = build_provenance_batch(records)
    return {
        "schema_version": 1,
        "tool_outputs": [item.to_dict() for item in provenance],
    }

_AUDIT_ENVELOPE_KEYS = frozenset({"schema_version", "tool_outputs", "payload_sha256"})


def seal_tool_provenance_audit_details(details: dict[str, Any]) -> dict[str, Any]:
    """Attach a deterministic checksum to a metadata-only provenance envelope.

    The checksum detects accidental or unauthorized mutation only when compared with a
    separately trusted copy. It is not a signature, identity proof, or substitute for
    access control and durable append-only audit storage.
    """
    if not isinstance(details, dict) or set(details) != {"schema_version", "tool_outputs"}:
        raise ValueError("audit details must contain only schema_version and tool_outputs")
    if details.get("schema_version") != 1:
        raise ValueError("unsupported audit details schema_version")
    outputs = details.get("tool_outputs")
    if not isinstance(outputs, list) or len(outputs) > 12:
        raise ValueError("tool_outputs must be a bounded list")
    allowed_output_keys = {
        "tool_name", "content_sha256", "detector_version", "injection_markers",
        "output_chars", "evidence_count", "untrusted",
    }
    for item in outputs:
        if not isinstance(item, dict) or set(item) != allowed_output_keys:
            raise ValueError("tool output must match the metadata-only provenance schema")
        if not isinstance(item["tool_name"], str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", item["tool_name"]):
            raise ValueError("tool output contains an invalid tool_name")
        if not isinstance(item["content_sha256"], str) or not _SHA256.fullmatch(item["content_sha256"]):
            raise ValueError("tool output contains an invalid content_sha256")
        if not isinstance(item["detector_version"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}", item["detector_version"]):
            raise ValueError("tool output contains an invalid detector_version")
        markers = item["injection_markers"]
        if not isinstance(markers, list) or len(markers) > 5 or any(marker not in {
            "instruction_override", "prompt_or_secret_disclosure", "tool_misuse",
            "safety_bypass", "external_exfiltration",
        } for marker in markers) or len(set(markers)) != len(markers):
            raise ValueError("tool output contains invalid injection markers")
        if not isinstance(item["output_chars"], int) or isinstance(item["output_chars"], bool) or not 0 <= item["output_chars"] <= 20_000:
            raise ValueError("tool output contains invalid output_chars")
        if not isinstance(item["evidence_count"], int) or isinstance(item["evidence_count"], bool) or not 0 <= item["evidence_count"] <= 100:
            raise ValueError("tool output contains invalid evidence_count")
        if item["untrusted"] is not True:
            raise ValueError("tool output must remain untrusted")
    # Round-trip through stable JSON to ensure only deterministic JSON values are sealed.
    canonical_details = json.loads(stable_json(details))
    digest = hashlib.sha256(stable_json(canonical_details).encode("utf-8")).hexdigest()
    return {**canonical_details, "payload_sha256": digest}


def verify_tool_provenance_audit_details(envelope: dict[str, Any]) -> bool:
    """Validate envelope shape, metadata schema, and checksum; fail closed on invalid input."""
    if not isinstance(envelope, dict) or set(envelope) != _AUDIT_ENVELOPE_KEYS:
        return False
    digest = envelope.get("payload_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        return False
    details = {
        "schema_version": envelope.get("schema_version"),
        "tool_outputs": envelope.get("tool_outputs"),
    }
    try:
        expected_envelope = seal_tool_provenance_audit_details(details)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(expected_envelope["payload_sha256"], digest)
