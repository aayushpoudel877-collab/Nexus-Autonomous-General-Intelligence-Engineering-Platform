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
            "content_sha256": "a" * 64,
            "detector_version": "markers-v1",
            "injection_markers": [],
            "output_chars": 12,
            "evidence_count": 1,
            "untrusted": True,
        }],
    })


@pytest.mark.asyncio
async def test_database_writer_adds_verified_metadata_to_existing_audit_event():
    session = AsyncMock()
    session.add = MagicMock()
    organization_id = uuid4()
    actor_user_id = uuid4()
    envelope = _envelope()
    writer = build_database_tool_audit_writer(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        request_id="req-123",
    )

    await writer(str(organization_id), envelope)

    session.add.assert_called_once()
    event = session.add.call_args.args[0]
    assert event.organization_id == organization_id
    assert event.actor_user_id == actor_user_id
    assert event.action == "rag.tool_execution.completed"
    assert event.resource_type == "rag_tool_execution"
    assert event.resource_id == "req-123"
    assert event.request_id == "req-123"
    assert event.detail == envelope
    assert "text" not in event.detail["tool_outputs"][0]
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_writer_rejects_cross_tenant_scope_before_database_write():
    session = AsyncMock()
    session.add = MagicMock()
    organization_id = uuid4()
    other_organization_id = uuid4()
    writer = build_database_tool_audit_writer(session, organization_id=organization_id)

    with pytest.raises(PermissionError, match="does not match"):
        await writer(str(other_organization_id), _envelope())

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_writer_rejects_tampered_envelope_before_database_write():
    session = AsyncMock()
    session.add = MagicMock()
    organization_id = uuid4()
    writer = build_database_tool_audit_writer(session, organization_id=organization_id)
    envelope = deepcopy(_envelope())
    envelope["tool_outputs"][0]["output_chars"] = 999

    with pytest.raises(ValueError, match="failed verification"):
        await writer(str(organization_id), envelope)

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_writer_rejects_non_uuid_tenant_and_non_dict_envelope():
    session = AsyncMock()
    session.add = MagicMock()
    organization_id = uuid4()
    writer = build_database_tool_audit_writer(session, organization_id=organization_id)

    with pytest.raises(ValueError, match="tenant_id"):
        await writer("not-a-uuid", _envelope())
    with pytest.raises(TypeError, match="dictionary"):
        await writer(str(organization_id), [])

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


def test_database_writer_validates_captured_authenticated_context():
    session = AsyncMock()
    with pytest.raises(TypeError, match="organization_id"):
        build_database_tool_audit_writer(session, organization_id="not-a-uuid")
    with pytest.raises(TypeError, match="actor_user_id"):
        build_database_tool_audit_writer(session, organization_id=uuid4(), actor_user_id="user")
    with pytest.raises(ValueError, match="request_id"):
        build_database_tool_audit_writer(session, organization_id=uuid4(), request_id="bad request id")
