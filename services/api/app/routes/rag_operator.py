"""Tenant-scoped operator endpoints for RAG health, feedback, and reindex approval."""
from hashlib import sha256
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, get_membership, require_roles
from ..db.session import get_db
from ..models import RAGChunk, RAGDocument, User
from ..models.rag import RAGFeedback, RAGReindexRequest
from ..services.audit import record_audit

router = APIRouter(prefix="/rag/operator", tags=["rag-operator"])


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    rating: Literal["helpful", "unhelpful"]
    note: str = Field(default="", max_length=1000)

    @field_validator("query")
    @classmethod
    def query_has_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must contain non-whitespace characters")
        return value.strip()

    @field_validator("evidence_ids")
    @classmethod
    def evidence_ids_are_bounded(cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > 100 for value in values):
            raise ValueError("evidence IDs must be non-empty and at most 100 characters")
        if len(set(values)) != len(values):
            raise ValueError("evidence IDs must be unique")
        return values


class FeedbackStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["triaged", "resolved", "ignored"]


class ReindexRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reason_has_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must contain non-whitespace characters")
        return value.strip()


class ReindexReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]


@router.get("/health")
async def operator_health(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    membership = await get_membership(user, db)
    org_id = membership.organization_id
    document_counts = await db.execute(
        select(RAGDocument.status, func.count(RAGDocument.id))
        .where(RAGDocument.organization_id == org_id)
        .group_by(RAGDocument.status)
    )
    chunk_count = await db.scalar(
        select(func.count(RAGChunk.id)).where(RAGChunk.organization_id == org_id)
    )
    pending_feedback = await db.scalar(
        select(func.count(RAGFeedback.id)).where(
            RAGFeedback.organization_id == org_id, RAGFeedback.status == "new"
        )
    )
    pending_reindex = await db.scalar(
        select(func.count(RAGReindexRequest.id)).where(
            RAGReindexRequest.organization_id == org_id,
            RAGReindexRequest.status == "pending_approval",
        )
    )
    return {
        "documents": {row[0]: row[1] for row in document_counts.all()},
        "chunks": int(chunk_count or 0),
        "new_feedback": int(pending_feedback or 0),
        "pending_reindex_approvals": int(pending_reindex or 0),
        "retrieval_mode": "lexical",
        "reindex_execution": "not_connected",
    }


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    row = RAGFeedback(
        organization_id=membership.organization_id,
        actor_user_id=user.id,
        query_sha256=sha256(payload.query.encode("utf-8")).hexdigest(),
        evidence_ids=payload.evidence_ids,
        rating=payload.rating,
        note=payload.note.strip(),
    )
    db.add(row)
    await record_audit(
        db,
        action="rag.feedback.created",
        resource_type="rag_feedback",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=None,
        detail={"rating": payload.rating, "evidence_count": len(payload.evidence_ids)},
    )
    await db.commit()
    await db.refresh(row)
    return _feedback_dict(row)


@router.get("/feedback")
async def list_feedback(
    status_filter: Literal["new", "triaged", "resolved", "ignored"] | None = Query(default="new", alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    statement = select(RAGFeedback).where(RAGFeedback.organization_id == membership.organization_id)
    if status_filter is not None:
        statement = statement.where(RAGFeedback.status == status_filter)
    rows = await db.scalars(statement.order_by(RAGFeedback.created_at.desc(), RAGFeedback.id).offset(offset).limit(limit))
    return [_feedback_dict(row) for row in rows.all()]


@router.patch("/feedback/{feedback_id}")
async def update_feedback_status(
    feedback_id: UUID,
    payload: FeedbackStatusUpdate,
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    row = await db.scalar(select(RAGFeedback).where(
        RAGFeedback.id == feedback_id,
        RAGFeedback.organization_id == membership.organization_id,
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    row.status = payload.status
    row.triaged_by_user_id = user.id
    await record_audit(
        db, action="rag.feedback.status_updated", resource_type="rag_feedback",
        actor_user_id=user.id, organization_id=membership.organization_id,
        resource_id=str(row.id), detail={"status": payload.status},
    )
    await db.commit()
    await db.refresh(row)
    return _feedback_dict(row)


@router.post("/documents/{document_id}/reindex", status_code=status.HTTP_201_CREATED)
async def request_reindex(
    document_id: UUID,
    payload: ReindexRequestCreate,
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    document = await db.scalar(select(RAGDocument).where(
        RAGDocument.id == document_id,
        RAGDocument.organization_id == membership.organization_id,
        RAGDocument.status == "active",
    ))
    if document is None:
        raise HTTPException(status_code=404, detail="Active RAG document not found")
    row = RAGReindexRequest(
        organization_id=membership.organization_id,
        document_id=document.id,
        requested_by_user_id=user.id,
        reason=payload.reason,
        status="pending_approval",
    )
    db.add(row)
    await record_audit(
        db, action="rag.reindex.requested", resource_type="rag_document",
        actor_user_id=user.id, organization_id=membership.organization_id,
        resource_id=str(document.id), detail={"request_id": str(row.id), "status": row.status},
    )
    await db.commit()
    await db.refresh(row)
    return _reindex_dict(row)


@router.get("/reindex-requests")
async def list_reindex_requests(
    status_filter: Literal["pending_approval", "approved", "rejected"] | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    statement = select(RAGReindexRequest).where(RAGReindexRequest.organization_id == membership.organization_id)
    if status_filter is not None:
        statement = statement.where(RAGReindexRequest.status == status_filter)
    rows = await db.scalars(statement.order_by(RAGReindexRequest.created_at.desc(), RAGReindexRequest.id).offset(offset).limit(limit))
    return [_reindex_dict(row) for row in rows.all()]


@router.patch("/reindex-requests/{request_id}")
async def review_reindex_request(
    request_id: UUID,
    payload: ReindexReview,
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    row = await db.scalar(select(RAGReindexRequest).where(
        RAGReindexRequest.id == request_id,
        RAGReindexRequest.organization_id == membership.organization_id,
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Reindex request not found")
    if row.status != "pending_approval":
        raise HTTPException(status_code=409, detail="Only pending reindex requests can be reviewed")
    row.status = payload.decision
    row.reviewed_by_user_id = user.id
    await record_audit(
        db, action="rag.reindex.reviewed", resource_type="rag_document",
        actor_user_id=user.id, organization_id=membership.organization_id,
        resource_id=str(row.document_id), detail={"request_id": str(row.id), "decision": payload.decision},
    )
    await db.commit()
    await db.refresh(row)
    return _reindex_dict(row)


def _feedback_dict(row: RAGFeedback) -> dict:
    return {
        "id": str(row.id), "query_sha256": row.query_sha256, "evidence_ids": row.evidence_ids,
        "rating": row.rating, "note": row.note, "status": row.status,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _reindex_dict(row: RAGReindexRequest) -> dict:
    return {
        "id": str(row.id), "document_id": str(row.document_id), "reason": row.reason,
        "status": row.status, "requested_by_user_id": str(row.requested_by_user_id) if row.requested_by_user_id else None,
        "reviewed_by_user_id": str(row.reviewed_by_user_id) if row.reviewed_by_user_id else None,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }
