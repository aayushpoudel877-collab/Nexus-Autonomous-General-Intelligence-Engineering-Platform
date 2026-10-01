from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class WorkbenchProject(Base):
    __tablename__ = "workbench_projects"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    task_type: Mapped[str] = mapped_column(String(40), default="classification")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    datasets: Mapped[list["WorkbenchDataset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    experiments: Mapped[list["WorkbenchExperiment"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class WorkbenchDataset(Base):
    __tablename__ = "workbench_datasets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("workbench_projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    source_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schema_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    project: Mapped["WorkbenchProject"] = relationship(back_populates="datasets")


class WorkbenchExperiment(Base):
    __tablename__ = "workbench_experiments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("workbench_projects.id", ondelete="CASCADE"), index=True
    )
    dataset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workbench_datasets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    algorithm: Mapped[str] = mapped_column(String(120), default="baseline")
    status: Mapped[str] = mapped_column(String(20), default="planned")
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    project: Mapped["WorkbenchProject"] = relationship(back_populates="experiments")
