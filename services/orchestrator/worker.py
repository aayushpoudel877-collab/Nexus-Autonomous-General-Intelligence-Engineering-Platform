"""Continuous durable workflow run worker with row-lock claiming and leases."""

import asyncio
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from services.api.app.db.session import SessionLocal
from services.api.app.models.workflow import WorkflowRun
from services.api.app.services.audit import record_audit

from .engine import DEFAULT_LEASE_SECONDS, load_run, tick_run

POLL_SECONDS = max(0.2, float(os.getenv("NEXUS_ORCHESTRATOR_POLL_SECONDS", "2")))
LEASE_SECONDS = max(30, int(os.getenv("NEXUS_ORCHESTRATOR_LEASE_SECONDS", str(DEFAULT_LEASE_SECONDS))))
BATCH_SIZE = max(1, min(32, int(os.getenv("NEXUS_ORCHESTRATOR_BATCH_SIZE", "8"))))
WORKER_ID = os.getenv("NEXUS_ORCHESTRATOR_WORKER_ID", f"orchestrator:{socket.gethostname()}:{uuid.uuid4().hex[:12]}")


async def claim_runs(db):
    now = datetime.now(timezone.utc)
    statement = (
        select(WorkflowRun)
        .where(
            or_(
                WorkflowRun.status == "queued",
                (WorkflowRun.status == "running")
                & or_(
                    WorkflowRun.worker_id == WORKER_ID,
                    WorkflowRun.lease_expires_at.is_(None),
                    WorkflowRun.lease_expires_at <= now,
                ),
            )
        )
        .order_by(WorkflowRun.created_at)
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )
    rows = list((await db.scalars(statement)).all())
    for run in rows:
        run.worker_id = WORKER_ID
        run.attempt_count += 1
        run.heartbeat_at = now
        run.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
    return rows


async def run_once() -> int:
    processed = 0
    async with SessionLocal() as db:
        try:
            claimed = await claim_runs(db)
            await db.flush()
            for claimed_run in claimed:
                run = await load_run(db, claimed_run.id)
                if run is None:
                    continue
                try:
                    await tick_run(
                        db,
                        run,
                        organization_id=run.organization_id,
                        worker_id=WORKER_ID,
                        lease_seconds=LEASE_SECONDS,
                    )
                except Exception as exc:
                    run.status = "failed"
                    run.failure_reason = str(exc)[:4000] if hasattr(run, "failure_reason") else None
                    run.finished_at = datetime.now(timezone.utc)
                    run.worker_id = None
                    run.lease_expires_at = None
                    await record_audit(
                        db,
                        action="workflow.worker.failed",
                        resource_type="workflow_run",
                        organization_id=run.organization_id,
                        resource_id=str(run.id),
                        detail={"error": type(exc).__name__},
                    )
                processed += 1
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return processed


async def main() -> None:
    while True:
        count = await run_once()
        await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
