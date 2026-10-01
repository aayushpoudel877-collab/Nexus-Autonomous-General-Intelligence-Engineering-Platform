"""AI tutor conversations and messages."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_ai_tutor"
down_revision = "0002_lms"
branch_labels = None
depends_on = None

def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "tutor_conversations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", uuid, sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False, server_default="New tutoring session"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tutor_conversations_user_id", "tutor_conversations", ["user_id"])
    op.create_index("ix_tutor_conversations_organization_id", "tutor_conversations", ["organization_id"])
    op.create_index("ix_tutor_conversations_course_id", "tutor_conversations", ["course_id"])
    op.create_table(
        "tutor_messages",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("conversation_id", uuid, sa.ForeignKey("tutor_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider", sa.String(80), nullable=False, server_default="local"),
        sa.Column("model", sa.String(120), nullable=False, server_default="grounded-template"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tutor_messages_conversation_id", "tutor_messages", ["conversation_id"])

def downgrade() -> None:
    op.drop_index("ix_tutor_messages_conversation_id", table_name="tutor_messages")
    op.drop_table("tutor_messages")
    op.drop_index("ix_tutor_conversations_course_id", table_name="tutor_conversations")
    op.drop_index("ix_tutor_conversations_organization_id", table_name="tutor_conversations")
    op.drop_index("ix_tutor_conversations_user_id", table_name="tutor_conversations")
    op.drop_table("tutor_conversations")
