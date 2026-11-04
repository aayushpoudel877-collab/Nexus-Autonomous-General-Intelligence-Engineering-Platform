from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute

from services.api.app.main import app
from services.api.app.routes import rag_operator


def _dependency_calls(dependant):
    calls = {getattr(dependency.call, "__name__", "") for dependency in dependant.dependencies}
    for dependency in dependant.dependencies:
        calls.update(_dependency_calls(dependency))
    return calls


def _feedback_row():
    return SimpleNamespace(
        id=uuid4(),
        query_sha256="a" * 64,
        evidence_ids=["evidence-1"],
        rating="unhelpful",
        note="Needs a clearer citation",
        status="new",
        created_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
        updated_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
    )


def test_feedback_page_route_has_bounded_pagination_and_authentication():
    operation = app.openapi()["paths"]["/api/v1/rag/operator/feedback/page"]["get"]
    parameters = {item["name"]: item["schema"] for item in operation["parameters"]}
    assert parameters["limit"]["minimum"] == 1
    assert parameters["limit"]["maximum"] == 100
    assert parameters["offset"]["minimum"] == 0
    assert parameters["offset"]["maximum"] == 1_000_000
    route = next(
        route for route in rag_operator.router.routes
        if isinstance(route, APIRoute) and route.path.endswith("/feedback/page")
    )
    assert "get_current_user" in _dependency_calls(route.dependant)


@pytest.mark.asyncio
async def test_feedback_page_returns_tenant_scoped_items_and_navigation_metadata(monkeypatch):
    organization_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=organization_id)
    row = _feedback_row()
    session = AsyncMock()
    session.scalar.return_value = 61
    page_result = MagicMock()
    page_result.all.return_value = [row]
    session.scalars.return_value = page_result

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    response = await rag_operator.page_feedback(
        status_filter="new", limit=25, offset=50, user=user, db=session
    )

    assert response["total"] == 61
    assert response["limit"] == 25
    assert response["offset"] == 50
    assert response["has_more"] is True
    assert len(response["items"]) == 1
    assert response["items"][0]["id"] == str(row.id)

    count_statement = session.scalar.await_args.args[0]
    page_statement = session.scalars.await_args.args[0]
    for statement in (count_statement, page_statement):
        assert "rag_feedback.organization_id" in str(statement)
        assert "rag_feedback.status" in str(statement)
        assert organization_id in statement.compile().params.values()
        assert "new" in statement.compile().params.values()
    page_sql = str(page_statement)
    assert "ORDER BY rag_feedback.created_at DESC, rag_feedback.id ASC" in page_sql
    assert "LIMIT" in page_sql
    assert "OFFSET" in page_sql


@pytest.mark.asyncio
async def test_feedback_page_empty_results_has_no_next_page(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=uuid4())
    session = AsyncMock()
    session.scalar.return_value = 0
    page_result = MagicMock()
    page_result.all.return_value = []
    session.scalars.return_value = page_result

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    response = await rag_operator.page_feedback(
        status_filter="resolved", limit=25, offset=0, user=user, db=session
    )

    assert response == {
        "items": [],
        "total": 0,
        "limit": 25,
        "offset": 0,
        "has_more": False,
    }
