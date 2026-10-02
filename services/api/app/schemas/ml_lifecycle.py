from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrainingRunCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    algorithm: str = Field(default="baseline", min_length=1, max_length=120)
    dataset_id: UUID | None = None
    parameters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class TrainingRunUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(queued|running|succeeded|failed|cancelled)$")
    metrics: dict[str, float | int | str | None] | None = None
    error_summary: str | None = Field(default=None, max_length=12000)

    @model_validator(mode="before")
    @classmethod
    def reject_null_update_values(cls, values):
        if isinstance(values, dict) and any(value is None for value in values.values()):
            raise ValueError("Update fields cannot be null")
        return values

    @model_validator(mode="after")
    def require_an_update(self) -> "TrainingRunUpdate":
        if self.status is None and self.metrics is None and self.error_summary is None:
            raise ValueError("At least one training run field must be provided")
        return self


class TrainingRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    dataset_id: UUID | None
    name: str
    algorithm: str
    status: str
    parameters: dict
    metrics: dict
    error_summary: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class RegisteredModelCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    version: str = Field(min_length=1, max_length=80)
    framework: str = Field(default="unknown", min_length=1, max_length=80)
    artifact_uri: str | None = Field(default=None, max_length=2048)
    source_training_run_id: UUID | None = None
    source_experiment_id: UUID | None = None
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_source(self) -> "RegisteredModelCreate":
        if self.source_training_run_id is None and self.source_experiment_id is None:
            raise ValueError("A model must reference a training run or experiment")
        if self.source_training_run_id is not None and self.source_experiment_id is not None:
            raise ValueError("Choose one model source: training run or experiment")
        return self


class RegisteredModelUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(candidate|validated|approved|archived)$")
    approval_note: str | None = Field(default=None, max_length=12000)

    @model_validator(mode="before")
    @classmethod
    def reject_null_update_values(cls, values):
        if isinstance(values, dict) and any(value is None for value in values.values()):
            raise ValueError("Update fields cannot be null")
        return values

    @model_validator(mode="after")
    def require_an_update(self) -> "RegisteredModelUpdate":
        if self.status is None and self.approval_note is None:
            raise ValueError("At least one model field must be provided")
        return self


class RegisteredModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    source_training_run_id: UUID | None
    source_experiment_id: UUID | None
    name: str
    version: str
    framework: str
    artifact_uri: str | None
    status: str
    metrics: dict
    approval_note: str
    created_at: datetime
    updated_at: datetime


class ModelEvaluationCreate(BaseModel):
    evaluator: str = Field(min_length=2, max_length=120)
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
    criteria: dict[str, float | int | str | bool | None] = Field(default_factory=dict)
    summary: str = Field(default="", max_length=12000)


class ModelEvaluationUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(queued|running|passed|failed|cancelled)$")
    metrics: dict[str, float | int | str | None] | None = None
    summary: str | None = Field(default=None, max_length=12000)

    @model_validator(mode="before")
    @classmethod
    def reject_null_update_values(cls, values):
        if isinstance(values, dict) and any(value is None for value in values.values()):
            raise ValueError("Update fields cannot be null")
        return values

    @model_validator(mode="after")
    def require_an_update(self) -> "ModelEvaluationUpdate":
        if self.status is None and self.metrics is None and self.summary is None:
            raise ValueError("At least one evaluation field must be provided")
        return self


class ModelEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_id: UUID
    evaluator: str
    status: str
    metrics: dict
    criteria: dict
    summary: str
    created_at: datetime
    finished_at: datetime | None
