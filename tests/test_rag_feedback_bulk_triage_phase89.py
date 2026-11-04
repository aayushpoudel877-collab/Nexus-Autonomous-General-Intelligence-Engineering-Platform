from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError

from services.api.app.main import app
from services.api.app.routes import rag_operator


def _dependency_calls(dependant):
    calls = {getattr(dependency.call, "__name__", "") for dependency in dependant.dependencies}
    for dependency in dependant.dependencies:
        calls.update(_dependency_calls(dependency))
    return calls


def _row(status="new"):
    return SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        status=status,
        triaged_by_user_id=None,
    )


def _payload(rows, status="triaged"):
    return rag_operator.FeedbackBulkStatusUpdate(
        feedback_ids=[row.id for row in rows],
        status=status,
    )


def test_bulk_feedback_route_is_registered_and_role_gated():
    assert "/api/v1/rag/operator/feedback/bulk-update" in app.openapi()["paths"]
    route = next(
        route for route in rag_operator.router.routes
        if isinstance(route, APIRoute) and route.path.endswith("/feedback/bulk-update")
    )
    assert "get_current_user" in _dependency_calls(route.dependant)


def test_bulk_feedback_payload_rejects_empty_duplicate_and_oversized_batches():
    with pytest.raises(ValidationError):
        rag_operator.FeedbackBulkStatusUpdate(feedback_ids=[], status="triaged")
    duplicate_id = uuid4()
    with pytest.raises(ValidationError):
        rag_operator.FeedbackBulkStatusUpdate(
            feedback_ids=[duplicate_id, duplicate_id], status="triaged"
        )
    with pytest.raises(ValidationError):
        rag_operator.FeedbackBulkStatusUpdate(
            feedback_ids=[uuid4() for _ in range(51)], status="triaged"
        )


@pytest.mark.asyncio
async def test_bulk_feedback_transition_updates_and_audits_all_items_atomically(monkeypatch):
    organization_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=organization_id)
    rows = [_row(), _row()]
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    session.scalars.return_value = result
    audit = AsyncMock()
    monkeypatch.setattr(rag_operator, "get_membership", AsyncMock(return_value=membership))
    monkeypatch.setattr(rag_operator, "record_audit", audit)

    response = await rag_operator.bulk_update_feedback_status(
        payload=_payload(rows), user=user, db=session
    )

    assert response == {"requested": 2, "updated": 2, "unchanged": 0, "status": "triaged"}
    assert all(row.status == "triaged" for row in rows)
    assert all(row.triaged_by_user_id == user.id for row in rows)
    assert audit.await_count == 2
    assert session.commit.await_count == 1
    statement = session.scalars.await_args.args[0]
    sql = str(statement)
    assert "rag_feedback.organization_id" in sql
    assert "rag_feedback.id IN" in sql
    assert organization_id in statement.compile().params.values()


@pytest.mark.asyncio
async def test_bulk_feedback_rejects_invalid_transition_without_partial_mutation(monkeypatch):
    organization_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=organization_id)
    rows = [_row("new"), _row("resolved")]
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    session.scalars.return_value = result
    audit = AsyncMock()
    monkeypatch.setattr(rag_operator, "get_membership", AsyncMock(return_value=membership))
    monkeypatch.setattr(rag_operator, "record_audit", audit)

    with pytest.raises(HTTPException) as error:
        await rag_operator.bulk_update_feedback_status(
            payload=_payload(rows), user=user, db=session
        )

    assert error.value.status_code == 409
    assert [row.status for row in rows] == ["new", "resolved"]
    audit.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_feedback_rejects_missing_or_cross_tenant_ids(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=uuid4())
    row = _row()
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    session.scalars.return_value = result
    monkeypatch.setattr(rag_operator, "get_membership", AsyncMock(return_value=membership))

    with pytest.raises(HTTPException) as error:
        await rag_operator.bulk_update_feedback_status(
            payload=_payload([row]), user=user, db=session
        )

    assert error.value.status_code == 404
    session.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_bulk_feedback_same_status_is_reported_unchanged_without_audit(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=uuid4())
    rows = [_row("triaged"), _row("triaged")]
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    session.scalars.return_value = result
    audit = AsyncMock()
    monkeypatch.setattr(rag_operator, "get_membership", AsyncMock(return_value=membership))
    monkeypatch.setattr(rag_operator, "record_audit", audit)

    response = await rag_operator.bulk_update_feedback_status(
        payload=_payload(rows, status="triaged"), user=user, db=session
    )

    assert response == {"requested": 2, "updated": 0, "unchanged": 2, "status": "triaged"}
    audit.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_feedback_rolls_back_when_commit_fails(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=uuid4())
    rows = [_row(), _row()]
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    session.scalars.return_value = result
    session.commit.side_effect = RuntimeError("commit failed")
    audit = AsyncMock()
    monkeypatch.setattr(rag_operator, "get_membership", AsyncMock(return_value=membership))
    monkeypatch.setattr(rag_operator, "record_audit", audit)

    with pytest.raises(RuntimeError, match="commit failed"):
        await rag_operator.bulk_update_feedback_status(
            payload=_payload(rows), user=user, db=session
        )

    assert audit.await_count == 2
    session.rollback.assert_awaited_once()

