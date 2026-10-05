"""Persist execution secret grant IDs."""

from alembic import op
import sqlalchemy as sa


revision = "0018_execution_secret_grants"
down_revision = "0017_secret_grants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_requests",
        sa.Column(
            "secret_grant_ids",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
    )
    op.alter_column(
        "execution_requests",
        "secret_grant_ids",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("execution_requests", "secret_grant_ids")
