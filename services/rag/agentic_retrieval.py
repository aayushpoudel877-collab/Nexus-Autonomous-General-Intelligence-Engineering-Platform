"""Explicitly allowlisted, budgeted tool orchestration for agentic RAG.

Tool outputs are untrusted data. This module does not create tools, access the network,
run shell commands, or grant permissions; callers must provide an explicit registry.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from .prompt_injection import DETECTOR_VERSION, detect_injection_markers

MAX_PLAN_STEPS = 12
MAX_ARGUMENT_BYTES = 8_192
MAX_ARGUMENT_DEPTH = 8
MAX_ARGUMENT_ITEMS = 100
MAX_TOOL_OUTPUT_CHARS = 20_000
MAX_TOTAL_OUTPUT_CHARS = 50_000
MAX_EVIDENCE_IDS = 100
_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SENSITIVE_ARGUMENT_KEY_PARTS = (
    "password", "passwd", "secret", "token", "credential", "authorization",
    "apikey", "privatekey", "accesskey", "bearer",
)


class ToolPolicyError(RuntimeError):
    """A planned tool call violated the explicit retrieval policy."""


class ToolExecutionError(RuntimeError):
    """An allowlisted tool failed or returned an invalid result."""


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One requested call to a registered tool; arguments are untrusted input."""

    tool_name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """A tool result that must be treated as untrusted data by downstream reasoning."""

    tenant_id: str
    text: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip() or len(self.tenant_id) > 200:
            raise ValueError("tool result tenant_id is required and bounded")
        if not isinstance(self.text, str):
            raise TypeError("tool result text must be a string")
        if not isinstance(self.evidence_ids, tuple):
            raise TypeError("tool result evidence_ids must be a tuple")
        if len(self.evidence_ids) > MAX_EVIDENCE_IDS:
            raise ValueError("tool result has too many evidence IDs")
        if any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in self.evidence_ids):
            raise ValueError("tool result evidence IDs must be non-empty and bounded")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("tool result evidence IDs must be unique")


@dataclass(frozen=True, slots=True)
class RetrievalTool:
    """An explicitly registered tool with a per-tool scope, call, timeout, and output budget."""

    name: str
    executor: Callable[[str, Mapping[str, Any]], Awaitable[ToolResult]]
    argument_model: type[BaseModel]
    required_scopes: frozenset[str] = frozenset()
    max_calls: int = 2
    timeout_seconds: float = 5.0
    max_output_chars: int = 12_000
    read_only: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _TOOL_NAME.fullmatch(self.name):
            raise ValueError("tool name must be a lowercase identifier")
        if not callable(self.executor):
            raise TypeError("tool executor must be callable")
        if not isinstance(self.argument_model, type) or not issubclass(self.argument_model, BaseModel):
            raise TypeError("argument_model must be a Pydantic model class")
        if self.argument_model.model_config.get("extra") != "forbid":
            raise ValueError("tool argument models must forbid extra fields")
        if not isinstance(self.required_scopes, (set, frozenset)):
            raise TypeError("required_scopes must be a set of scope names")
        if any(not isinstance(scope, str) or not scope.strip() for scope in self.required_scopes):
            raise ValueError("required scopes must be non-empty strings")
        object.__setattr__(self, "required_scopes", frozenset(self.required_scopes))
        if not isinstance(self.read_only, bool) or not self.read_only:
            raise ValueError("retrieval tools must be explicitly read-only")
        if isinstance(self.max_calls, bool) or not isinstance(self.max_calls, int) or not 1 <= self.max_calls <= 10:
            raise ValueError("max_calls must be between 1 and 10")
        if not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be finite and in (0, 30]")
        if isinstance(self.max_output_chars, bool) or not isinstance(self.max_output_chars, int) or not 1 <= self.max_output_chars <= MAX_TOOL_OUTPUT_CHARS:
            raise ValueError("max_output_chars must be between 1 and the configured limit")


@dataclass(frozen=True, slots=True)
class AgenticRetrievalPolicy:
    """Global request budgets applied in addition to per-tool limits."""

    max_steps: int = 8
    max_total_output_chars: int = 30_000
    max_evidence_ids: int = 50

    def __post_init__(self) -> None:
        if isinstance(self.max_steps, bool) or not isinstance(self.max_steps, int) or not 1 <= self.max_steps <= MAX_PLAN_STEPS:
            raise ValueError(f"max_steps must be between 1 and {MAX_PLAN_STEPS}")
        if isinstance(self.max_total_output_chars, bool) or not isinstance(self.max_total_output_chars, int) or not 1 <= self.max_total_output_chars <= MAX_TOTAL_OUTPUT_CHARS:
            raise ValueError("max_total_output_chars is outside the configured limit")
        if isinstance(self.max_evidence_ids, bool) or not isinstance(self.max_evidence_ids, int) or not 1 <= self.max_evidence_ids <= MAX_EVIDENCE_IDS:
            raise ValueError("max_evidence_ids is outside the configured limit")


@dataclass(frozen=True, slots=True)
class ToolExecutionRecord:
    """Audit-friendly record; text remains untrusted and is never promoted to instructions."""

    tool_name: str
    text: str
    evidence_ids: tuple[str, ...]
    output_chars: int
    untrusted: bool = True
    injection_markers: tuple[str, ...] = ()
    content_sha256: str = ""
    detector_version: str = DETECTOR_VERSION


def _validate_json_value(value: Any, *, depth: int = 0) -> None:
    if depth > MAX_ARGUMENT_DEPTH:
        raise ToolPolicyError("tool arguments exceed the maximum nesting depth")
    if isinstance(value, dict):
        if len(value) > MAX_ARGUMENT_ITEMS:
            raise ToolPolicyError("tool argument object has too many fields")
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ToolPolicyError("tool argument keys must be non-empty strings")
            compact_key = "".join(character for character in key.casefold() if character.isalnum())
            if compact_key == "auth" or any(part in compact_key for part in _SENSITIVE_ARGUMENT_KEY_PARTS):
                raise ToolPolicyError("credential-like tool argument keys are not allowed")
            _validate_json_value(item, depth=depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_ARGUMENT_ITEMS:
            raise ToolPolicyError("tool argument list has too many items")
        for item in value:
            _validate_json_value(item, depth=depth + 1)
    elif isinstance(value, str):
        if len(value) > MAX_ARGUMENT_BYTES:
            raise ToolPolicyError("tool argument string exceeds the configured limit")
    elif value is None or isinstance(value, (bool, int)) or (
        isinstance(value, float) and math.isfinite(value)
    ):
        return
    else:
        raise ToolPolicyError("tool arguments must contain JSON-compatible values")


def _validate_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(arguments, Mapping) or isinstance(arguments, (str, bytes)):
        raise ToolPolicyError("tool arguments must be an object")
    normalized = dict(arguments)
    _validate_json_value(normalized)
    try:
        encoded = json.dumps(normalized, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ToolPolicyError("tool arguments must be JSON serializable") from exc
    if len(encoded) > MAX_ARGUMENT_BYTES:
        raise ToolPolicyError("tool arguments exceed the encoded-size limit")
    return normalized


async def execute_bounded_tool_plan(
    plan: Sequence[ToolCall],
    *,
    tools: Mapping[str, RetrievalTool],
    tenant_id: str,
    actor_scopes: frozenset[str],
    policy: AgenticRetrievalPolicy = AgenticRetrievalPolicy(),
) -> tuple[ToolExecutionRecord, ...]:
    """Execute a sequential plan only through an explicit registry and bounded policy."""
    if not isinstance(tenant_id, str) or not tenant_id.strip() or len(tenant_id) > 200:
        raise ToolPolicyError("tenant_id is required and bounded")
    if not isinstance(plan, Sequence) or isinstance(plan, (str, bytes)):
        raise ToolPolicyError("plan must be a sequence of tool calls")
    if len(plan) > policy.max_steps:
        raise ToolPolicyError("tool plan exceeds the maximum step count")
    if not isinstance(actor_scopes, (set, frozenset)):
        raise ToolPolicyError("actor_scopes must be a set of scope names")
    if any(not isinstance(scope, str) or not scope.strip() for scope in actor_scopes):
        raise ToolPolicyError("actor scopes must be non-empty strings")

    calls_by_tool: dict[str, int] = {}
    records: list[ToolExecutionRecord] = []
    seen_evidence: set[str] = set()
    total_chars = 0

    for call in plan:
        if not isinstance(call, ToolCall):
            raise ToolPolicyError("plan entries must be ToolCall values")
        if not isinstance(call.tool_name, str) or not _TOOL_NAME.fullmatch(call.tool_name):
            raise ToolPolicyError("tool call name is invalid")
        tool = tools.get(call.tool_name)
        if not isinstance(tool, RetrievalTool) or tool.name != call.tool_name:
            raise ToolPolicyError(f"tool {call.tool_name!r} is not allowlisted")
        if not tool.required_scopes.issubset(actor_scopes):
            raise ToolPolicyError(f"actor lacks required scope for tool {tool.name!r}")
        calls_by_tool[tool.name] = calls_by_tool.get(tool.name, 0) + 1
        if calls_by_tool[tool.name] > tool.max_calls:
            raise ToolPolicyError(f"tool {tool.name!r} exceeded its call budget")

        arguments = _validate_arguments(call.arguments)
        try:
            arguments = tool.argument_model.model_validate(arguments).model_dump(mode="json")
        except ValidationError as exc:
            raise ToolPolicyError(f"arguments failed the schema for tool {tool.name!r}") from exc
        try:
            result = await asyncio.wait_for(
                tool.executor(tenant_id, arguments),
                timeout=tool.timeout_seconds,
            )
        except TimeoutError as exc:
            raise ToolExecutionError(f"tool {tool.name!r} timed out") from exc
        except Exception as exc:
            raise ToolExecutionError(f"tool {tool.name!r} failed") from exc

        if not isinstance(result, ToolResult):
            raise ToolExecutionError(f"tool {tool.name!r} returned an invalid result")
        if result.tenant_id != tenant_id:
            raise ToolPolicyError(f"tool {tool.name!r} returned cross-tenant data")
        if len(result.text) > tool.max_output_chars:
            raise ToolPolicyError(f"tool {tool.name!r} exceeded its output budget")
        total_chars += len(result.text)
        if total_chars > policy.max_total_output_chars:
            raise ToolPolicyError("tool plan exceeded the total output budget")
        seen_evidence.update(result.evidence_ids)
        if len(seen_evidence) > policy.max_evidence_ids:
            raise ToolPolicyError("tool plan returned too many unique evidence IDs")
        markers = detect_injection_markers(result.text)
        records.append(
            ToolExecutionRecord(
                tool.name,
                result.text,
                result.evidence_ids,
                len(result.text),
                untrusted=True,
                injection_markers=markers,
                content_sha256=hashlib.sha256(result.text.encode("utf-8")).hexdigest(),
                detector_version=DETECTOR_VERSION,
            )
        )

    return tuple(records)
