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
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "name",
            name="uq_integration_org_provider_name",
        ),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_integration_connection_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    secret_ref: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PluginRelease(Base):
    __tablename__ = "plugin_releases"
    __table_args__ = (
        UniqueConstraint(
            "plugin_id",
            "version",
            name="uq_plugin_release_version",
        ),
        CheckConstraint(
            "status IN ('pending', 'verified', 'rejected')",
            name="ck_plugin_release_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    plugin_id: Mapped[UUID] = mapped_column(
        ForeignKey("plugin_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    package_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    manifest_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signer: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    verification_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    artifact_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    artifact_verified_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    verification_key_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    verification_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    artifact_storage_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    artifact_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artifact_staged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PluginInstallation(Base):
    __tablename__ = "plugin_installations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "plugin_release_id",
            name="uq_plugin_installation_org_release",
        ),
        CheckConstraint(
            "status IN ('requested', 'approved', 'revoked')",
            name="ck_plugin_installation_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plugin_release_id: Mapped[UUID] = mapped_column(
        ForeignKey("plugin_releases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    requested_scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    approved_scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")
    approval_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
