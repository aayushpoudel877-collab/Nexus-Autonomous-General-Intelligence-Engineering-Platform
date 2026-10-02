from datetime import datetime
from math import isfinite
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BenchmarkCriterion(BaseModel):
    direction: Literal["maximize", "minimize"]
    minimum_improvement: float = Field(default=0, ge=0, le=1_000_000_000)

    @field_validator("minimum_improvement")
    @classmethod
    def finite_threshold(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("minimum_improvement must be finite")
        return value


class BenchmarkComparisonCreate(BaseModel):
    baseline_model_id: UUID
    candidate_model_id: UUID
    baseline_metrics: dict[str, int | float]
    candidate_metrics: dict[str, int | float]
    criteria: dict[str, BenchmarkCriterion] = Field(min_length=1, max_length=50)
    summary: str = Field(default="", max_length=12000)

    @field_validator("baseline_metrics", "candidate_metrics", mode="before")
    @classmethod
    def finite_metrics(cls, value):
        if not isinstance(value, dict) or not value or len(value) > 100:
            raise ValueError("Metrics must contain 1 to 100 entries")
        for name, number in value.items():
            if not isinstance(name, str) or not name.strip() or len(name) > 120:
                raise ValueError("Metric names must be 1 to 120 characters")
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not isfinite(number):
                raise ValueError("Metric values must be finite numbers")
        return value

    @model_validator(mode="after")
    def validate_comparison(self) -> "BenchmarkComparisonCreate":
        if self.baseline_model_id == self.candidate_model_id:
            raise ValueError("Baseline and candidate must be different models")
        missing = (set(self.criteria) - set(self.baseline_metrics)) | (set(self.criteria) - set(self.candidate_metrics))
        if missing:
            raise ValueError(f"Metrics required by criteria are missing: {', '.join(sorted(missing))}")
        return self


class BenchmarkComparisonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    owner_id: UUID
    baseline_model_id: UUID
    candidate_model_id: UUID
    baseline_metrics: dict
    candidate_metrics: dict
    criteria: dict
    deltas: dict
    status: Literal["passed", "needs_improvement"]
    summary: str
    created_at: datetime
