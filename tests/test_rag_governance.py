from datetime import datetime, timedelta, timezone

import pytest

from services.rag.governance import (
    RAGModelCard,
    RetentionPolicy,
    acknowledge_deletion,
    build_audit_event,
    build_index_deletion_request,
    build_source_lineage,
    retention_expired,
    stable_json,
    validate_model_card,
)

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64


def test_audit_event_is_allowlisted_and_deterministic():
    event = build_audit_event(
        event_id="evt-1",
        event_type="retrieval.completed",
        occurred_at=NOW,
        organization_id="org-1",
        actor_id="user-1",
        resource_id="doc-1",
        outcome="success",
        duration_ms=42,
        evidence_count=3,
        trace_id="trace-1",
    )
    payload = event.to_dict()
    assert payload["occurred_at"] == NOW.isoformat()
    assert "query" not in payload and "text" not in payload and "token" not in payload
    assert stable_json(event) == stable_json(payload)


@pytest.mark.parametrize("kwargs", [
    {"event_type": "unknown.event"},
    {"outcome": "maybe"},
    {"organization_id": "contains private query text"},
    {"duration_ms": -1},
    {"evidence_count": 1001},
])
def test_audit_event_rejects_invalid_fields(kwargs):
    values = dict(
        event_id="evt-1", event_type="retrieval.completed", occurred_at=NOW,
        organization_id="org-1", outcome="success",
    )
    values.update(kwargs)
    with pytest.raises(ValueError):
        build_audit_event(**values)


def test_audit_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_audit_event(
            event_id="evt-1", event_type="retrieval.completed",
            occurred_at=datetime(2026, 1, 1), organization_id="org-1", outcome="success",
        )


def test_lineage_contains_digest_and_versions_not_content():
    lineage = build_source_lineage(
        organization_id="org-1", document_id="doc-1", chunk_id="chunk-1",
        content_sha256=DIGEST, source_version="v2", parser_version="txt-v1", indexed_at=NOW,
    )
    assert lineage.content_sha256 == DIGEST
    assert "text" not in lineage.to_dict()
    with pytest.raises(ValueError, match="SHA-256"):
        build_source_lineage(
            organization_id="org-1", document_id="doc-1", chunk_id="chunk-1",
            content_sha256="not-a-hash", source_version="v2", parser_version="txt-v1", indexed_at=NOW,
        )


def test_deletion_request_is_idempotent_across_request_times():
    first = build_index_deletion_request(
        organization_id="org-1", document_id="doc-1", content_sha256=DIGEST, requested_at=NOW,
    )
    second = build_index_deletion_request(
        organization_id="org-1", document_id="doc-1", content_sha256=DIGEST,
        requested_at=NOW + timedelta(minutes=3),
    )
    assert first.idempotency_key == second.idempotency_key
    assert first.status == "pending"
    assert acknowledge_deletion(first, attempts=2).status == "acknowledged"
    with pytest.raises(ValueError, match="only pending"):
        acknowledge_deletion(acknowledge_deletion(first))


def test_retention_policy_bounds_and_expiry():
    policy = RetentionPolicy()
    assert policy.event_days == 90
    assert retention_expired(created_at=NOW, now=NOW + timedelta(days=90), retention_days=90)
    assert not retention_expired(created_at=NOW, now=NOW + timedelta(days=89), retention_days=90)
    with pytest.raises(ValueError):
        RetentionPolicy(event_days=0)


def test_model_card_requires_limitations_and_valid_date():
    card = RAGModelCard(
        model_name="retriever", model_version="1.2.0", intended_use="Internal search",
        limitations="Synthetic benchmark only", evaluation_dataset="rag-golden-v1",
        evaluation_date="2026-10-13", owner="platform-team",
    )
    assert validate_model_card(card) == card
    with pytest.raises(ValueError, match="limitations"):
        validate_model_card(RAGModelCard(
            model_name="retriever", model_version="1.2.0", intended_use="Internal search",
            limitations="", evaluation_dataset="rag-golden-v1", evaluation_date="2026-10-13",
            owner="platform-team",
        ))
    with pytest.raises(ValueError, match="ISO-8601"):
        validate_model_card(RAGModelCard(
            model_name="retriever", model_version="1.2.0", intended_use="Internal search",
            limitations="Limitations documented", evaluation_dataset="rag-golden-v1",
            evaluation_date="not-a-date", owner="platform-team",
        ))
