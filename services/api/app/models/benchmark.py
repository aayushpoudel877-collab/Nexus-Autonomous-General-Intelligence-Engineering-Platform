from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class BenchmarkComparison(Base):
    __tablename__ = "benchmark_comparisons"
    __table_args__ = (
        CheckConstraint("baseline_model_id <> candidate_model_id", name="ck_benchmark_distinct_models"),
        CheckConstraint("status IN ('passed', 'needs_improvement')", name="ck_benchmark_status"),
        Index("ix_benchmark_comparisons_project_created", "project_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("workbench_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_model_id: Mapped[UUID] = mapped_column(ForeignKey("registered_models.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_model_id: Mapped[UUID] = mapped_column(ForeignKey("registered_models.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    candidate_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    criteria: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    deltas: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
