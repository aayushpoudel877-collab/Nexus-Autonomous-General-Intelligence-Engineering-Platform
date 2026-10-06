import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from services.api.app.models import ExecutionRequest, IntegrationConnection, SecretGrant
from services.api.app.services.audit import record_audit
from services.api.app.services.execution import MAX_FAILURE_REASON

from .config import settings
from .db import SessionLocal, engine
from .executor import ExecutionOutcome, SandboxAdmissionExecutor
from .repository import claim_next_request, finish_request, heartbeat_request, requeue_expired_requests
from services.secrets.broker import SecretGrantSpec


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [nexus-worker] %(message)s",
)
logger = logging.getLogger(__name__)


async def _heartbeat_loop(request_id, stop_event: asyncio.Event) -> None:
    interval = max(1.0, min(30.0, settings.lease_seconds / 3))
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            pass

        async with SessionLocal() as heartbeat_db:
            refreshed = await heartbeat_request(
                heartbeat_db,
                request_id=request_id,
                worker_id=settings.worker_id,
                lease_seconds=settings.lease_seconds,
            )
            await heartbeat_db.commit()
            if not refreshed:
                logger.warning(
                    "execution %s lost worker lease during heartbeat",
                    request_id,
                )
                return


async def _load_secret_grants(request_id) -> list[SecretGrantSpec]:
    async with SessionLocal() as db:
        request = await db.get(ExecutionRequest, request_id)
        if request is None:
            return []
        grant_ids = list(dict.fromkeys(request.secret_grant_ids or []))
        if not grant_ids:
            return []
        rows = await db.execute(
            select(SecretGrant, IntegrationConnection)
            .join(
                IntegrationConnection,
                SecretGrant.integration_id == IntegrationConnection.id,
            )
            .where(
                SecretGrant.organization_id == request.organization_id,
                SecretGrant.installation_id == request.installation_id,
                SecretGrant.id.in_(grant_ids),
                SecretGrant.status == "approved",
                SecretGrant.expires_at.is_not(None),
                SecretGrant.expires_at > datetime.now(timezone.utc),
                IntegrationConnection.organization_id == request.organization_id,
                IntegrationConnection.status == "active",
            )
        )
        grants = rows.all()
        specs = [
            SecretGrantSpec(
                grant_id=str(grant.id),
                secret_ref=integration.secret_ref,
            )
            for grant, integration in grants
            if integration.secret_ref
        ]
        return specs

async def _is_execution_cancelled(request_id) -> bool:
    try:
        async with SessionLocal() as db:
            status = await db.scalar(
                select(ExecutionRequest.status).where(ExecutionRequest.id == request_id)
            )
            return status == "cancelled"
    except Exception:
        logger.exception(
            "could not check cancellation state for execution %s; failing closed",
            request_id,
        )
        return True


async def process_one() -> bool:
    async with SessionLocal() as db:
        requeued = await requeue_expired_requests(db)
        request = await claim_next_request(
            db,
            worker_id=settings.worker_id,
            lease_seconds=settings.lease_seconds,
        )
        if request is None:
            await db.commit()
            if requeued:
                logger.info("requeued %s expired execution request(s)", requeued)
            return False

        await record_audit(
            db,
            action="execution.worker_claimed",
            resource_type="execution_request",
            organization_id=request.organization_id,
            resource_id=str(request.id),
            detail={
                "worker_id": settings.worker_id,
                "attempt": request.attempt_count,
                "entrypoint": request.entrypoint,
            },
        )
        await db.commit()
        logger.info(
            "claimed execution %s attempt=%s entrypoint=%s",
            request.id,
            request.attempt_count,
            request.entrypoint,
        )

    stop_event = asyncio.Event()
    heartbeat_task = asyncio.create_task(_heartbeat_loop(request.id, stop_event))
    try:
        secret_grants = await _load_secret_grants(request.id)
        outcome = await SandboxAdmissionExecutor().execute(
            request,
            cancellation_check=lambda: _is_execution_cancelled(request.id),
            secret_grants=secret_grants,
        )
    except Exception:
        logger.exception("execution %s failed inside worker", request.id)
        outcome = ExecutionOutcome(
            success=False,
            result={"status": "failed"},
            output_bytes=0,
            error_code="worker_error",
            failure_reason="Execution backend failed unexpectedly; inspect worker logs for details.",
        )
    finally:
        stop_event.set()
        await heartbeat_task

    async with SessionLocal() as finish_db:
        finished = await finish_request(
            finish_db,
            request_id=request.id,
            worker_id=settings.worker_id,
            success=outcome.success,
            result_json=outcome.result,
            output_bytes=outcome.output_bytes,
            error_code=outcome.error_code,
            failure_reason=(outcome.failure_reason or "")[:MAX_FAILURE_REASON],
        )
        current_status = await finish_db.scalar(
            select(ExecutionRequest.status).where(ExecutionRequest.id == request.id)
        )
        audit_action = (
            "execution.worker_finished"
            if finished
            else (
                "execution.worker_cancelled"
                if current_status == "cancelled"
                else "execution.worker_lease_lost"
            )
        )
        await record_audit(
            finish_db,
            action=audit_action,
            resource_type="execution_request",
            organization_id=request.organization_id,
            resource_id=str(request.id),
            detail={
                "worker_id": settings.worker_id,
                "status": current_status or ("succeeded" if outcome.success else "failed"),
                "error_code": outcome.error_code,
                "lease_owned": finished,
                "sandbox_cancelled": outcome.result.get("status") == "cancelled",
            },
        )
        await finish_db.commit()

    if not finished:
        logger.warning(
            "execution %s was not completed because the lease is no longer owned",
            request.id,
        )
    return True


async def run() -> None:
    logger.info(
        "starting worker id=%s poll=%ss lease=%ss",
        settings.worker_id,
        settings.poll_seconds,
        settings.lease_seconds,
    )
    try:
        while True:
            did_work = await process_one()
            if not did_work:
                await asyncio.sleep(settings.poll_seconds)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
