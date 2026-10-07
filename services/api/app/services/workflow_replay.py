"""Deterministic, read-only workflow replay from the durable event journal."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.workflow_event import WorkflowEvent


@dataclass(frozen=True)
class ReplayNode:
    node_key: str
    status: str


@dataclass(frozen=True)
class WorkflowReplay:
    run_id: UUID
    event_count: int
    replay_checksum: str
    projected_status: str | None
    projected_nodes: tuple[ReplayNode, ...]
    drifted: bool


def _canonical_event(event: WorkflowEvent) -> bytes:
    payload = {
        "sequence": event.sequence,
        "event_type": event.event_type,
        "from_status": event.from_status,
        "to_status": event.to_status,
        "attempt": event.attempt,
        "payload": event.payload_json,
        "actor": event.actor,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()


async def replay_workflow_run(
    db: AsyncSession,
    *,
    run_id: UUID,
    live_status: str,
    live_nodes: dict[str, str],
) -> WorkflowReplay:
    rows = await db.scalars(
        select(WorkflowEvent)
        .where(WorkflowEvent.run_id == run_id)
        .order_by(WorkflowEvent.sequence.asc())
    )
    events = list(rows.all())
    digest = hashlib.sha256()
    projected_status: str | None = None
    projected_nodes: dict[str, str] = {}

    for event in events:
        digest.update(_canonical_event(event))
        if event.to_status:
            projected_status = event.to_status
        if event.event_type == "workflow.tick":
            node_statuses = event.payload_json.get("node_statuses", {})
            if isinstance(node_statuses, dict):
                for key, status in node_statuses.items():
                    if isinstance(key, str) and isinstance(status, str):
                        projected_nodes[key] = status

    projected_tuple = tuple(
        ReplayNode(node_key=key, status=projected_nodes[key])
        for key in sorted(projected_nodes)
    )
    drifted = (
        projected_status is not None
        and projected_status != live_status
    ) or {
        node.node_key: node.status for node in projected_tuple
    } != live_nodes

    return WorkflowReplay(
        run_id=run_id,
        event_count=len(events),
        replay_checksum=digest.hexdigest(),
        projected_status=projected_status,
        projected_nodes=projected_tuple,
        drifted=drifted,
    )
