"""Allow a new secret grant after a previous grant is revoked.

A revoked grant ID remains immutable so historical execution policy snapshots
cannot regain access if a later approval is created for the same integration.
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_secret_grant_revocation_reuse"
down_revision = "0018_execution_secret_grants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_secret_grant_org_installation_integration",
        "secret_grants",
        type_="unique",
    )
    op.create_index(
        "uq_secret_grant_org_installation_integration_live",
        "secret_grants",
        ["organization_id", "installation_id", "integration_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'revoked'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_secret_grant_org_installation_integration_live",
        table_name="secret_grants",
    )
    op.create_unique_constraint(
        "uq_secret_grant_org_installation_integration",
        "secret_grants",
        ["organization_id", "installation_id", "integration_id"],
    )
