import asyncio

import pytest

from services.rag.agentic_retrieval import (
    AgenticRetrievalPolicy,
    RetrievalTool,
    ToolCall,
    ToolExecutionError,
    ToolPolicyError,
    ToolResult,
    execute_bounded_tool_plan,
)


async def _search(tenant_id, arguments):
    return ToolResult(tenant_id, f"Found {arguments['query']}", ("E1",))


def _tool(executor=_search, **overrides):
    values = {
        "name": "lexical_search",
        "executor": executor,
        "required_scopes": frozenset({"rag:read"}),
        "max_calls": 2,
        "timeout_seconds": 1.0,
        "max_output_chars": 100,
    }
    values.update(overrides)
    return RetrievalTool(**values)


@pytest.mark.asyncio
async def test_allowlisted_read_only_tool_executes_with_tenant_and_scopes():
    tool = _tool()
    records = await execute_bounded_tool_plan(
        [ToolCall("lexical_search", {"query": "capital"})],
        tools={"lexical_search": tool},
        tenant_id="org-a",
        actor_scopes=frozenset({"rag:read"}),
    )
    assert len(records) == 1
    assert records[0].text == "Found capital"
    assert records[0].evidence_ids == ("E1",)
    assert records[0].output_chars == len("Found capital")


@pytest.mark.asyncio
async def test_unregistered_tools_and_missing_scopes_are_rejected():
    tool = _tool()
    with pytest.raises(ToolPolicyError, match="not allowlisted"):
        await execute_bounded_tool_plan(
            [ToolCall("shell", {})],
            tools={"lexical_search": tool},
            tenant_id="org-a",
            actor_scopes=frozenset({"rag:read"}),
        )
    with pytest.raises(ToolPolicyError, match="lacks required scope"):
        await execute_bounded_tool_plan(
            [ToolCall("lexical_search", {"query": "capital"})],
            tools={"lexical_search": tool},
            tenant_id="org-a",
            actor_scopes=frozenset(),
        )


@pytest.mark.asyncio
async def test_cross_tenant_tool_results_are_rejected():
    async def bad_tool(tenant_id, arguments):
        return ToolResult("org-b", "private data", ("E-private",))

    with pytest.raises(ToolPolicyError, match="cross-tenant"):
        await execute_bounded_tool_plan(
            [ToolCall("lexical_search", {})],
            tools={"lexical_search": _tool(executor=bad_tool)},
            tenant_id="org-a",
            actor_scopes=frozenset({"rag:read"}),
        )


@pytest.mark.asyncio
async def test_per_tool_call_and_global_plan_budgets_are_enforced():
    tool = _tool(max_calls=1)
    with pytest.raises(ToolPolicyError, match="call budget"):
        await execute_bounded_tool_plan(
            [ToolCall("lexical_search", {"query": "one"}), ToolCall("lexical_search", {"query": "two"})],
            tools={"lexical_search": tool},
            tenant_id="org-a",
            actor_scopes=frozenset({"rag:read"}),
        )
    with pytest.raises(ToolPolicyError, match="step count"):
        await execute_bounded_tool_plan(
            [ToolCall("lexical_search", {})] * 2,
            tools={"lexical_search": tool},
            tenant_id="org-a",
            actor_scopes=frozenset({"rag:read"}),
            policy=AgenticRetrievalPolicy(max_steps=1),
        )


@pytest.mark.asyncio
async def test_argument_secrets_and_output_budgets_fail_closed():
    tool = _tool()
    with pytest.raises(ToolPolicyError, match="credential-like"):
        await execute_bounded_tool_plan(
            [ToolCall("lexical_search", {"filters": {"api-key": "do-not-pass"}})],
            tools={"lexical_search": tool},
            tenant_id="org-a",
            actor_scopes=frozenset({"rag:read"}),
        )

    with pytest.raises(ToolPolicyError, match="output budget"):
        await execute_bounded_tool_plan(
            [ToolCall("lexical_search", {})],
            tools={"lexical_search": _tool(max_output_chars=3)},
            tenant_id="org-a",
            actor_scopes=frozenset({"rag:read"}),
        )


@pytest.mark.asyncio
async def test_tool_timeout_is_bounded():
    async def slow_tool(tenant_id, arguments):
        await asyncio.sleep(0.05)
        return ToolResult(tenant_id, "late")

    with pytest.raises(ToolExecutionError, match="timed out"):
        await execute_bounded_tool_plan(
            [ToolCall("lexical_search", {})],
            tools={"lexical_search": _tool(executor=slow_tool, timeout_seconds=0.001)},
            tenant_id="org-a",
            actor_scopes=frozenset({"rag:read"}),
        )


def test_tool_policy_rejects_non_read_only_tools_and_invalid_limits():
    with pytest.raises(ValueError, match="read-only"):
        _tool(read_only=False)
    with pytest.raises(ValueError, match="max_steps"):
        AgenticRetrievalPolicy(max_steps=13)
