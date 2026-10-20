"""Tenant-scoped verification of the persisted RAG corpus.

The caller must supply a session and an organization ID from trusted scheduler
configuration. This module never loads raw source documents or sends data externally.
"""
from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.audit import AuditEvent
from services.api.app.models.rag import RAGChunk, RAGDocument
from .source_integrity import IntegrityReceipt, MAX_ARTIFACT_BYTES


def _reconstruct_indexed_text(
    document: RAGDocument, chunks: list[RAGChunk]
) -> tuple[bytes | None, str | None]:
    """Reconstruct normalized indexed text from overlapping chunks and offsets."""
    size = document.content_chars
    if size < 0 or size > MAX_ARTIFACT_BYTES:
        return None, "indexed_content_exceeds_size_limit"
    if size == 0:
        return (b"", None) if not chunks else (None, "unexpected_chunks_for_empty_document")
    if not chunks:
        return None, "indexed_chunks_unavailable"

    characters: list[str | None] = [None] * size
    for chunk in chunks:
        if chunk.start_char < 0 or chunk.end_char > size:
            return None, "chunk_offset_out_of_bounds"
        if chunk.end_char <= chunk.start_char:
            return None, "invalid_chunk_offsets"
        if len(chunk.text) != chunk.end_char - chunk.start_char:
            return None, "chunk_text_offset_length_mismatch"
        for offset, character in enumerate(chunk.text, start=chunk.start_char):
            previous = characters[offset]
            if previous is not None and previous != character:
                return None, "overlapping_chunk_conflict"
            characters[offset] = character

    if any(character is None for character in characters):
        return None, "indexed_chunk_gap"
    return "".join(character for character in characters if character is not None).encode("utf-8"), None


async def verify_persisted_document(
    session: AsyncSession, *, organization_id: UUID, document_id: UUID
) -> IntegrityReceipt | None:
    """Verify a document and its stored chunks within one tenant boundary.

    Returns None when the document is not visible in the supplied organization.
    The receipt is persisted to audit_events for mismatches/unavailable records;
    the caller owns transaction commit/rollback.
    """
    document = await session.scalar(
        select(RAGDocument).where(
            RAGDocument.id == document_id,
            RAGDocument.organization_id == organization_id,
        )
    )
    if document is None:
        return None

    chunks_result = await session.scalars(
        select(RAGChunk)
        .where(
            RAGChunk.document_id == document_id,
            RAGChunk.organization_id == organization_id,
        )
        .order_by(RAGChunk.ordinal.asc())
    )
    chunks = list(chunks_result.all())
    content, reason = _reconstruct_indexed_text(document, chunks)
    if reason is not None:
        receipt = IntegrityReceipt(
            artifact_id=str(document.id),
            expected_sha256=document.content_sha256,
            observed_sha256=None,
            status="unavailable",
            size_bytes=None,
            reason=reason,
        )
    else:
        observed = sha256(content or b"").hexdigest()
        matches = observed == document.content_sha256.lower()
        receipt = IntegrityReceipt(
            artifact_id=str(document.id),
            expected_sha256=document.content_sha256,
            observed_sha256=observed,
            status="verified" if matches else "mismatch",
            size_bytes=len(content or b""),
            reason=None if matches else "sha256_mismatch",
        )

    if receipt.status in {"mismatch", "unavailable", "not_checked"}:
        session.add(
            AuditEvent(
                organization_id=organization_id,
                action="rag.source_integrity.failed",
                resource_type="rag_document",
                resource_id=str(document.id),
                detail={
                    "status": receipt.status,
                    "expected_sha256": receipt.expected_sha256,
                    "observed_sha256": receipt.observed_sha256,
                    "size_bytes": receipt.size_bytes,
                    "reason": receipt.reason,
                },
            )
        )
        await session.flush()
    return receipt


async def scan_organization_integrity(
    session: AsyncSession, *, organization_id: UUID, limit: int = 100
) -> list[IntegrityReceipt]:
    """Scan at most limit active documents for one organization."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    ids = await session.scalars(
        select(RAGDocument.id)
        .where(
            RAGDocument.organization_id == organization_id,
            RAGDocument.status == "active",
        )
        .order_by(RAGDocument.created_at.asc(), RAGDocument.id.asc())
        .limit(limit)
    )
    receipts: list[IntegrityReceipt] = []
    for document_id in ids.all():
        receipt = await verify_persisted_document(
            session, organization_id=organization_id, document_id=document_id
        )
        if receipt is not None:
            receipts.append(receipt)
    return receipts
