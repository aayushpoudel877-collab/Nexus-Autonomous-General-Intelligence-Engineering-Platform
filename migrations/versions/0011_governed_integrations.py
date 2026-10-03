"""Add governed integrations, plugin releases and installation approvals."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0011_governed_integrations"
down_revision = "0010_developer_ecosystem"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("secret_ref", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "provider", "name", name="uq_integration_org_provider_name"),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_integration_connection_status"),
    )
    op.create_index("ix_integration_connections_organization_id", "integration_connections", ["organization_id"])
    op.create_index("ix_integration_connections_created_by_user_id", "integration_connections", ["created_by_user_id"])
    op.create_index("ix_integration_connections_provider", "integration_connections", ["provider"])

    op.create_table(
        "plugin_releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plugin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("artifact_uri", sa.String(length=2048), nullable=False),
        sa.Column("package_sha256", sa.String(length=64), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("signer", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("verification_note", sa.Text(), nullable=False),
        sa.Column("verified_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugin_registrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "version", name="uq_plugin_release_version"),
        sa.CheckConstraint("status IN ('pending', 'verified', 'rejected')", name="ck_plugin_release_status"),
    )
    op.create_index("ix_plugin_releases_plugin_id", "plugin_releases", ["plugin_id"])
    op.create_index("ix_plugin_releases_created_by_user_id", "plugin_releases", ["created_by_user_id"])
    op.create_index("ix_plugin_releases_package_sha256", "plugin_releases", ["package_sha256"])
    op.create_index("ix_plugin_releases_manifest_sha256", "plugin_releases", ["manifest_sha256"])
    op.create_index("ix_plugin_releases_verified_by_user_id", "plugin_releases", ["verified_by_user_id"])

    op.create_table(
        "plugin_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plugin_release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_scopes", sa.JSON(), nullable=False),
        sa.Column("approved_scopes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("approval_note", sa.Text(), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plugin_release_id"], ["plugin_releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "plugin_release_id", name="uq_plugin_installation_org_release"),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'revoked')",
            name="ck_plugin_installation_status",
        ),
    )
    op.create_index("ix_plugin_installations_organization_id", "plugin_installations", ["organization_id"])
    op.create_index("ix_plugin_installations_plugin_release_id", "plugin_installations", ["plugin_release_id"])
    op.create_index("ix_plugin_installations_created_by_user_id", "plugin_installations", ["created_by_user_id"])
    op.create_index("ix_plugin_installations_approved_by_user_id", "plugin_installations", ["approved_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_plugin_installations_approved_by_user_id", table_name="plugin_installations")
    op.drop_index("ix_plugin_installations_created_by_user_id", table_name="plugin_installations")
    op.drop_index("ix_plugin_installations_plugin_release_id", table_name="plugin_installations")
    op.drop_index("ix_plugin_installations_organization_id", table_name="plugin_installations")
    op.drop_table("plugin_installations")

    op.drop_index("ix_plugin_releases_verified_by_user_id", table_name="plugin_releases")
    op.drop_index("ix_plugin_releases_manifest_sha256", table_name="plugin_releases")
    op.drop_index("ix_plugin_releases_package_sha256", table_name="plugin_releases")
    op.drop_index("ix_plugin_releases_created_by_user_id", table_name="plugin_releases")
    op.drop_index("ix_plugin_releases_plugin_id", table_name="plugin_releases")
    op.drop_table("plugin_releases")

    op.drop_index("ix_integration_connections_provider", table_name="integration_connections")
    op.drop_index("ix_integration_connections_created_by_user_id", table_name="integration_connections")
    op.drop_index("ix_integration_connections_organization_id", table_name="integration_connections")
    op.drop_table("integration_connections")
