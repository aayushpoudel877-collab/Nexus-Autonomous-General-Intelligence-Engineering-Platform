"""Phase 52 contracts for idempotent metadata-only provenance persistence."""
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from services.rag.governance import seal_tool_provenance_audit_details
from services.rag.persistence import build_database_tool_audit_writer


def _envelope():
    return seal_tool_provenance_audit_details({
        "schema_version": 1,
        "tool_outputs": [{
            "tool_name": "lexical_search",
            "content_sha256": "b" * 64,
            "detector_version": "markers-v1",
            "injection_markers": [],
            "output_chars": 8,
            "evidence_count": 0,
            "untrusted": True,
        }],
    })


@pytest.mark.asyncio
async def test_first_request_id_persists_one_audit_event():
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.return_value = None
    org = uuid4()
    writer = build_database_tool_audit_writer(
        session, organization_id=org, actor_user_id=uuid4(), request_id="retry-001"
    )

    await writer(str(org), _envelope())

    session.scalar.assert_awaited_once()
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_exact_retry_is_idempotent_and_does_not_add_duplicate():
    session = AsyncMock()
    session.add = MagicMock()
    org = uuid4()
    actor = uuid4()
    envelope = _envelope()
    existing = MagicMock(
        organization_id=org,
        actor_user_id=actor,
        action="rag.tool_execution.completed",
        resource_type="rag_tool_execution",
        resource_id="retry-002",
        request_id="retry-002",
        detail=deepcopy(envelope),
    )
    session.scalar.return_value = existing
    writer = build_database_tool_audit_writer(
        session, organization_id=org, actor_user_id=actor, request_id="retry-002"
    )

    await writer(str(org), envelope)

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_reusing_request_id_with_different_envelope_fails_closed():
    session = AsyncMock()
    session.add = MagicMock()
    org = uuid4()
    actor = uuid4()
    envelope = _envelope()
    existing = MagicMock(
        organization_id=org,
        actor_user_id=actor,
        action="rag.tool_execution.completed",
        resource_type="rag_tool_execution",
        resource_id="retry-003",
        request_id="retry-003",
        detail=deepcopy(envelope),
    )
    session.scalar.return_value = existing
    changed = deepcopy(envelope)
    changed["tool_outputs"][0]["output_chars"] = 99
    # Reseal the changed metadata so the conflict is about request-ID reuse,
    # rather than a malformed checksum.
    changed = seal_tool_provenance_audit_details({
        key: value for key, value in changed.items()
        if key not in {"payload_sha256", "schema_version"}
    } | {"schema_version": 1})
    writer = build_database_tool_audit_writer(
        session, organization_id=org, actor_user_id=actor, request_id="retry-003"
    )

    with pytest.raises(ValueError, match="already used"):
        await writer(str(org), changed)

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_request_from_another_actor_is_not_replayed():
    session = AsyncMock()
    session.add = MagicMock()
    org = uuid4()
    envelope = _envelope()
    existing = MagicMock(
        organization_id=org,
        actor_user_id=uuid4(),
        action="rag.tool_execution.completed",
        resource_type="rag_tool_execution",
        resource_id="retry-004",
        request_id="retry-004",
        detail=deepcopy(envelope),
    )
    session.scalar.return_value = existing
    writer = build_database_tool_audit_writer(
        session, organization_id=org, actor_user_id=uuid4(), request_id="retry-004"
    )

    with pytest.raises(ValueError, match="already used"):
        await writer(str(org), envelope)

    session.add.assert_not_called()
    session.flush.assert_not_awaited()
