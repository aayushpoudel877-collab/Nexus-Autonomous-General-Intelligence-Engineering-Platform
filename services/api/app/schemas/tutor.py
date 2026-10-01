from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TutorConversationCreate(BaseModel):
    title: str = Field(default="New tutoring session", min_length=1, max_length=200)
    course_id: UUID | None = None


class TutorMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class TutorMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    created_at: datetime


class TutorConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    course_id: UUID | None
    created_at: datetime
    messages: list[TutorMessageRead] = Field(default_factory=list)
