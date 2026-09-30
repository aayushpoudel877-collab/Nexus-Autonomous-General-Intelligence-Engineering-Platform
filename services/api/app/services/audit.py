from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import AuditEvent

async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    actor_user_id: UUID | None = None,
    organization_id: UUID | None = None,
    resource_id: str | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        resource_type=resource_type,
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        resource_id=resource_id,
        detail=detail or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(event)
    return event
