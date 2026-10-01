from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResearchPlanCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    goal: str = Field(min_length=10, max_length=12000)
    workbench_project_id: UUID | None = None


class ResearchTaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=12000)
    task_type: str = Field(
        default="analysis",
        pattern="^(literature_review|data_collection|data_cleaning|analysis|experiment|evaluation|report|other)$",
    )
    depends_on: list[UUID] = Field(default_factory=list, max_length=30)


class ResearchTaskUpdate(BaseModel):
    status: str | None = Field(
        default=None,
        pattern="^(planned|ready|running|blocked|succeeded|failed|cancelled)$",
    )
    output_summary: str | None = Field(default=None, max_length=12000)


class ResearchTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    title: str
    description: str
    task_type: str
    status: str
    depends_on: list[str]
    output_summary: str
    created_at: datetime


class ResearchPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    goal: str
    workbench_project_id: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime
    tasks: list[ResearchTaskRead] = Field(default_factory=list)
