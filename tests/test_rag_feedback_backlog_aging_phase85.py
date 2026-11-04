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


def _result(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


def test_feedback_backlog_route_is_registered_and_role_gated():
    assert "/api/v1/rag/operator/feedback/backlog" in app.openapi()["paths"]
    route = next(
        route for route in rag_operator.router.routes
        if isinstance(route, APIRoute) and route.path.endswith("/feedback/backlog")
    )
    assert "get_current_user" in _dependency_calls(route.dependant)


@pytest.mark.asyncio
async def test_feedback_backlog_returns_all_age_buckets_and_tenant_scoped_counts(monkeypatch):
    organization_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=organization_id)
    session = AsyncMock()
    session.execute.return_value = _result([
        ("under_24_hours", "new", 2),
        ("1_to_7_days", "triaged", 3),
        ("7_to_30_days", "triaged", 5),
        ("over_30_days", "new", 1),
    ])

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    response = await rag_operator.feedback_backlog_aging(user=user, db=session)

    assert response["timezone"] == "UTC"
    assert response["total_open"] == 11
    assert response["new_total"] == 3
    assert response["triaged_total"] == 8
    assert [item["key"] for item in response["series"]] == [
        "under_24_hours", "1_to_7_days", "7_to_30_days", "over_30_days"
    ]
    assert response["series"][0] == {
        "key": "under_24_hours",
        "label": "Under 24 hours",
        "new": 2,
        "triaged": 0,
        "total": 2,
    }
    assert response["series"][2]["triaged"] == 5
    assert response["series"][2]["total"] == 5
    assert response["series"][3]["new"] == 1
    assert "no individual feedback fields" in response["privacy"]

    statement = session.execute.await_args.args[0]
    sql = str(statement)
    assert "rag_feedback.organization_id" in sql
    assert "rag_feedback.created_at" in sql
    assert "rag_feedback.status" in sql
    params = statement.compile().params
    assert organization_id in params.values()
    assert ["new", "triaged"] in params.values()


@pytest.mark.asyncio
async def test_feedback_backlog_empty_queue_returns_zero_filled_buckets(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=uuid4())
    session = AsyncMock()
    session.execute.return_value = _result([])

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    response = await rag_operator.feedback_backlog_aging(user=user, db=session)

    assert response["total_open"] == 0
    assert response["new_total"] == 0
    assert response["triaged_total"] == 0
    assert len(response["series"]) == 4
    assert all(item["total"] == 0 for item in response["series"])
