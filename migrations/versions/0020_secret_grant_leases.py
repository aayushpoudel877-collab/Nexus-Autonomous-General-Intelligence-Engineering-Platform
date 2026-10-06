"""Add bounded expiration to secret grants.

Existing non-revoked grants are expired immediately so Phase 20 requires an
explicit re-approval with a finite lease rather than silently extending old
credentials.
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_secret_grant_leases"
down_revision = "0019_secret_grant_revocation_reuse"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "secret_grants",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_secret_grants_expires_at",
        "secret_grants",
        ["expires_at"],
    )
    op.execute(
        sa.text(
            "UPDATE secret_grants "
            "SET expires_at = created_at "
            "WHERE status <> 'revoked' AND expires_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_secret_grants_expires_at", table_name="secret_grants")
    op.drop_column("secret_grants", "expires_at")
