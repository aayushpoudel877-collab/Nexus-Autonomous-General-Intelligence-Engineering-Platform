from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class MultimodalAsset(Base):
    __tablename__ = "multimodal_assets"
    __table_args__ = (
        CheckConstraint(
            "modality IN ('text', 'image', 'audio', 'video', 'structured')",
            name="ck_multimodal_assets_modality",
        ),
        CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="ck_multimodal_assets_byte_size"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_multimodal_assets_duration"),
        CheckConstraint("width IS NULL OR width > 0", name="ck_multimodal_assets_width"),
        CheckConstraint("height IS NULL OR height > 0", name="ck_multimodal_assets_height"),
        Index("ix_multimodal_assets_project_created", "project_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("workbench_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    modality: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_reference: Mapped[str] = mapped_column(String(2048), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    width: Mapped[int | None] = mapped_column(nullable=True)
    height: Mapped[int | None] = mapped_column(nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
