"""Add plugin trust roots and artifact verification state."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0015_plugin_artifact_verification"
down_revision = "0014_execution_worker_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_trust_roots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_id", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "key_id",
            name="uq_plugin_trust_root_org_key",
        ),
        sa.CheckConstraint(
            "algorithm IN ('ed25519')",
            name="ck_plugin_trust_root_algorithm",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_plugin_trust_root_status",
        ),
    )
    op.create_index(
        "ix_plugin_trust_roots_organization_id",
        "plugin_trust_roots",
        ["organization_id"],
    )
    op.create_index(
        "ix_plugin_trust_roots_created_by_user_id",
        "plugin_trust_roots",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_plugin_trust_roots_revoked_by_user_id",
        "plugin_trust_roots",
        ["revoked_by_user_id"],
    )

    op.add_column(
        "plugin_releases",
        sa.Column("artifact_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "plugin_releases",
        sa.Column(
            "artifact_verified_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "plugin_releases",
        sa.Column("verification_key_id", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "plugin_releases",
        sa.Column("verification_method", sa.String(length=32), nullable=True),
    )
    op.create_foreign_key(
        "fk_plugin_releases_artifact_verified_by_user_id",
        "plugin_releases",
        "users",
        ["artifact_verified_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_plugin_releases_artifact_verified_by_user_id",
        "plugin_releases",
        ["artifact_verified_by_user_id"],
    )
    op.create_index(
        "ix_plugin_releases_verification_key_id",
        "plugin_releases",
        ["verification_key_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_plugin_releases_verification_key_id",
        table_name="plugin_releases",
    )
    op.drop_index(
        "ix_plugin_releases_artifact_verified_by_user_id",
        table_name="plugin_releases",
    )
    op.drop_constraint(
        "fk_plugin_releases_artifact_verified_by_user_id",
        "plugin_releases",
        type_="foreignkey",
    )
    op.drop_column("plugin_releases", "verification_method")
    op.drop_column("plugin_releases", "verification_key_id")
    op.drop_column("plugin_releases", "artifact_verified_by_user_id")
    op.drop_column("plugin_releases", "artifact_verified_at")

    op.drop_index(
        "ix_plugin_trust_roots_revoked_by_user_id",
        table_name="plugin_trust_roots",
    )
    op.drop_index(
        "ix_plugin_trust_roots_created_by_user_id",
        table_name="plugin_trust_roots",
    )
    op.drop_index(
        "ix_plugin_trust_roots_organization_id",
        table_name="plugin_trust_roots",
    )
    op.drop_table("plugin_trust_roots")
