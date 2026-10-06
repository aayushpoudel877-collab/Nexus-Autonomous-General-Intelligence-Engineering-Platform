from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkflowNodeCreate(BaseModel):
    node_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    title: str = Field(min_length=1, max_length=200)
    node_type: str = Field(pattern=r"^(checkpoint|research_task|execution|approval)$")
    depends_on: list[str] = Field(default_factory=list, max_length=30)
    config: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_config_size(self) -> "WorkflowNodeCreate":
        import json
        if len(json.dumps(self.config, separators=(",", ":"), sort_keys=True, default=str).encode()) > 32_768:
            raise ValueError("Node configuration is too large")
        return self


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=12_000)
    workbench_project_id: UUID | None = None
    research_plan_id: UUID | None = None
    nodes: list[WorkflowNodeCreate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_nodes(self) -> "WorkflowCreate":
        keys = [node.node_key for node in self.nodes]
        if len(keys) != len(set(keys)):
            raise ValueError("Workflow node keys must be unique")
        return self


class WorkflowNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    node_key: str
    title: str
    node_type: str
    depends_on: list[str]
    config: dict
    created_at: datetime


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str
    version: int
    status: str
    workbench_project_id: UUID | None
    research_plan_id: UUID | None
    created_at: datetime
    updated_at: datetime
    nodes: list[WorkflowNodeRead] = Field(default_factory=list)


class WorkflowRunCreate(BaseModel):
    input_json: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_input_size(self) -> "WorkflowRunCreate":
        import json
        if len(json.dumps(self.input_json, separators=(",", ":"), sort_keys=True, default=str).encode()) > 65_536:
            raise ValueError("Workflow input is too large")
        return self


class WorkflowNodeRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    node_id: UUID
    status: str
    attempt: int
    lease_expires_at: datetime | None
    input_json: dict
    output_json: dict
    error_message: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class WorkflowApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    node_run_id: UUID
    status: str
    prompt: str
    decided_by: UUID | None
    decision_note: str
    decided_at: datetime | None
    created_at: datetime


class WorkflowRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workflow_id: UUID
    status: str
    input_json: dict
    context_json: dict
    policy_snapshot: dict
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    node_runs: list[WorkflowNodeRunRead] = Field(default_factory=list)
    approvals: list[WorkflowApprovalRead] = Field(default_factory=list)


class WorkflowApprovalDecision(BaseModel):
    status: str = Field(pattern=r"^(approved|rejected)$")
    note: str = Field(default="", max_length=4_000)
