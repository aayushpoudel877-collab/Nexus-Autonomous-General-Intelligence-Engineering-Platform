from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class MLTrainingRun(Base):
    __tablename__ = "ml_training_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("workbench_projects.id", ondelete="CASCADE"), index=True
    )
    dataset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workbench_datasets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    algorithm: Mapped[str] = mapped_column(String(120), default="baseline")
    status: Mapped[str] = mapped_column(String(20), default="queued")
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    error_summary: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RegisteredModel(Base):
    __tablename__ = "registered_models"
    __table_args__ = (
        UniqueConstraint("project_id", "name", "version", name="uq_registered_model_project_name_version"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("workbench_projects.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_training_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ml_training_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_experiment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workbench_experiments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    version: Mapped[str] = mapped_column(String(80))
    framework: Mapped[str] = mapped_column(String(80), default="unknown")
    artifact_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="candidate")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    approval_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    evaluations: Mapped[list["ModelEvaluation"]] = relationship(
        back_populates="model", cascade="all, delete-orphan", order_by="ModelEvaluation.created_at"
    )


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("registered_models.id", ondelete="CASCADE"), index=True
    )
    evaluator: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    criteria: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model: Mapped["RegisteredModel"] = relationship(back_populates="evaluations")
