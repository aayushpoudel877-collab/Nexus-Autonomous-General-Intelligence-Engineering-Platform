from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError
from services.api.app.main import app
from services.api.app.routes.rag import router
from services.api.app.routes.rag_operator import (
    FeedbackCreate,
    ReindexRequestCreate,
    router as operator_router,
)
from services.api.app.schemas.rag import RAGDocumentCreate, RAGQueryRequest


def _dependency_calls(dependant):
    calls = {getattr(dependency.call, "__name__", "") for dependency in dependant.dependencies}
    for dependency in dependant.dependencies:
        calls.update(_dependency_calls(dependency))
    return calls


def test_rag_routes_are_registered_under_api_v1():
    paths = app.openapi()["paths"]
    assert "post" in paths["/api/v1/rag/documents"]
    assert "get" in paths["/api/v1/rag/documents"]
    assert "get" in paths["/api/v1/rag/documents/{document_id}/chunks"]
    assert "delete" in paths["/api/v1/rag/documents/{document_id}"]
    assert "post" in paths["/api/v1/rag/query"]


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
    with pytest.raises(ValidationError):
        RAGDocumentCreate(title="   ", text="content")
    with pytest.raises(ValidationError):
        RAGDocumentCreate(title="notes", text="  \n  ")
    with pytest.raises(ValidationError, match="overlap"):
        RAGDocumentCreate(title="notes", text="content", max_chars=100, overlap=100)


def test_query_contract_has_strict_bounds_and_rejects_tenant_override():
    with pytest.raises(ValidationError):
        RAGQueryRequest(query="what is this?", top_k=0)
    with pytest.raises(ValidationError):
        RAGQueryRequest(query="what is this?", organization_id=str(uuid4()))
    normalized = RAGQueryRequest(query="  what is this?  ", top_k=5)
    assert normalized.top_k == 5
    assert normalized.query == "what is this?"
    with pytest.raises(ValidationError, match="non-whitespace"):
        RAGQueryRequest(query="   ")



def test_operator_routes_are_registered_and_authenticated():
    paths = app.openapi()["paths"]
    assert "get" in paths["/api/v1/rag/operator/health"]
    assert "post" in paths["/api/v1/rag/operator/feedback"]
    assert "get" in paths["/api/v1/rag/operator/feedback"]
    assert "patch" in paths["/api/v1/rag/operator/feedback/{feedback_id}"]
    assert "post" in paths["/api/v1/rag/operator/documents/{document_id}/reindex"]
    assert "patch" in paths["/api/v1/rag/operator/reindex-requests/{request_id}"]
    for route in operator_router.routes:
        if not isinstance(route, APIRoute):
            continue
        calls = _dependency_calls(route.dependant)
        assert "get_current_user" in calls, f"{route.path} does not require authenticated user context"


def test_operator_feedback_contract_rejects_invalid_or_duplicate_evidence():
    with pytest.raises(ValidationError):
        FeedbackCreate(query="   ", rating="helpful")
    with pytest.raises(ValidationError):
        FeedbackCreate(query="question", rating="neutral")
    with pytest.raises(ValidationError):
        FeedbackCreate(query="question", rating="helpful", evidence_ids=["chunk-1", "chunk-1"])
    with pytest.raises(ValidationError):
        FeedbackCreate(query="question", rating="helpful", evidence_ids=[""])


def test_reindex_request_requires_a_nonblank_reason():
    with pytest.raises(ValidationError):
        ReindexRequestCreate(reason="   ")
    assert ReindexRequestCreate(reason=" refresh index ").reason == "refresh index"
