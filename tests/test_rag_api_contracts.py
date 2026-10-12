from uuid import uuid4

import pytest
from pydantic import ValidationError
from fastapi.routing import APIRoute

from services.api.app.main import app
from services.api.app.routes.rag import router
from services.api.app.schemas.rag import RAGDocumentCreate, RAGQueryRequest


def _dependency_calls(dependant):
    calls = {getattr(dependency.call, "__name__", "") for dependency in dependant.dependencies}
    for dependency in dependant.dependencies:
        calls.update(_dependency_calls(dependency))
    return calls


def test_rag_routes_are_registered_under_api_v1():
    routes = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert ("/api/v1/rag/documents", "POST") in routes
    assert ("/api/v1/rag/documents", "GET") in routes
    assert ("/api/v1/rag/documents/{document_id}/chunks", "GET") in routes
    assert ("/api/v1/rag/documents/{document_id}", "DELETE") in routes
    assert ("/api/v1/rag/query", "POST") in routes


def test_every_rag_endpoint_requires_authenticated_user_context():
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        calls = _dependency_calls(route.dependant)
        assert "get_current_user" in calls, f"{route.path} does not require authenticated user context"


def test_document_ingestion_rejects_extra_fields_and_invalid_bounds():
    with pytest.raises(ValidationError):
        RAGDocumentCreate(title="notes", text="content", organization_id=str(uuid4()))
    with pytest.raises(ValidationError):
        RAGDocumentCreate(title="notes", text="content", max_chars=99)
    with pytest.raises(ValidationError):
        RAGDocumentCreate(title="", text="content")


def test_query_contract_has_strict_bounds_and_rejects_tenant_override():
    with pytest.raises(ValidationError):
        RAGQueryRequest(query="what is this?", top_k=0)
    with pytest.raises(ValidationError):
        RAGQueryRequest(query="what is this?", organization_id=str(uuid4()))
    assert RAGQueryRequest(query="  what is this?  ", top_k=5).top_k == 5
