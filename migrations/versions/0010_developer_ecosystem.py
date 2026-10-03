"""Add developer API keys and tenant-scoped plugin registrations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_developer_ecosystem"
down_revision = "0009_audit_request_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "developer_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_developer_api_keys_organization_id", "developer_api_keys", ["organization_id"])
    op.create_index("ix_developer_api_keys_created_by_user_id", "developer_api_keys", ["created_by_user_id"])
    op.create_index("ix_developer_api_keys_key_prefix", "developer_api_keys", ["key_prefix"])
    op.create_index("ix_developer_api_keys_key_hash", "developer_api_keys", ["key_hash"])

    op.create_table(
        "plugin_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_plugin_org_slug"),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_plugin_registration_status"),
    )
    op.create_index("ix_plugin_registrations_organization_id", "plugin_registrations", ["organization_id"])
    op.create_index("ix_plugin_registrations_created_by_user_id", "plugin_registrations", ["created_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_plugin_registrations_created_by_user_id", table_name="plugin_registrations")
    op.drop_index("ix_plugin_registrations_organization_id", table_name="plugin_registrations")
    op.drop_table("plugin_registrations")
    op.drop_index("ix_developer_api_keys_key_hash", table_name="developer_api_keys")
    op.drop_index("ix_developer_api_keys_key_prefix", table_name="developer_api_keys")
    op.drop_index("ix_developer_api_keys_created_by_user_id", table_name="developer_api_keys")
    op.drop_index("ix_developer_api_keys_organization_id", table_name="developer_api_keys")
    op.drop_table("developer_api_keys")
