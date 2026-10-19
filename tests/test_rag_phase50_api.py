from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

from services.api.app.main import app
from services.api.app.routes.rag_agentic import (
    AgenticRAGQuery,
    _LexicalSearchArguments,
    router,
)
from services.rag.agentic_retrieval import RetrievalTool


def _dependency_calls(dependant):
    calls = {getattr(dependency.call, "__name__", "") for dependency in dependant.dependencies}
    for dependency in dependant.dependencies:
        calls.update(_dependency_calls(dependency))
    return calls


def test_audited_agentic_endpoint_is_registered_and_authenticated():
    operation = app.openapi()["paths"]["/api/v1/rag/agentic-query"]["post"]
    assert operation["operationId"] == "audited_agentic_query_api_v1_rag_agentic_query_post"
    routes = [route for route in router.routes if isinstance(route, APIRoute)]
    assert len(routes) == 1
    assert "get_current_user" in _dependency_calls(routes[0].dependant)


def test_agentic_request_is_strictly_bounded_and_rejects_tenant_override():
    with pytest.raises(ValidationError):
        AgenticRAGQuery(query="   ")
    with pytest.raises(ValidationError):
        AgenticRAGQuery(query="question", organization_id=str(uuid4()))
    with pytest.raises(ValidationError):
        AgenticRAGQuery(query="question", top_k=6)
    assert AgenticRAGQuery(query=" question ").query == "question"


def test_tool_arguments_reject_extra_fields_and_out_of_range_values():
    with pytest.raises(ValidationError):
        _LexicalSearchArguments(query="question", top_k=1, character_ngram_weight=0, tenant_id="other")
    with pytest.raises(ValidationError):
        _LexicalSearchArguments(query="question", top_k=0, character_ngram_weight=0)


def test_registered_tool_is_explicitly_read_only_and_scoped():
    async def unused_executor(tenant_id, arguments):
        raise AssertionError("contract test must not execute a database tool")

    tool = RetrievalTool(
        name="lexical_search",
        executor=unused_executor,
        argument_model=_LexicalSearchArguments,
        required_scopes=frozenset({"rag:read"}),
        max_calls=1,
        timeout_seconds=5,
        max_output_chars=20_000,
        read_only=True,
    )
    assert tool.read_only is True
    assert tool.required_scopes == frozenset({"rag:read"})
    assert tool.max_calls == 1
