"""Async persistence helpers for the NEXUS RAG corpus.

Authorization must be performed by the API before calling these functions. Every
read/update is still scoped by organization_id to reduce accidental cross-tenant access.
"""
from __future__ import annotations

import json
import re
from hashlib import sha256
from uuid import UUID
from collections.abc import Mapping
from typing import Any, Awaitable, Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.rag import RAGChunk, RAGDocument
from services.api.app.models.audit import AuditEvent
from .chunking import Chunk, chunk_text

MAX_DOCUMENT_CHARS = 2_000_000
MAX_CHUNK_CHARS = 12_000
MAX_METADATA_BYTES = 16_384


class DocumentAlreadyArchived(ValueError):
    """Raised when an archived or deleted document is selected for new ingestion."""


async def ingest_document(
    session: AsyncSession,
    *,
    organization_id: UUID,
    title: str,
    text: str,
    source_uri: str = "",
    metadata: dict | None = None,
    max_chars: int = 1200,
    overlap: int = 160,
) -> tuple[RAGDocument, bool]:
    """Persist a document and chunks idempotently by organization + content hash.

    Returns (document, created). The caller owns the transaction and commit boundary.
    """
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be a non-empty string")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("document text must be a non-empty string")
    if not isinstance(source_uri, str):
        raise TypeError("source_uri must be a string")
    if len(title) > 300 or len(source_uri) > 2048:
        raise ValueError("title or source_uri exceeds the supported length")
    if len(text) > MAX_DOCUMENT_CHARS:
        raise ValueError(f"document text exceeds {MAX_DOCUMENT_CHARS} characters")
    if not 100 <= max_chars <= MAX_CHUNK_CHARS or not 0 <= overlap < max_chars:
        raise ValueError(f"require 100 <= max_chars <= {MAX_CHUNK_CHARS} and 0 <= overlap < max_chars")

    metadata_value = {} if metadata is None else metadata
    if not isinstance(metadata_value, dict):
        raise TypeError("metadata must be a JSON object")
    try:
        metadata_size = len(json.dumps(metadata_value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("metadata must contain JSON-serializable values") from exc
    if metadata_size > MAX_METADATA_BYTES:
        raise ValueError(f"metadata exceeds {MAX_METADATA_BYTES} bytes")

    digest = sha256(text.encode("utf-8")).hexdigest()
    existing = await session.scalar(
        select(RAGDocument).where(
            RAGDocument.organization_id == organization_id,
            RAGDocument.content_sha256 == digest,
        )
    )
    if existing is not None:
        if existing.status != "active":
            raise DocumentAlreadyArchived("matching document exists but is not active")
        return existing, False

    document = RAGDocument(
        organization_id=organization_id,
        title=title.strip(),
        source_uri=source_uri,
        content_sha256=digest,
        content_chars=len(text),
        metadata_json=metadata_value,
    )
    chunks: list[Chunk] = chunk_text(
        text, str(document.id or "pending"), str(organization_id),
        max_chars=max_chars, overlap=overlap,
    )
    try:
        # A savepoint keeps a uniqueness race from invalidating the caller's outer
        # transaction. The API still owns the outer commit/rollback boundary.
        async with session.begin_nested():
            session.add(document)
            await session.flush()
            for part in chunks:
                session.add(RAGChunk(
                    organization_id=organization_id,
                    document_id=document.id,
                    ordinal=part.ordinal,
                    text=part.text,
                    start_char=part.start_char,
                    end_char=part.end_char,
                    token_count=len(part.text.split()),
                ))
            await session.flush()
    except IntegrityError:
        # Under PostgreSQL READ COMMITTED, the winning concurrent insert is visible
        # after its uniqueness conflict resolves. Re-raise unrelated integrity errors.
        existing = await session.scalar(
            select(RAGDocument).where(
                RAGDocument.organization_id == organization_id,
                RAGDocument.content_sha256 == digest,
            )
        )
        if existing is None:
            raise
        if existing.status != "active":
            raise DocumentAlreadyArchived("matching document exists but is not active")
        return existing, False
    return document, True


async def list_document_chunks(
    session: AsyncSession, *, organization_id: UUID, document_id: UUID,
    limit: int = 200, offset: int = 0,
) -> list[RAGChunk]:
    """List chunks only when both document and organization scope match."""
    if not 1 <= limit <= 1000 or not 0 <= offset <= 1_000_000:
        raise ValueError("invalid pagination bounds")
    result = await session.scalars(
        select(RAGChunk)
        .where(
            RAGChunk.organization_id == organization_id,
            RAGChunk.document_id == document_id,
        )
        .order_by(RAGChunk.ordinal.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.all())


async def set_document_status(
    session: AsyncSession, *, organization_id: UUID, document_id: UUID, status: str,
) -> bool:
    """Apply monotonic lifecycle transitions; return whether a tenant-scoped row matched.

    Allowed transitions are active -> archived/deleted and archived -> deleted.
    Repeating the current status is idempotent. Deleted documents cannot be restored.
    """
    if status not in {"active", "archived", "deleted"}:
        raise ValueError("unsupported document status")
    allowed_current = {
        "active": ("active",),
        "archived": ("active", "archived"),
        "deleted": ("active", "archived", "deleted"),
    }[status]
    result = await session.execute(
        update(RAGDocument)
        .where(
            RAGDocument.id == document_id,
            RAGDocument.organization_id == organization_id,
            RAGDocument.status.in_(allowed_current),
        )
        .values(status=status)
    )
    return result.rowcount == 1

_AUDIT_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def build_database_tool_audit_writer(
    session: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID | None = None,
    request_id: str | None = None,
) -> Callable[[str, Mapping[str, Any]], Awaitable[None]]:
    """Create an audit writer bound to authenticated context and the caller's transaction.

    The returned async writer is compatible with execute_bounded_tool_plan_with_audit.
    It validates the tenant against the organization captured from authenticated request
    context, verifies the sealed metadata-only envelope, adds an existing AuditEvent,
    and flushes without committing. The caller owns commit/rollback, so audit persistence
    participates in the same database transaction as related application changes.
    """
    if not isinstance(organization_id, UUID):
        raise TypeError("organization_id must be a UUID from authenticated context")
    if actor_user_id is not None and not isinstance(actor_user_id, UUID):
        raise TypeError("actor_user_id must be a UUID or None")
    if request_id is not None and (
        not isinstance(request_id, str) or not _AUDIT_REQUEST_ID.fullmatch(request_id)
    ):
        raise ValueError("request_id must be a bounded opaque identifier")

    async def write(tenant_id: str, envelope: Mapping[str, Any]) -> None:
        try:
            supplied_organization_id = UUID(tenant_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("tenant_id must match the authenticated organization") from exc
        if supplied_organization_id != organization_id:
            raise PermissionError("tool audit tenant does not match authenticated organization")
        if not isinstance(envelope, dict):
            raise TypeError("audit envelope must be a dictionary")

        from .governance import stable_json, verify_tool_provenance_audit_details

        if not verify_tool_provenance_audit_details(envelope):
            raise ValueError("tool provenance audit envelope failed verification")
        details = json.loads(stable_json(envelope))
        event = AuditEvent(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="rag.tool_execution.completed",
            resource_type="rag_tool_execution",
            resource_id=request_id,
            detail=details,
            request_id=request_id,
        )
        session.add(event)
        await session.flush()

    return write

