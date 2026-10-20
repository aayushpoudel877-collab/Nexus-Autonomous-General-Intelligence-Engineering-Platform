"""Phase 53: PostgreSQL integration tests for provenance audit idempotency.

These tests intentionally use the migrated CI database; they are skipped in local
runs without DATABASE_URL rather than silently substituting SQLite semantics.
"""
import asyncio
import os
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from services.api.app.models import AuditEvent, Organization, User
from services.rag.governance import seal_tool_provenance_audit_details
from services.rag.persistence import build_database_tool_audit_writer

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not DATABASE_URL.startswith("postgresql+asyncpg://"),
    reason="requires the PostgreSQL integration database configured by CI",
)


def _envelope(output_chars: int = 8) -> dict:
    return seal_tool_provenance_audit_details({
        "schema_version": 1,
        "tool_outputs": [{
            "tool_name": "lexical_search",
            "content_sha256": "b" * 64,
            "detector_version": "markers-v1",
            "injection_markers": [],
            "output_chars": output_chars,
            "evidence_count": 0,
            "untrusted": True,
        }],
    })


async def _identity(session_factory):
    organization_id = uuid4()
    actor_id = uuid4()
    async with session_factory() as session:
        session.add(Organization(
            id=organization_id,
            name="Phase 53 test organization",
            slug=f"phase53-{organization_id.hex}",
        ))
        session.add(User(
            id=actor_id,
            email=f"phase53-{actor_id.hex}@example.invalid",
            full_name="Phase 53 Integration Test",
            password_hash="not-a-real-password-hash",
            is_active=True,
        ))
        await session.commit()
    return organization_id, actor_id


async def _persist(session_factory, organization_id, actor_id, request_id, envelope):
    async with session_factory() as session:
        try:
            writer = build_database_tool_audit_writer(
                session,
                organization_id=organization_id,
                actor_user_id=actor_id,
                request_id=request_id,
            )
            await writer(str(organization_id), envelope)
            await session.commit()
            return "ok"
        except Exception as exc:
            await session.rollback()
            return exc


async def _count_request(session_factory, organization_id, request_id):
    async with session_factory() as session:
        return await session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action == "rag.tool_execution.completed",
                AuditEvent.request_id == request_id,
            )
        )


@pytest.mark.asyncio
async def test_postgres_exact_retry_persists_only_one_event():
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        organization_id, actor_id = await _identity(session_factory)
        request_id = f"phase53-replay-{uuid4().hex}"
        envelope = _envelope()
        assert await _persist(session_factory, organization_id, actor_id, request_id, envelope) == "ok"
        assert await _persist(session_factory, organization_id, actor_id, request_id, deepcopy(envelope)) == "ok"
        assert await _count_request(session_factory, organization_id, request_id) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_request_id_reuse_with_changed_metadata_fails_closed():
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        organization_id, actor_id = await _identity(session_factory)
        request_id = f"phase53-conflict-{uuid4().hex}"
        assert await _persist(session_factory, organization_id, actor_id, request_id, _envelope()) == "ok"
        result = await _persist(session_factory, organization_id, actor_id, request_id, _envelope(99))
        assert isinstance(result, ValueError)
        assert "already used" in str(result)
        assert await _count_request(session_factory, organization_id, request_id) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_concurrent_same_request_id_never_creates_duplicates():
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=0)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        organization_id, actor_id = await _identity(session_factory)
        request_id = f"phase53-race-{uuid4().hex}"
        envelope = _envelope()
        results = await asyncio.gather(
            _persist(session_factory, organization_id, actor_id, request_id, envelope),
            _persist(session_factory, organization_id, actor_id, request_id, deepcopy(envelope)),
        )
        assert "ok" in results
        assert await _count_request(session_factory, organization_id, request_id) == 1
        # A race loser may receive a unique-constraint IntegrityError. The invariant
        # is one persisted event; retries are safe after the caller checks stored state.
    finally:
        await engine.dispose()
