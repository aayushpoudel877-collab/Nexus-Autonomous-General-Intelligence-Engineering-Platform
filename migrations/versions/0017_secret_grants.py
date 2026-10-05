"""Add approved secret grants for isolated execution."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0017_secret_grants"
down_revision = "0016_verified_artifact_staging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "secret_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("approved_scopes", sa.JSON(), nullable=False),
        sa.Column("approval_note", sa.Text(), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'revoked')",
            name="ck_secret_grant_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["installation_id"], ["plugin_installations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_id"], ["integration_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "installation_id",
            "integration_id",
            name="uq_secret_grant_org_installation_integration",
        ),
    )
    op.create_index("ix_secret_grants_organization_id", "secret_grants", ["organization_id"])
    op.create_index("ix_secret_grants_installation_id", "secret_grants", ["installation_id"])
    op.create_index("ix_secret_grants_integration_id", "secret_grants", ["integration_id"])


def downgrade() -> None:
    op.drop_index("ix_secret_grants_integration_id", table_name="secret_grants")
    op.drop_index("ix_secret_grants_installation_id", table_name="secret_grants")
    op.drop_index("ix_secret_grants_organization_id", table_name="secret_grants")
    op.drop_table("secret_grants")
