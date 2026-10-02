from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: UUID | None
    organization_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    detail: dict
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    created_at: datetime
