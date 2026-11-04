from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from services.api.app.main import app
from services.api.app.routes import rag_operator


def _dependency_calls(dependant):
    calls = {getattr(dependency.call, "__name__", "") for dependency in dependant.dependencies}
    for dependency in dependant.dependencies:
        calls.update(_dependency_calls(dependency))
    return calls


def _row(status):
    return SimpleNamespace(id=uuid4(), status=status)


def _payload(rows, status="triaged"):
    return rag_operator.FeedbackBulkStatusUpdate(
        feedback_ids=[row.id for row in rows],
        status=status,
    )


def _session_with_rows(rows):
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    session.scalars.return_value = result
    return session


def test_bulk_preview_route_is_registered_and_role_gated():
    assert "/api/v1/rag/operator/feedback/bulk-preview" in app.openapi()["paths"]
    route = next(
        route for route in rag_operator.router.routes
        if isinstance(route, APIRoute) and route.path.endswith("/feedback/bulk-preview")
    )
    assert "get_current_user" in _dependency_calls(route.dependant)


@pytest.mark.asyncio
async def test_bulk_preview_reports_eligible_and_unchanged_counts_without_writes(monkeypatch):
    organization_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=organization_id)
    rows = [_row("new"), _row("triaged")]
    session = _session_with_rows(rows)
    monkeypatch.setattr(rag_operator, "get_membership", AsyncMock(return_value=membership))

    response = await rag_operator.preview_bulk_feedback_status(
        payload=_payload(rows), user=user, db=session
    )

    assert response["requested"] == 2
    assert response["target_status"] == "triaged"
    assert response["eligible"] == 1
    assert response["unchanged"] == 1
    assert response["blocked"] == 0
    assert response["can_apply"] is True
    assert "no feedback IDs" in response["privacy"]
    session.commit.assert_not_awaited()
    statement = session.scalars.await_args.args[0]
    assert "rag_feedback.organization_id" in str(statement)
    assert organization_id in statement.compile().params.values()


@pytest.mark.asyncio
async def test_bulk_preview_blocks_terminal_feedback_without_mutating(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=uuid4())
    rows = [_row("new"), _row("resolved"), _row("ignored")]
    session = _session_with_rows(rows)
    monkeypatch.setattr(rag_operator, "get_membership", AsyncMock(return_value=membership))

    response = await rag_operator.preview_bulk_feedback_status(
        payload=_payload(rows), user=user, db=session
    )

    assert response["eligible"] == 1
    assert response["unchanged"] == 0
    assert response["blocked"] == 2
    assert response["blocked_by_status"] == {
        "new": 0, "triaged": 0, "resolved": 1, "ignored": 1
    }
    assert response["can_apply"] is False
    assert [row.status for row in rows] == ["new", "resolved", "ignored"]
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_preview_returns_not_found_for_missing_or_cross_tenant_items(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=uuid4())
    rows = [_row("new")]
    session = _session_with_rows([])
    monkeypatch.setattr(rag_operator, "get_membership", AsyncMock(return_value=membership))

    with pytest.raises(HTTPException) as error:
        await rag_operator.preview_bulk_feedback_status(
            payload=_payload(rows), user=user, db=session
        )

    assert error.value.status_code == 404
    session.commit.assert_not_awaited()
