"""Bind secret grants to the approved external reference identity."""

from alembic import op
import sqlalchemy as sa


revision = "0021_secret_reference_binding"
down_revision = "0020_secret_grant_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "secret_grants",
        sa.Column("secret_ref_sha256", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_secret_grants_secret_ref_sha256",
        "secret_grants",
        ["secret_ref_sha256"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_secret_grants_secret_ref_sha256",
        table_name="secret_grants",
    )
    op.drop_column("secret_grants", "secret_ref_sha256")
