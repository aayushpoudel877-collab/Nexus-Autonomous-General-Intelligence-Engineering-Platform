"""Async persistence helpers for the NEXUS RAG corpus.

Authorization must be performed by the API before calling these functions. Every
read/update is still scoped by organization_id to reduce accidental cross-tenant access.
"""
from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.rag import RAGChunk, RAGDocument
from .chunking import Chunk, chunk_text


class DocumentAlreadyArchived(ValueError):
    """Raised when an archived document is selected for a new ingestion operation."""


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
    if not title.strip():
        raise ValueError("title must not be empty")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("document text must not be empty")
    if len(title) > 300 or len(source_uri) > 2048:
        raise ValueError("title or source_uri exceeds the supported length")
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
        metadata_json=metadata or {},
    )
    chunks: list[Chunk] = chunk_text(
        text, str(document.id or "pending"), str(organization_id),
        max_chars=max_chars, overlap=overlap,
    )
    session.add(document)
    await session.flush()
    # Re-key chunks to the database-generated document UUID after flush.
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
    """Update lifecycle state with tenant-scoped predicates; return whether a row matched."""
    if status not in {"active", "archived", "deleted"}:
        raise ValueError("unsupported document status")
    result = await session.execute(
        update(RAGDocument)
        .where(
            RAGDocument.id == document_id,
            RAGDocument.organization_id == organization_id,
        )
        .values(status=status)
    )
    return result.rowcount == 1
