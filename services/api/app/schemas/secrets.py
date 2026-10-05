from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SecretGrantCreate(BaseModel):
    installation_id: UUID
    integration_id: UUID


class SecretGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    installation_id: UUID
    integration_id: UUID
    created_by_user_id: UUID | None
    status: str
    approved_scopes: list[str]
    approval_note: str
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    created_at: datetime


class SecretGrantApproval(BaseModel):
    status: str = Field(pattern=r"^(approved|revoked)$")
    note: str = Field(default="", max_length=4000)

    @classmethod
    def normalize_note(cls, value: str) -> str:
        return value.strip()
