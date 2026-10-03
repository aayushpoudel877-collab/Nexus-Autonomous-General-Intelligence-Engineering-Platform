from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class ExecutionRequest(Base):
    __tablename__ = "execution_requests"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_execution_request_org_idempotency",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_execution_request_status",
        ),
        CheckConstraint(
            "network_policy IN ('none', 'allowlist')",
            name="ck_execution_request_network_policy",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_execution_request_attempt_count",
        ),
        CheckConstraint(
            "output_bytes >= 0",
            name="ck_execution_request_output_bytes",
        ),
        Index(
            "ix_execution_requests_claimable_lease",
            "status",
            "lease_expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    installation_id: Mapped[UUID] = mapped_column(
        ForeignKey("plugin_installations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    entrypoint: Mapped[str] = mapped_column(String(240), nullable=False)
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    max_memory_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=512)
    max_output_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=1_048_576)
    network_policy: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    network_allowlist: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    worker_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
