"""Authenticated, organization-scoped RAG corpus and lexical retrieval API."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, get_membership, require_roles
from ..db.session import get_db
from ..models import RAGChunk, RAGDocument, User
from ..services.audit import record_audit
from services.rag.chunking import Chunk
from services.rag.persistence import (
    DocumentAlreadyArchived,
    ingest_document,
    list_document_chunks,
    set_document_status,
)
from services.rag.retrieval import hybrid_retrieve, pack_evidence
from ..schemas.rag import (
    RAGChunkRead,
    RAGDocumentCreate,
    RAGDocumentCreated,
    RAGDocumentRead,
    RAGEvidenceRead,
    RAGQueryRequest,
    RAGQueryResponse,
)

router = APIRouter(prefix="/rag", tags=["rag-knowledge"])


@router.post("/documents", response_model=RAGDocumentCreated, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: RAGDocumentCreate,
    response: Response,
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    try:
        document, created = await ingest_document(
            db,
            organization_id=membership.organization_id,
            title=payload.title,
            text=payload.text,
            source_uri=payload.source_uri,
            metadata=payload.metadata,
            max_chars=payload.max_chars,
            overlap=payload.overlap,
        )
    except DocumentAlreadyArchived as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if created:
        await record_audit(
            db,
            action="rag.document.created",
            resource_type="rag_document",
            actor_user_id=user.id,
            organization_id=membership.organization_id,
            resource_id=str(document.id),
            detail={"content_sha256": document.content_sha256, "content_chars": document.content_chars},
        )
    await db.commit()
    await db.refresh(document)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return RAGDocumentCreated(document=RAGDocumentRead.from_record(document), created=created)


@router.get("/documents", response_model=list[RAGDocumentRead])
async def list_documents(
    status_filter: Literal["active", "archived", "deleted"] | None = Query(default="active", alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    statement = select(RAGDocument).where(RAGDocument.organization_id == membership.organization_id)
    if status_filter is not None:
        statement = statement.where(RAGDocument.status == status_filter)
    rows = await db.scalars(
        statement.order_by(RAGDocument.created_at.desc(), RAGDocument.id).offset(offset).limit(limit)
    )
    return [RAGDocumentRead.from_record(item) for item in rows.all()]


async def _active_document(
    db: AsyncSession, *, document_id: UUID, organization_id: UUID
) -> RAGDocument:
    document = await db.scalar(
        select(RAGDocument).where(
            RAGDocument.id == document_id,
            RAGDocument.organization_id == organization_id,
            RAGDocument.status == "active",
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Active RAG document not found")
    return document


@router.get("/documents/{document_id}/chunks", response_model=list[RAGChunkRead])
async def get_document_chunks(
    document_id: UUID,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _active_document(db, document_id=document_id, organization_id=membership.organization_id)
    try:
        chunks = await list_document_chunks(
            db, organization_id=membership.organization_id, document_id=document_id,
            limit=limit, offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [
        RAGChunkRead(
            id=item.id,
            document_id=item.document_id,
            ordinal=item.ordinal,
            text=item.text,
            start_char=item.start_char,
            end_char=item.end_char,
            token_count=item.token_count,
        )
        for item in chunks
    ]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    changed = await set_document_status(
        db, organization_id=membership.organization_id, document_id=document_id, status="deleted"
    )
    if not changed:
        raise HTTPException(status_code=404, detail="RAG document not found")
    await record_audit(
        db,
        action="rag.document.deleted",
        resource_type="rag_document",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(document_id),
    )
    await db.commit()


@router.post("/query", response_model=RAGQueryResponse)
async def query_corpus(
    payload: RAGQueryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    rows = await db.execute(
        select(RAGChunk, RAGDocument)
        .join(
            RAGDocument,
            (RAGDocument.id == RAGChunk.document_id)
            & (RAGDocument.organization_id == RAGChunk.organization_id),
        )
        .where(
            RAGChunk.organization_id == membership.organization_id,
            RAGDocument.organization_id == membership.organization_id,
            RAGDocument.status == "active",
        )
        .order_by(RAGDocument.created_at.desc(), RAGChunk.ordinal.asc())
        .limit(2_000)
    )
    pairs = rows.all()
    chunks = [
        Chunk(
            chunk_id=str(chunk.id),
            document_id=str(document.id),
            tenant_id=str(membership.organization_id),
            text=chunk.text,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            ordinal=chunk.ordinal,
        )
        for chunk, document in pairs
    ]
    hits = hybrid_retrieve(
        payload.query.strip(),
        chunks,
        tenant_id=str(membership.organization_id),
        top_k=payload.top_k,
        character_ngram_weight=payload.character_ngram_weight,
    )
    documents = {str(document.id): document for _, document in pairs}
    evidence = pack_evidence(
        hits,
        document_titles={key: item.title for key, item in documents.items()},
        source_uris={key: item.source_uri for key, item in documents.items()},
    )
    return RAGQueryResponse(
        query=payload.query.strip(),
        retrieval_mode="lexical",
        evidence=[
            RAGEvidenceRead(
                evidence_id=item.evidence_id,
                document_id=UUID(item.document_id),
                chunk_id=UUID(item.chunk_id),
                title=item.title,
                source_uri=item.source_uri,
                text=item.text,
                start_char=item.start_char,
                end_char=item.end_char,
                score=item.score,
            )
            for item in evidence
        ],
        note=(
            "Lexical retrieval only; optional character n-gram matching can assist scripts "
            "without whitespace segmentation. Embeddings and generated answers are not enabled."
        ),
    )
