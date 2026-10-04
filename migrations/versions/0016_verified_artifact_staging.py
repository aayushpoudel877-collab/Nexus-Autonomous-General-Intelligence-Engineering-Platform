"""Persist shared verified plugin artifact staging metadata."""

from alembic import op
import sqlalchemy as sa


revision = "0016_verified_artifact_staging"
down_revision = "0015_plugin_artifact_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plugin_releases",
        sa.Column("artifact_storage_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "plugin_releases",
        sa.Column("artifact_size_bytes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "plugin_releases",
        sa.Column("artifact_staged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_plugin_releases_artifact_storage_key",
        "plugin_releases",
        ["artifact_storage_key"],
    )
    op.create_check_constraint(
        "ck_plugin_releases_artifact_size_bytes",
        "plugin_releases",
        "artifact_size_bytes IS NULL OR artifact_size_bytes >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_plugin_releases_artifact_size_bytes",
        "plugin_releases",
        type_="check",
    )
    op.drop_index(
        "ix_plugin_releases_artifact_storage_key",
        table_name="plugin_releases",
    )
    op.drop_column("plugin_releases", "artifact_staged_at")
    op.drop_column("plugin_releases", "artifact_size_bytes")
    op.drop_column("plugin_releases", "artifact_storage_key")
