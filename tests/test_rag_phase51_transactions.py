"""Phase 51 contracts for audited retrieval transaction boundaries.

These tests use a session double to verify API orchestration. They are not a
substitute for the PostgreSQL-backed integration suite still required by CI.
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.api.app.routes import rag_agentic
from services.rag.agentic_retrieval import ToolExecutionError, ToolResult


@pytest.mark.asyncio
async def test_audited_retrieval_commits_metadata_before_returning(monkeypatch):
    organization_id = uuid4()
    actor_id = uuid4()
    user = SimpleNamespace(id=actor_id)
    membership = SimpleNamespace(organization_id=organization_id)
    session = AsyncMock()
    session.add = MagicMock()

    async def membership_for_user(_user, _session):
        return membership

    async def fake_search(tenant_id, arguments, *, db):
        assert tenant_id == str(organization_id)
        assert arguments["query"] == "private query text"
        return ToolResult(
            tenant_id=tenant_id,
            text=json.dumps({"retrieval_mode": "lexical", "evidence": []}),
            evidence_ids=(),
        )

    monkeypatch.setattr(rag_agentic, "get_membership", membership_for_user)
    monkeypatch.setattr(rag_agentic, "_lexical_search", fake_search)

    response = await rag_agentic.audited_agentic_query(
        rag_agentic.AgenticRAGQuery(query="private query text"),
        user=user,
        db=session,
    )

    assert response["query"] == "private query text"
    assert response["retrieval_mode"] == "lexical"
    session.add.assert_called_once()
    event = session.add.call_args.args[0]
    assert event.organization_id == organization_id
    assert event.actor_user_id == actor_id
    assert event.action == "rag.tool_execution.completed"
    assert "private query text" not in str(event.detail)
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_audited_retrieval_rolls_back_and_fails_closed_when_audit_fails(monkeypatch):
    organization_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=organization_id)
    session = AsyncMock()
    session.add = MagicMock()

    async def membership_for_user(_user, _session):
        return membership

    async def fail_execution(*args, **kwargs):
        raise ToolExecutionError("audit writer unavailable")

    monkeypatch.setattr(rag_agentic, "get_membership", membership_for_user)
    monkeypatch.setattr(rag_agentic, "execute_bounded_tool_plan_with_audit", fail_execution)

    with pytest.raises(HTTPException) as error:
        await rag_agentic.audited_agentic_query(
            rag_agentic.AgenticRAGQuery(query="hello"),
            user=user,
            db=session,
        )

    assert error.value.status_code == 503
    assert "audit failed" in error.value.detail
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_audited_retrieval_rolls_back_unexpected_commit_failure(monkeypatch):
    organization_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=organization_id)
    session = AsyncMock()
    session.add = MagicMock()
    session.commit.side_effect = RuntimeError("database unavailable")

    async def membership_for_user(_user, _session):
        return membership

    async def fake_search(tenant_id, arguments, *, db):
        return ToolResult(
            tenant_id=tenant_id,
            text=json.dumps({"retrieval_mode": "lexical", "evidence": []}),
            evidence_ids=(),
        )

    monkeypatch.setattr(rag_agentic, "get_membership", membership_for_user)
    monkeypatch.setattr(rag_agentic, "_lexical_search", fake_search)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await rag_agentic.audited_agentic_query(
            rag_agentic.AgenticRAGQuery(query="hello"),
            user=user,
            db=session,
        )

    session.commit.assert_awaited_once()
    session.rollback.assert_awaited_once()
