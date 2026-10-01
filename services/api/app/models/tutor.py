from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..db.base import Base

class TutorConversation(Base):
    __tablename__ = "tutor_conversations"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[UUID | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="New tutoring session")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    messages: Mapped[list["TutorMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="TutorMessage.created_at")

class TutorMessage(Base):
    __tablename__ = "tutor_messages"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("tutor_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text())
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    provider: Mapped[str] = mapped_column(String(80), default="local")
    model: Mapped[str] = mapped_column(String(120), default="grounded-template")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    conversation: Mapped["TutorConversation"] = relationship(back_populates="messages")
