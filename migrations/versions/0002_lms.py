"""phase 2 LMS schema"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_lms"
down_revision = "0001_identity"
branch_labels = None
depends_on = None

def upgrade() -> None:
    u=postgresql.UUID(as_uuid=True)
    op.create_table("courses",
        sa.Column("id",u,primary_key=True),sa.Column("organization_id",u,sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("author_id",u,sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),sa.Column("title",sa.String(200),nullable=False),
        sa.Column("slug",sa.String(220),nullable=False),sa.Column("description",sa.Text(),nullable=False,server_default=""),
        sa.Column("status",sa.String(20),nullable=False,server_default="draft"),sa.Column("published_at",sa.DateTime(timezone=True)),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_courses_organization_id","courses",["organization_id"])
    op.create_index("ix_courses_slug","courses",["slug"])
    op.create_table("course_modules",
        sa.Column("id",u,primary_key=True),sa.Column("course_id",u,sa.ForeignKey("courses.id",ondelete="CASCADE"),nullable=False),
        sa.Column("title",sa.String(200),nullable=False),sa.Column("description",sa.Text(),nullable=False,server_default=""),
        sa.Column("position",sa.Integer(),nullable=False,server_default="0"))
    op.create_index("ix_course_modules_course_id","course_modules",["course_id"])
    op.create_table("lessons",
        sa.Column("id",u,primary_key=True),sa.Column("module_id",u,sa.ForeignKey("course_modules.id",ondelete="CASCADE"),nullable=False),
        sa.Column("title",sa.String(200),nullable=False),sa.Column("content",sa.Text(),nullable=False,server_default=""),
        sa.Column("content_type",sa.String(30),nullable=False,server_default="article"),sa.Column("position",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("estimated_minutes",sa.Integer(),nullable=False,server_default="10"),sa.Column("is_published",sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_index("ix_lessons_module_id","lessons",["module_id"])
    op.create_table("enrollments",
        sa.Column("id",u,primary_key=True),sa.Column("course_id",u,sa.ForeignKey("courses.id",ondelete="CASCADE"),nullable=False),
        sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("status",sa.String(20),nullable=False,server_default="active"),
        sa.Column("enrolled_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("completed_at",sa.DateTime(timezone=True)))
    op.create_index("ix_enrollments_course_id","enrollments",["course_id"]); op.create_index("ix_enrollments_user_id","enrollments",["user_id"])
    op.create_unique_constraint("uq_enrollment_course_user","enrollments",["course_id","user_id"])
    op.create_table("lesson_progress",
        sa.Column("id",u,primary_key=True),sa.Column("lesson_id",u,sa.ForeignKey("lessons.id",ondelete="CASCADE"),nullable=False),
        sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("completed",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("progress_percent",sa.Integer(),nullable=False,server_default="0"),sa.Column("last_position_seconds",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_lesson_progress_lesson_id","lesson_progress",["lesson_id"]); op.create_index("ix_lesson_progress_user_id","lesson_progress",["user_id"])
    op.create_unique_constraint("uq_lesson_progress_lesson_user","lesson_progress",["lesson_id","user_id"])
    op.create_table("assessments",
        sa.Column("id",u,primary_key=True),sa.Column("lesson_id",u,sa.ForeignKey("lessons.id",ondelete="CASCADE"),nullable=False),
        sa.Column("title",sa.String(200),nullable=False),sa.Column("instructions",sa.Text(),nullable=False,server_default=""),
        sa.Column("passing_score",sa.Integer(),nullable=False,server_default="70"))
    op.create_index("ix_assessments_lesson_id","assessments",["lesson_id"])
    op.create_table("questions",
        sa.Column("id",u,primary_key=True),sa.Column("assessment_id",u,sa.ForeignKey("assessments.id",ondelete="CASCADE"),nullable=False),
        sa.Column("prompt",sa.Text(),nullable=False),sa.Column("question_type",sa.String(30),nullable=False,server_default="single_choice"),
        sa.Column("points",sa.Integer(),nullable=False,server_default="1"),sa.Column("position",sa.Integer(),nullable=False,server_default="0"))
    op.create_index("ix_questions_assessment_id","questions",["assessment_id"])
    op.create_table("question_choices",
        sa.Column("id",u,primary_key=True),sa.Column("question_id",u,sa.ForeignKey("questions.id",ondelete="CASCADE"),nullable=False),
        sa.Column("label",sa.Text(),nullable=False),sa.Column("is_correct",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("position",sa.Integer(),nullable=False,server_default="0"))
    op.create_index("ix_question_choices_question_id","question_choices",["question_id"])
    op.create_table("assessment_attempts",
        sa.Column("id",u,primary_key=True),sa.Column("assessment_id",u,sa.ForeignKey("assessments.id",ondelete="CASCADE"),nullable=False),
        sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("score",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("passed",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("submitted_at",sa.DateTime(timezone=True)))
    op.create_index("ix_assessment_attempts_assessment_id","assessment_attempts",["assessment_id"]); op.create_index("ix_assessment_attempts_user_id","assessment_attempts",["user_id"])
    op.create_table("assessment_answers",
        sa.Column("id",u,primary_key=True),sa.Column("attempt_id",u,sa.ForeignKey("assessment_attempts.id",ondelete="CASCADE"),nullable=False),
        sa.Column("question_id",u,sa.ForeignKey("questions.id",ondelete="CASCADE"),nullable=False),
        sa.Column("choice_id",u,sa.ForeignKey("question_choices.id",ondelete="SET NULL")))
    op.create_index("ix_assessment_answers_attempt_id","assessment_answers",["attempt_id"])

def downgrade() -> None:
    for name in ["assessment_answers","assessment_attempts","question_choices","questions","assessments","lesson_progress","enrollments","lessons","course_modules","courses"]:
        op.drop_table(name)
