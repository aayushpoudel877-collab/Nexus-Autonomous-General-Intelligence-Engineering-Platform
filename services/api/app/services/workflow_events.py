"""Durable workflow event journal helpers.

Events contain workflow control metadata only. Secret values and credential-like
payloads are deliberately rejected before persistence.
"""

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.workflow_event import WorkflowEvent

_FORBIDDEN_KEYS = {"secret", "token", "password", "credential", "api_key"}


def _validate_payload(payload: dict) -> dict:
    """Validate and normalize JSON event data, including every nested key/value."""
    if not isinstance(payload, dict):
        raise TypeError("Workflow event payload must be an object")

    def inspect(value, depth: int = 0) -> None:
        if depth > 16:
            raise ValueError("Workflow event payload is nested too deeply")
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise TypeError("Workflow event payload keys must be strings")
                lowered = key.lower()
                if any(term in lowered for term in _FORBIDDEN_KEYS):
                    raise ValueError(
                        "Workflow event payload cannot contain credential-like fields"
                    )
                inspect(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                inspect(child, depth + 1)
        elif value is not None and not isinstance(value, (str, int, float, bool)):
            raise TypeError("Workflow event payload must contain only JSON values")

    inspect(payload)
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("Workflow event payload must contain valid JSON values") from exc
    if len(encoded.encode("utf-8")) > 16_384:
        raise ValueError("Workflow event payload is too large")
    return json.loads(encoded)


async def append_workflow_event(
    db: AsyncSession,
    *,
    run_id: UUID,
    event_type: str,
    node_run_id: UUID | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    attempt: int = 0,
    payload: dict | None = None,
    actor: str = "orchestrator",
) -> WorkflowEvent:
    if not event_type or len(event_type) > 60:
        raise ValueError("Invalid workflow event type")
    if not 0 <= attempt <= 100000:
        raise ValueError("Invalid workflow event attempt")
    event = WorkflowEvent(
        run_id=run_id,
        node_run_id=node_run_id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        attempt=attempt,
        payload_json=_validate_payload(payload if payload is not None else {}),
        actor=actor,
    )
    db.add(event)
    await db.flush()
    return event


async def list_workflow_events(db: AsyncSession, *, run_id: UUID, limit: int = 100) -> list[WorkflowEvent]:
    if not 1 <= limit <= 500:
        raise ValueError("Event limit must be between 1 and 500")
    rows = await db.scalars(
        select(WorkflowEvent)
        .where(WorkflowEvent.run_id == run_id)
        .order_by(WorkflowEvent.sequence.desc())
        .limit(limit)
    )
    return list(rows.all())
