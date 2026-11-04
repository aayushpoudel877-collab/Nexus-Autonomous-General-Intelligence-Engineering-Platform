"""Tenant-scoped operator endpoints for RAG health, feedback, and reindex approval."""
from hashlib import sha256
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, get_membership, require_roles
from ..db.session import get_db
from ..models import AuditEvent, RAGChunk, RAGDocument, User
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
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 100 for value in normalized):
            raise ValueError("evidence IDs must be non-blank and at most 100 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("evidence IDs must be unique")
        return normalized


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


@router.get("/feedback/summary")
async def feedback_summary(
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    """Return privacy-conscious feedback aggregates for the active organization."""
    membership = await get_membership(user, db)
    rows = await db.execute(
        select(RAGFeedback.rating, RAGFeedback.status, func.count(RAGFeedback.id))
        .where(RAGFeedback.organization_id == membership.organization_id)
        .group_by(RAGFeedback.rating, RAGFeedback.status)
    )
    by_rating = {"helpful": 0, "unhelpful": 0}
    by_status = {"new": 0, "triaged": 0, "resolved": 0, "ignored": 0}
    for rating, feedback_status, count in rows.all():
        by_rating[rating] = int(by_rating.get(rating, 0) + count)
        by_status[feedback_status] = int(by_status.get(feedback_status, 0) + count)
    total = sum(by_rating.values())
    helpful_rate = round((by_rating["helpful"] / total) * 100, 1) if total else None
    return {
        "total": total,
        "by_rating": by_rating,
        "by_status": by_status,
        "helpful_rate_percent": helpful_rate,
        "privacy": "Aggregates only; raw queries and feedback notes are not returned.",
    }


@router.get("/feedback/trend")
async def feedback_trend(
    days: int = Query(default=30, ge=7, le=90),
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    """Return a bounded UTC daily feedback trend for the active organization."""
    from datetime import datetime, time, timedelta, timezone

    membership = await get_membership(user, db)
    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=days - 1)
    since = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
    rows = await db.execute(
        select(
            func.date_trunc("day", RAGFeedback.created_at, "UTC"),
            RAGFeedback.rating,
            func.count(RAGFeedback.id),
        )
        .where(
            RAGFeedback.organization_id == membership.organization_id,
            RAGFeedback.created_at >= since,
        )
        .group_by(func.date_trunc("day", RAGFeedback.created_at, "UTC"), RAGFeedback.rating)
        .order_by(func.date_trunc("day", RAGFeedback.created_at, "UTC"))
    )
    buckets = {
        (first_day + timedelta(days=index)).isoformat(): {"helpful": 0, "unhelpful": 0, "total": 0}
        for index in range(days)
    }
    for bucket_at, rating, count in rows.all():
        bucket_date = bucket_at.date() if hasattr(bucket_at, "date") else bucket_at
        key = bucket_date.isoformat()
        if key in buckets and rating in ("helpful", "unhelpful"):
            buckets[key][rating] += int(count)
            buckets[key]["total"] += int(count)
    return {
        "days": days,
        "timezone": "UTC",
        "total": sum(item["total"] for item in buckets.values()),
        "series": [{"date": day, **counts} for day, counts in buckets.items()],
        "privacy": "Daily aggregates only; raw queries, notes, actors, and evidence IDs are not returned.",
    }


@router.get("/feedback/compare")
async def feedback_period_comparison(
    days: int = Query(default=30, ge=7, le=90),
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    """Compare two adjacent, complete UTC feedback windows using aggregates only."""
    from datetime import datetime, time, timedelta, timezone

    membership = await get_membership(user, db)
    today = datetime.now(timezone.utc).date()
    current_start_day = today - timedelta(days=days)
    previous_start_day = current_start_day - timedelta(days=days)

    async def period_counts(start_day, end_day):
        start_at = datetime.combine(start_day, time.min, tzinfo=timezone.utc)
        end_at = datetime.combine(end_day, time.min, tzinfo=timezone.utc)
        result = await db.execute(
            select(RAGFeedback.rating, func.count(RAGFeedback.id))
            .where(
                RAGFeedback.organization_id == membership.organization_id,
                RAGFeedback.created_at >= start_at,
                RAGFeedback.created_at < end_at,
            )
            .group_by(RAGFeedback.rating)
        )
        counts = {"helpful": 0, "unhelpful": 0}
        for rating, count in result.all():
            if rating in counts:
                counts[rating] = int(count)
        total = counts["helpful"] + counts["unhelpful"]
        return {
            "start_date": start_day.isoformat(),
            "end_date_exclusive": end_day.isoformat(),
            "helpful": counts["helpful"],
            "unhelpful": counts["unhelpful"],
            "total": total,
            "helpful_rate_percent": round(counts["helpful"] / total * 100, 1) if total else None,
        }

    current = await period_counts(current_start_day, today)
    previous = await period_counts(previous_start_day, current_start_day)

    def count_change(key):
        current_value = current[key]
        previous_value = previous[key]
        return {
            "absolute": current_value - previous_value,
            "percent": (
                round((current_value - previous_value) / previous_value * 100, 1)
                if previous_value
                else None
            ),
        }

    current_rate = current["helpful_rate_percent"]
    previous_rate = previous["helpful_rate_percent"]
    return {
        "days": days,
        "timezone": "UTC",
        "current": current,
        "previous": previous,
        "change": {
            "total": count_change("total"),
            "helpful": count_change("helpful"),
            "unhelpful": count_change("unhelpful"),
            "helpful_rate_percentage_points": (
                round(current_rate - previous_rate, 1)
                if current_rate is not None and previous_rate is not None
                else None
            ),
        },
        "privacy": "Two complete-period aggregates only; raw queries, notes, actors, and evidence IDs are not returned.",
    }


@router.get("/feedback/backlog")
async def feedback_backlog_aging(
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    """Return age buckets for unresolved feedback in the active organization."""
    from datetime import datetime, timedelta, timezone

    membership = await get_membership(user, db)
    now = datetime.now(timezone.utc)
    age_bucket = case(
        (RAGFeedback.created_at >= now - timedelta(hours=24), "under_24_hours"),
        (RAGFeedback.created_at >= now - timedelta(days=7), "1_to_7_days"),
        (RAGFeedback.created_at >= now - timedelta(days=30), "7_to_30_days"),
        else_="over_30_days",
    )
    rows = await db.execute(
        select(age_bucket, RAGFeedback.status, func.count(RAGFeedback.id))
        .where(
            RAGFeedback.organization_id == membership.organization_id,
            RAGFeedback.status.in_(("new", "triaged")),
        )
        .group_by(age_bucket, RAGFeedback.status)
    )
    buckets = {
        "under_24_hours": {"label": "Under 24 hours", "new": 0, "triaged": 0, "total": 0},
        "1_to_7_days": {"label": "1–7 days", "new": 0, "triaged": 0, "total": 0},
        "7_to_30_days": {"label": "7–30 days", "new": 0, "triaged": 0, "total": 0},
        "over_30_days": {"label": "Over 30 days", "new": 0, "triaged": 0, "total": 0},
    }
    for bucket, feedback_status, count in rows.all():
        if bucket in buckets and feedback_status in ("new", "triaged"):
            buckets[bucket][feedback_status] = int(count)
            buckets[bucket]["total"] += int(count)
    series = [{"key": key, **values} for key, values in buckets.items()]
    return {
        "timezone": "UTC",
        "total_open": sum(item["total"] for item in series),
        "new_total": sum(item["new"] for item in series),
        "triaged_total": sum(item["triaged"] for item in series),
        "series": series,
        "privacy": "Age-bucket aggregates for new and triaged feedback only; no individual feedback fields are returned.",
    }


@router.get("/feedback/lifecycle-trend")
async def feedback_lifecycle_trend(
    days: int = Query(default=30, ge=7, le=90),
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    """Return daily feedback lifecycle action counts from tenant-scoped audit events."""
    from datetime import datetime, time, timedelta, timezone

    membership = await get_membership(user, db)
    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=days - 1)
    since = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
    until = datetime.combine(today + timedelta(days=1), time.min, tzinfo=timezone.utc)
    status_value = AuditEvent.detail["status"].as_string()
    activity_type = case(
        (AuditEvent.action == "rag.feedback.created", "created"),
        (status_value == "triaged", "triaged"),
        (status_value == "resolved", "resolved"),
        (status_value == "ignored", "ignored"),
        else_=None,
    )
    day_bucket = func.date_trunc("day", AuditEvent.created_at, "UTC")
    rows = await db.execute(
        select(day_bucket, activity_type, func.count(AuditEvent.id))
        .where(
            AuditEvent.organization_id == membership.organization_id,
            AuditEvent.resource_type == "rag_feedback",
            AuditEvent.action.in_(("rag.feedback.created", "rag.feedback.status_updated")),
            AuditEvent.created_at >= since,
            AuditEvent.created_at < until,
        )
        .group_by(day_bucket, activity_type)
        .order_by(day_bucket)
    )
    buckets = {
        (first_day + timedelta(days=index)).isoformat(): {
            "created": 0, "triaged": 0, "resolved": 0, "ignored": 0, "total_actions": 0
        }
        for index in range(days)
    }
    for bucket_at, activity, count in rows.all():
        bucket_date = bucket_at.date() if hasattr(bucket_at, "date") else bucket_at
        key = bucket_date.isoformat()
        if key in buckets and activity in ("created", "triaged", "resolved", "ignored"):
            buckets[key][activity] += int(count)
            buckets[key]["total_actions"] += int(count)
    series = [{"date": day, **counts} for day, counts in buckets.items()]
    totals = {
        key: sum(item[key] for item in series)
        for key in ("created", "triaged", "resolved", "ignored", "total_actions")
    }
    return {
        "days": days,
        "timezone": "UTC",
        "totals": totals,
        "series": series,
        "interpretation": "Counts are audit actions, not unique feedback records; one item may be triaged and later resolved or ignored.",
        "privacy": "Daily lifecycle aggregates only; audit actors, resource IDs, query digests, notes, and evidence IDs are not returned.",
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
    await db.flush()
    await record_audit(
        db,
        action="rag.feedback.created",
        resource_type="rag_feedback",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(row.id),
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


@router.get("/feedback/{feedback_id}/history")
async def feedback_history(
    feedback_id: UUID,
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    """Return a privacy-conscious lifecycle timeline for one tenant-owned feedback item."""
    membership = await get_membership(user, db)
    feedback = await db.scalar(
        select(RAGFeedback).where(
            RAGFeedback.id == feedback_id,
            RAGFeedback.organization_id == membership.organization_id,
        )
    )
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")

    rows = await db.execute(
        select(AuditEvent.action, AuditEvent.detail, AuditEvent.created_at)
        .where(
            AuditEvent.organization_id == membership.organization_id,
            AuditEvent.resource_type == "rag_feedback",
            AuditEvent.resource_id == str(feedback_id),
            AuditEvent.action.in_(("rag.feedback.created", "rag.feedback.status_updated")),
        )
        .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
    )
    events = []
    for action, detail, created_at in rows.all():
        if action == "rag.feedback.created":
            event_type = "submitted"
        elif action == "rag.feedback.status_updated":
            event_type = (detail or {}).get("status")
            if event_type not in ("triaged", "resolved", "ignored"):
                continue
        else:
            continue
        events.append({"event": event_type, "created_at": created_at})
    return {
        "current_status": feedback.status,
        "events": events,
        "privacy": "Lifecycle timestamps only; audit actor identifiers and raw audit details are not returned.",
    }


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
    ).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    if row.status == payload.status:
        return _feedback_dict(row)
    if payload.status not in _FEEDBACK_TRANSITIONS.get(row.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Feedback cannot transition from {row.status} to {payload.status}",
        )
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
    await db.flush()
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
    ).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail="Reindex request not found")
    if row.status != "pending_approval":
        raise HTTPException(status_code=409, detail="Only pending reindex requests can be reviewed")
    if row.requested_by_user_id == user.id:
        raise HTTPException(status_code=403, detail="The requester cannot review their own reindex request")
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


_FEEDBACK_TRANSITIONS = {
    "new": {"triaged", "resolved", "ignored"},
    "triaged": {"resolved", "ignored"},
    "resolved": set(),
    "ignored": set(),
}


def _feedback_transition_allowed(current: str, target: str) -> bool:
    """Allow idempotent updates and forward-only triage transitions."""
    return current == target or target in _FEEDBACK_TRANSITIONS.get(current, set())


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
