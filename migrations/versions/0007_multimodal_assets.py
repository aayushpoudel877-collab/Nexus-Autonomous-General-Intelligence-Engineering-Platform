"""Multimodal asset manifest catalog."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_multimodal_assets"
down_revision = "0006_ml_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "multimodal_assets",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "project_id", uuid,
            sa.ForeignKey("workbench_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id", uuid,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("modality", sa.String(20), nullable=False),
        sa.Column("source_reference", sa.String(2048), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "modality IN ('text', 'image', 'audio', 'video', 'structured')",
            name="ck_multimodal_assets_modality",
        ),
        sa.CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="ck_multimodal_assets_byte_size"),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_multimodal_assets_duration"),
        sa.CheckConstraint("width IS NULL OR width > 0", name="ck_multimodal_assets_width"),
        sa.CheckConstraint("height IS NULL OR height > 0", name="ck_multimodal_assets_height"),
    )
    op.create_index("ix_multimodal_assets_project_id", "multimodal_assets", ["project_id"])
    op.create_index("ix_multimodal_assets_owner_id", "multimodal_assets", ["owner_id"])
    op.create_index("ix_multimodal_assets_modality", "multimodal_assets", ["modality"])
    op.create_index(
        "ix_multimodal_assets_project_created", "multimodal_assets", ["project_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_multimodal_assets_project_created", table_name="multimodal_assets")
    op.drop_index("ix_multimodal_assets_modality", table_name="multimodal_assets")
    op.drop_index("ix_multimodal_assets_owner_id", table_name="multimodal_assets")
    op.drop_index("ix_multimodal_assets_project_id", table_name="multimodal_assets")
    op.drop_table("multimodal_assets")
