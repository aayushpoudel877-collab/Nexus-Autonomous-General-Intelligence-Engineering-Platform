import asyncio
import logging

from services.api.app.services.execution import MAX_FAILURE_REASON

from .config import settings
from .db import SessionLocal, engine
from .executor import FailClosedExecutor
from .repository import claim_next_request, finish_request, requeue_expired_requests


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [nexus-worker] %(message)s",
)
logger = logging.getLogger(__name__)


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

        await db.commit()
        logger.info(
            "claimed execution %s attempt=%s entrypoint=%s",
            request.id,
            request.attempt_count,
            request.entrypoint,
        )

        outcome = await FailClosedExecutor().execute(request)

        async with SessionLocal() as finish_db:
            finished = await finish_request(
                finish_db,
                request_id=request.id,
                worker_id=settings.worker_id,
                success=outcome.success,
                result_json=outcome.result,
                output_bytes=outcome.output_bytes,
                error_code=outcome.error_code,
                failure_reason=(
                    outcome.failure_reason or ""
                )[:MAX_FAILURE_REASON],
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
