from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..services.execution import (
    MAX_ALLOWLIST_ENTRIES,
    MAX_CAPABILITIES,
    MAX_INPUT_JSON_BYTES,
    MAX_MEMORY_MB,
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    validate_network_allowlist,
)
import json


class ExecutionRequestCreate(BaseModel):
    installation_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=180)
    entrypoint: str = Field(min_length=1, max_length=240)
    input_json: dict = Field(default_factory=dict)
    capabilities: list[str] = Field(min_length=1, max_length=MAX_CAPABILITIES)
    timeout_seconds: int = Field(default=300, ge=1, le=MAX_TIMEOUT_SECONDS)
    max_memory_mb: int = Field(default=512, ge=64, le=MAX_MEMORY_MB)
    max_output_bytes: int = Field(default=1_048_576, ge=4_096, le=MAX_OUTPUT_BYTES)
    network_policy: str = Field(default="none", pattern=r"^(none|allowlist)$")
    network_allowlist: list[str] = Field(default_factory=list, max_length=MAX_ALLOWLIST_ENTRIES)

    @field_validator("idempotency_key")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        return value.strip()

    @field_validator("entrypoint")
    @classmethod
    def normalize_entrypoint(cls, value: str) -> str:
        return value.strip()

    @field_validator("input_json")
    @classmethod
    def validate_input_json(cls, value: dict) -> dict:
        encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        if len(encoded) > MAX_INPUT_JSON_BYTES:
            raise ValueError("Execution input must be 64 KiB or smaller")
        return value

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if not normalized:
            raise ValueError("At least one execution capability is required")
        return list(dict.fromkeys(normalized))

    @field_validator("network_allowlist")
    @classmethod
    def normalize_allowlist(cls, value: list[str]) -> list[str]:
        return validate_network_allowlist(value)


class ExecutionRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    installation_id: UUID
    requested_by_user_id: UUID | None
    idempotency_key: str
    entrypoint: str
    input_json: dict
    capabilities: list[str]
    timeout_seconds: int
    max_memory_mb: int
    max_output_bytes: int
    network_policy: str
    network_allowlist: list[str]
    policy_snapshot: dict
    status: str
    worker_id: str | None
    failure_reason: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


class ExecutionCancel(BaseModel):
    reason: str = Field(default="Cancelled by caller", max_length=1000)
