from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models import ExecutionRequest
from services.api.app.services.execution import (
    execution_lease_expiry,
    normalize_failure_reason,
    should_retry_execution,
)


async def requeue_expired_requests(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    current = now or datetime.now(timezone.utc)
    rows = await db.scalars(
        select(ExecutionRequest)
        .where(
            ExecutionRequest.status == "running",
            ExecutionRequest.lease_expires_at.is_not(None),
            ExecutionRequest.lease_expires_at <= current,
        )
        .order_by(ExecutionRequest.created_at)
        .with_for_update(skip_locked=True)
        .limit(100)
    )
    changed = 0
    for record in rows.all():
        if should_retry_execution(record.attempt_count):
            record.status = "queued"
            record.worker_id = None
            record.lease_expires_at = None
            record.heartbeat_at = None
            record.error_code = "worker_lease_expired"
            record.failure_reason = normalize_failure_reason(
                "Worker lease expired; execution returned to the queue"
            )
        else:
            record.status = "failed"
            record.worker_id = None
            record.lease_expires_at = None
            record.heartbeat_at = None
            record.finished_at = current
            record.error_code = "worker_lease_expired"
            record.failure_reason = normalize_failure_reason(
                "Worker lease expired and retry limit was reached"
            )
        changed += 1
    return changed


async def claim_next_request(
    db: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int,
    now: datetime | None = None,
) -> ExecutionRequest | None:
    current = now or datetime.now(timezone.utc)
    record = await db.scalar(
        select(ExecutionRequest)
        .where(ExecutionRequest.status == "queued")
        .order_by(ExecutionRequest.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if record is None:
        return None

    record.status = "running"
    record.worker_id = worker_id
    record.attempt_count += 1
    record.heartbeat_at = current
    record.lease_expires_at = execution_lease_expiry(
        now=current,
        lease_seconds=lease_seconds,
    )
    if record.started_at is None:
        record.started_at = current
    record.failure_reason = None
    record.error_code = None
    await db.flush()
    return record


async def heartbeat_request(
    db: AsyncSession,
    *,
    request_id: UUID,
    worker_id: str,
    lease_seconds: int,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    result = await db.execute(
        update(ExecutionRequest)
        .where(
            ExecutionRequest.id == request_id,
            ExecutionRequest.worker_id == worker_id,
            ExecutionRequest.status == "running",
        )
        .values(
            heartbeat_at=current,
            lease_expires_at=execution_lease_expiry(
                now=current,
                lease_seconds=lease_seconds,
            ),
        )
    )
    return result.rowcount == 1


async def finish_request(
    db: AsyncSession,
    *,
    request_id: UUID,
    worker_id: str,
    success: bool,
    result_json: dict,
    output_bytes: int,
    error_code: str | None = None,
    failure_reason: str | None = None,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    values = {
        "status": "succeeded" if success else "failed",
        "result_json": result_json,
        "output_bytes": output_bytes,
        "error_code": error_code,
        "failure_reason": normalize_failure_reason(failure_reason or ""),
        "finished_at": current,
        "lease_expires_at": None,
        "heartbeat_at": None,
        "worker_id": None,
    }
    result = await db.execute(
        update(ExecutionRequest)
        .where(
            ExecutionRequest.id == request_id,
            ExecutionRequest.worker_id == worker_id,
            ExecutionRequest.status == "running",
        )
        .values(**values)
    )
    return result.rowcount == 1
