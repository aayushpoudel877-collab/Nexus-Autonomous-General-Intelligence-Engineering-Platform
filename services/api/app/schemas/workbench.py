from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=12000)
    task_type: str = Field(default="classification", pattern="^(classification|regression|clustering|nlp|computer_vision|forecasting|other)$")


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    task_type: str
    status: str
    created_at: datetime


class DatasetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=12000)
    source_uri: str | None = Field(default=None, max_length=2048)
    row_count: int | None = Field(default=None, ge=0)
    schema_summary: dict[str, str] = Field(default_factory=dict)


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: str
    source_uri: str | None
    row_count: int | None
    schema_summary: dict
    created_at: datetime


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    algorithm: str = Field(default="baseline", min_length=1, max_length=120)
    dataset_id: UUID | None = None
    parameters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=12000)


class ExperimentUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(planned|queued|running|succeeded|failed|cancelled)$")
    metrics: dict[str, float | int | str | None] | None = None
    notes: str | None = Field(default=None, max_length=12000)

    @model_validator(mode="before")
    @classmethod
    def reject_null_update_values(cls, values):
        if isinstance(values, dict) and any(value is None for value in values.values()):
            raise ValueError("Update fields cannot be null")
        return values

    @model_validator(mode="after")
    def require_an_update(self) -> "ExperimentUpdate":
        if self.status is None and self.metrics is None and self.notes is None:
            raise ValueError("At least one experiment field must be provided")
        return self


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    dataset_id: UUID | None
    name: str
    algorithm: str
    status: str
    parameters: dict
    metrics: dict
    notes: str
    created_at: datetime
