from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_membership, require_roles
from ..db.session import get_db
from ..models import AuditEvent, User
from ..schemas.audit import AuditEventRead

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditEventRead])
async def list_audit_events(
    action: str | None = Query(default=None, min_length=1, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10000),
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    statement = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == membership.organization_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if action:
        statement = statement.where(AuditEvent.action == action)
    rows = await db.scalars(statement)
    return list(rows.all())
