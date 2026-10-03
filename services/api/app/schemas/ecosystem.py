from datetime import datetime
from uuid import UUID

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeveloperApiKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[str] = Field(default_factory=list, max_length=8)
    expires_at: datetime | None = None

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("expires_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        return value


class DeveloperApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class DeveloperApiKeyCreated(DeveloperApiKeyRead):
    secret: str


class PluginCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-._]*$")
    name: str = Field(min_length=2, max_length=160)
    version: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=4000)
    manifest: dict = Field(default_factory=dict)

    @field_validator("manifest")
    @classmethod
    def validate_manifest_size(cls, value: dict) -> dict:
        encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        if len(encoded) > 65_536:
            raise ValueError("Plugin manifest must be 64 KiB or smaller")
        return value


class PluginUpdate(BaseModel):
    version: str | None = Field(default=None, min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=4000)
    manifest: dict | None = None

    @field_validator("manifest")
    @classmethod
    def validate_update_manifest_size(cls, value: dict | None) -> dict | None:
        if value is not None:
            encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            if len(encoded) > 65_536:
                raise ValueError("Plugin manifest must be 64 KiB or smaller")
        return value
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class PluginRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    slug: str
    name: str
    version: str
    description: str
    manifest: dict
    status: str
    created_at: datetime
    updated_at: datetime


class DeveloperIdentity(BaseModel):
    organization_id: UUID
    key_id: UUID
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None
