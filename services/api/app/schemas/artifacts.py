from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..services.artifact_verification import MAX_BASE64_BYTES


class PluginTrustRootCreate(BaseModel):
    key_id: str = Field(min_length=2, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")
    name: str = Field(min_length=2, max_length=160)
    algorithm: str = Field(default="ed25519", pattern=r"^ed25519$")
    public_key: str = Field(min_length=40, max_length=128)


class PluginTrustRootRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    key_id: str
    name: str
    algorithm: str
    public_key: str
    status: str
    created_by_user_id: UUID | None
    revoked_by_user_id: UUID | None
    created_at: datetime
    revoked_at: datetime | None


class PluginArtifactVerification(BaseModel):
    trust_root_id: UUID
    artifact_base64: str = Field(min_length=4, max_length=MAX_BASE64_BYTES)

    @field_validator("artifact_base64")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("artifact_base64 cannot be blank")
        return value.strip()
