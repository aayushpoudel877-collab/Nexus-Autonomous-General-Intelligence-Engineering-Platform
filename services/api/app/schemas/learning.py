from uuid import UUID
from pydantic import BaseModel, Field

class CourseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=10000)

class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: str | None = Field(default=None, pattern="^(draft|published|archived)$")

class CourseSummary(BaseModel):
    id: UUID
    title: str
    slug: str
    description: str
    status: str
    module_count: int
    enrolled_count: int

class ModuleCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = ""
    position: int = Field(default=0, ge=0)

class LessonCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    content: str = ""
    content_type: str = Field(default="article", max_length=30)
    position: int = Field(default=0, ge=0)
    estimated_minutes: int = Field(default=10, ge=1, le=600)
    is_published: bool = False

class LessonProgressUpdate(BaseModel):
    progress_percent: int = Field(ge=0, le=100)
    last_position_seconds: int = Field(default=0, ge=0)
    completed: bool = False

class CourseDetail(BaseModel):
    id: UUID
    title: str
    slug: str
    description: str
    status: str
    modules: list[dict]

class AssessmentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    instructions: str = ""
    passing_score: int = Field(default=70, ge=0, le=100)

class QuestionCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)
    question_type: str = "single_choice"
    points: int = Field(default=1, ge=1)
    position: int = Field(default=0, ge=0)

class ChoiceCreate(BaseModel):
    label: str = Field(min_length=1, max_length=2000)
    is_correct: bool = False
    position: int = Field(default=0, ge=0)

class AssessmentSubmission(BaseModel):
    answers: dict[UUID, UUID | None]

class AssessmentResult(BaseModel):
    attempt_id: UUID
    score: int
    passed: bool
