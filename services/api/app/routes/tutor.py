from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.dependencies import get_current_user, get_membership
from ..db.session import get_db
from ..models import Course, Enrollment, Lesson, TutorConversation, TutorMessage, User
from ..schemas.tutor import TutorConversationCreate, TutorConversationRead, TutorMessageCreate, TutorMessageRead
from ..services.tutor import LocalTutorProvider, TutorContext, estimate_tokens

router = APIRouter(prefix="/tutor", tags=["ai-tutor"])
provider = LocalTutorProvider()

async def _owned_conversation(db: AsyncSession, conversation_id: UUID, user: User, org_id: UUID) -> TutorConversation:
    conversation = await db.scalar(select(TutorConversation).where(
        TutorConversation.id == conversation_id,
        TutorConversation.user_id == user.id,
        TutorConversation.organization_id == org_id,
    ))
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@router.get("/conversations", response_model=list[TutorConversationRead])
async def list_conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db)
    rows = await db.scalars(select(TutorConversation).where(
        TutorConversation.user_id == user.id,
        TutorConversation.organization_id == membership.organization_id,
    ).order_by(TutorConversation.updated_at.desc()).limit(50))
    return list(rows.all())

@router.post("/conversations", response_model=TutorConversationRead, status_code=201)
async def create_conversation(payload: TutorConversationCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db)
    if payload.course_id:
        course = await db.scalar(select(Course).where(
            Course.id == payload.course_id,
            Course.organization_id == membership.organization_id,
        ))
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        enrolled = await db.scalar(select(Enrollment.id).where(
            Enrollment.course_id == course.id, Enrollment.user_id == user.id, Enrollment.status == "active"
        ))
        if course.status != "published" and course.author_id != user.id:
            raise HTTPException(status_code=403, detail="Course is not available")
        if course.status == "published" and not enrolled and course.author_id != user.id:
            raise HTTPException(status_code=403, detail="Enroll in this course before using course-aware tutoring")
    conversation = TutorConversation(
        user_id=user.id, organization_id=membership.organization_id,
        course_id=payload.course_id, title=payload.title,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation

@router.get("/conversations/{conversation_id}", response_model=TutorConversationRead)
async def get_conversation(conversation_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db)
    return await _owned_conversation(db, conversation_id, user, membership.organization_id)

@router.post("/conversations/{conversation_id}/messages", response_model=TutorMessageRead, status_code=201)
async def send_message(
    conversation_id: UUID,
    payload: TutorMessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    conversation = await _owned_conversation(db, conversation_id, user, membership.organization_id)
    question = payload.content.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Message cannot be blank")
    # Bound persisted conversation history to avoid unbounded prompt/context growth.
    recent = await db.scalars(select(TutorMessage).where(
        TutorMessage.conversation_id == conversation.id
    ).order_by(TutorMessage.created_at.desc()).limit(20))
    prior = list(reversed(recent.all()))
    context = TutorContext()
    if conversation.course_id:
        course = await db.scalar(select(Course).where(Course.id == conversation.course_id))
        if course:
            snippets = await db.scalars(select(Lesson.content).join(
                __import__("services.api.app.models.learning", fromlist=["CourseModule"]).CourseModule,
                Lesson.module_id == __import__("services.api.app.models.learning", fromlist=["CourseModule"]).CourseModule.id,
            ).where(
                __import__("services.api.app.models.learning", fromlist=["CourseModule"]).CourseModule.course_id == course.id,
                Lesson.is_published.is_(True),
            ).limit(4))
            context = TutorContext(course_title=course.title, lesson_snippets=tuple(s for s in snippets.all() if s))
    user_message = TutorMessage(
        conversation_id=conversation.id, role="user", content=question,
        token_estimate=estimate_tokens(question), provider="local", model="input",
    )
    db.add(user_message)
    reply = await provider.respond(question, context)
    assistant_message = TutorMessage(
        conversation_id=conversation.id, role="assistant", content=reply.content,
        token_estimate=estimate_tokens(reply.content), provider=reply.provider, model=reply.model,
    )
    db.add(assistant_message)
    if conversation.title == "New tutoring session":
        conversation.title = question[:190]
    await db.commit()
    await db.refresh(assistant_message)
    return assistant_message
