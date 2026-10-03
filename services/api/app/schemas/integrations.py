import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..services.ecosystem import is_sha256


MAX_JSON_BYTES = 65_536
FORBIDDEN_SECRET_KEY_PARTS = (
    "password",
    "token",
    "secret",
    "private_key",
    "api_key",
    "client_secret",
)


def _validate_json_object(value: dict) -> dict:
    encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError("JSON configuration must be 64 KiB or smaller")
    return value


def _validate_non_secret_config(value: dict) -> dict:
    def walk(obj: object, path: str = "config") -> None:
        if isinstance(obj, dict):
            for key, child in obj.items():
                normalized = str(key).lower().replace("-", "_")
                if any(part in normalized for part in FORBIDDEN_SECRET_KEY_PARTS):
                    raise ValueError(f"Secret-like field is not allowed in {path}.{key}; use secret_ref")
                walk(child, f"{path}.{key}")
        elif isinstance(obj, list):
            for index, child in enumerate(obj):
                walk(child, f"{path}[{index}]")

    _validate_json_object(value)
    walk(value)
    return value



def _validate_secret_ref(value: str | None) -> str | None:
    if value is not None and not value.startswith("secret://"):
        raise ValueError("secret_ref must be an external secret reference beginning with secret://")
    return value


class IntegrationCreate(BaseModel):
    provider: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str = Field(min_length=2, max_length=160)
    scopes: list[str] = Field(default_factory=list, max_length=16)
    config: dict = Field(default_factory=dict)
    secret_ref: str | None = Field(default=None, max_length=2048)

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: dict) -> dict:
        return _validate_non_secret_config(value)

    @field_validator("secret_ref")
    @classmethod
    def validate_secret_ref(cls, value: str | None) -> str | None:
        return _validate_secret_ref(value)


class IntegrationUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")
    scopes: list[str] | None = Field(default=None, max_length=16)
    config: dict | None = None
    secret_ref: str | None = Field(default=None, max_length=2048)

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: dict | None) -> dict | None:
        if value is None:
            return None
        return _validate_non_secret_config(value)

    @field_validator("secret_ref")
    @classmethod
    def validate_secret_ref(cls, value: str | None) -> str | None:
        return _validate_secret_ref(value)


class IntegrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    provider: str
    name: str
    status: str
    scopes: list[str]
    config: dict
    secret_ref: str | None
    created_at: datetime
    updated_at: datetime


class PluginReleaseCreate(BaseModel):
    version: str = Field(min_length=1, max_length=40)
    artifact_uri: str = Field(min_length=1, max_length=2048)
    package_sha256: str = Field(min_length=64, max_length=64)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    signature: str = Field(min_length=16, max_length=8192)
    signer: str = Field(min_length=2, max_length=160)

    @field_validator("package_sha256", "manifest_sha256")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        normalized = value.lower()
        if not is_sha256(normalized):
            raise ValueError("Digest must be a 64-character SHA-256 hexadecimal value")
        return normalized


class PluginReleaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plugin_id: UUID
    version: str
    artifact_uri: str
    package_sha256: str
    manifest_sha256: str
    signature: str
    signer: str
    status: str
    verification_note: str
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    created_at: datetime


class PluginReleaseVerification(BaseModel):
    status: str = Field(pattern=r"^(verified|rejected)$")
    note: str = Field(default="", max_length=4000)

    @field_validator("note")
    @classmethod
    def require_review_note(cls, value: str) -> str:
        return value.strip()


class PluginInstallationCreate(BaseModel):
    plugin_release_id: UUID
    requested_scopes: list[str] = Field(default_factory=list, max_length=16)


class PluginInstallationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    plugin_release_id: UUID
    created_by_user_id: UUID | None
    requested_scopes: list[str]
    approved_scopes: list[str]
    status: str
    approval_note: str
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    created_at: datetime


class PluginInstallationApproval(BaseModel):
    status: str = Field(pattern=r"^(approved|revoked)$")
    approved_scopes: list[str] = Field(default_factory=list, max_length=16)
    note: str = Field(default="", max_length=4000)

    @field_validator("note")
    @classmethod
    def normalize_review_note(cls, value: str) -> str:
        return value.strip()
