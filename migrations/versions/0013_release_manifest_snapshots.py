"""Freeze the plugin manifest used by each release."""

from alembic import op
import sqlalchemy as sa


revision = "0013_release_manifest_snapshots"
down_revision = "0012_controlled_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plugin_releases",
        sa.Column("manifest_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("plugin_releases", "manifest_snapshot")
