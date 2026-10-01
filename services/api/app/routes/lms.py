import re
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.dependencies import get_current_user, get_membership, require_roles
from ..db.session import get_db
from ..models import Assessment, AssessmentAnswer, AssessmentAttempt, Course, CourseModule, Enrollment, Lesson, LessonProgress, Question, QuestionChoice, User
from ..schemas.learning import AssessmentCreate, AssessmentResult, AssessmentSubmission, ChoiceCreate, CourseCreate, CourseDetail, CourseSummary, CourseUpdate, LessonCreate, LessonProgressUpdate, ModuleCreate, QuestionCreate

router = APIRouter(prefix="/lms", tags=["lms"])

def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:180] or "course"

async def _course_for_org(db: AsyncSession, course_id: UUID, org_id: UUID) -> Course:
    course = await db.scalar(select(Course).where(Course.id == course_id, Course.organization_id == org_id))
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course

@router.get("/courses", response_model=list[CourseSummary])
async def list_courses(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db)
    rows = await db.execute(select(Course).where(Course.organization_id == membership.organization_id).order_by(Course.created_at.desc()))
    courses = rows.scalars().all()
    result = []
    for course in courses:
        module_count = await db.scalar(select(func.count(CourseModule.id)).where(CourseModule.course_id == course.id)) or 0
        enrolled_count = await db.scalar(select(func.count(Enrollment.id)).where(Enrollment.course_id == course.id, Enrollment.status == "active")) or 0
        result.append(CourseSummary(id=course.id,title=course.title,slug=course.slug,description=course.description,status=course.status,module_count=module_count,enrolled_count=enrolled_count))
    return result

@router.post("/courses", response_model=CourseSummary, status_code=201)
async def create_course(payload: CourseCreate, user: User = Depends(require_roles("owner","admin","instructor")), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db)
    base = slugify(payload.title)
    slug = base
    suffix = 2
    while await db.scalar(select(Course.id).where(Course.organization_id == membership.organization_id, Course.slug == slug)):
        slug = f"{base}-{suffix}"; suffix += 1
    course = Course(organization_id=membership.organization_id, author_id=user.id, title=payload.title, slug=slug, description=payload.description)
    db.add(course); await db.commit(); await db.refresh(course)
    return CourseSummary(id=course.id,title=course.title,slug=course.slug,description=course.description,status=course.status,module_count=0,enrolled_count=0)

@router.patch("/courses/{course_id}", response_model=CourseSummary)
async def update_course(course_id: UUID, payload: CourseUpdate, user: User = Depends(require_roles("owner","admin","instructor")), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db); course = await _course_for_org(db, course_id, membership.organization_id)
    if payload.title is not None: course.title = payload.title
    if payload.description is not None: course.description = payload.description
    if payload.status is not None:
        course.status = payload.status
        course.published_at = datetime.now(timezone.utc) if payload.status == "published" else course.published_at
    await db.commit()
    modules = await db.scalar(select(func.count(CourseModule.id)).where(CourseModule.course_id == course.id)) or 0
    enrolled = await db.scalar(select(func.count(Enrollment.id)).where(Enrollment.course_id == course.id, Enrollment.status == "active")) or 0
    return CourseSummary(id=course.id,title=course.title,slug=course.slug,description=course.description,status=course.status,module_count=modules,enrolled_count=enrolled)

@router.post("/courses/{course_id}/modules", status_code=201)
async def create_module(course_id: UUID, payload: ModuleCreate, user: User = Depends(require_roles("owner","admin","instructor")), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db); await _course_for_org(db, course_id, membership.organization_id)
    module = CourseModule(course_id=course_id, title=payload.title, description=payload.description, position=payload.position)
    db.add(module); await db.commit(); await db.refresh(module)
    return {"id": module.id, "title": module.title, "position": module.position}

@router.post("/modules/{module_id}/lessons", status_code=201)
async def create_lesson(module_id: UUID, payload: LessonCreate, user: User = Depends(require_roles("owner","admin","instructor")), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db)
    module = await db.scalar(select(CourseModule).join(Course).where(CourseModule.id == module_id, Course.organization_id == membership.organization_id))
    if not module: raise HTTPException(status_code=404, detail="Module not found")
    lesson = Lesson(module_id=module_id, title=payload.title, content=payload.content, content_type=payload.content_type, position=payload.position, estimated_minutes=payload.estimated_minutes, is_published=payload.is_published)
    db.add(lesson); await db.commit(); await db.refresh(lesson)
    return {"id": lesson.id, "title": lesson.title, "published": lesson.is_published}

@router.get("/courses/{course_id}", response_model=CourseDetail)
async def get_course(course_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db); course = await _course_for_org(db, course_id, membership.organization_id)
    modules = (await db.execute(select(CourseModule).where(CourseModule.course_id == course.id).order_by(CourseModule.position))).scalars().all()
    data=[]
    for module in modules:
        lessons=(await db.execute(select(Lesson).where(Lesson.module_id==module.id).order_by(Lesson.position))).scalars().all()
        data.append({"id":str(module.id),"title":module.title,"description":module.description,"position":module.position,"lessons":[{"id":str(x.id),"title":x.title,"content_type":x.content_type,"position":x.position,"estimated_minutes":x.estimated_minutes,"is_published":x.is_published} for x in lessons]})
    return CourseDetail(id=course.id,title=course.title,slug=course.slug,description=course.description,status=course.status,modules=data)

@router.post("/courses/{course_id}/enroll", status_code=201)
async def enroll(course_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db); course = await _course_for_org(db, course_id, membership.organization_id)
    if course.status != "published": raise HTTPException(status_code=400, detail="Course is not published")
    existing = await db.scalar(select(Enrollment).where(Enrollment.course_id==course.id, Enrollment.user_id==user.id))
    if existing: return {"id":existing.id,"status":existing.status}
    enrollment=Enrollment(course_id=course.id,user_id=user.id); db.add(enrollment); await db.commit(); await db.refresh(enrollment)
    return {"id":enrollment.id,"status":enrollment.status}

@router.put("/lessons/{lesson_id}/progress")
async def update_progress(lesson_id: UUID, payload: LessonProgressUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db)
    lesson = await db.scalar(select(Lesson).join(CourseModule).join(Course).join(Enrollment, Enrollment.course_id==Course.id).where(Lesson.id==lesson_id, Course.organization_id==membership.organization_id, Enrollment.user_id==user.id, Enrollment.status=="active"))
    if not lesson: raise HTTPException(status_code=404, detail="Enrolled lesson not found")
    progress=await db.scalar(select(LessonProgress).where(LessonProgress.lesson_id==lesson_id,LessonProgress.user_id==user.id))
    if not progress: progress=LessonProgress(lesson_id=lesson_id,user_id=user.id); db.add(progress)
    progress.progress_percent=payload.progress_percent; progress.last_position_seconds=payload.last_position_seconds; progress.completed=payload.completed or payload.progress_percent==100
    await db.commit()
    return {"lesson_id":lesson_id,"progress_percent":progress.progress_percent,"completed":progress.completed}

@router.post("/lessons/{lesson_id}/assessments", status_code=201)
async def create_assessment(lesson_id: UUID, payload: AssessmentCreate, user: User = Depends(require_roles("owner","admin","instructor")), db: AsyncSession = Depends(get_db)):
    membership=await get_membership(user,db)
    lesson=await db.scalar(select(Lesson).join(CourseModule).join(Course).where(Lesson.id==lesson_id,Course.organization_id==membership.organization_id))
    if not lesson: raise HTTPException(status_code=404,detail="Lesson not found")
    assessment=Assessment(lesson_id=lesson_id,title=payload.title,instructions=payload.instructions,passing_score=payload.passing_score); db.add(assessment); await db.commit(); await db.refresh(assessment)
    return {"id":assessment.id,"title":assessment.title}

@router.post("/assessments/{assessment_id}/questions", status_code=201)
async def create_question(assessment_id: UUID, payload: QuestionCreate, user: User = Depends(require_roles("owner","admin","instructor")), db: AsyncSession = Depends(get_db)):
    membership=await get_membership(user,db)
    assessment=await db.scalar(select(Assessment).join(Lesson).join(CourseModule).join(Course).where(Assessment.id==assessment_id,Course.organization_id==membership.organization_id))
    if not assessment: raise HTTPException(status_code=404,detail="Assessment not found")
    q=Question(assessment_id=assessment_id,prompt=payload.prompt,question_type=payload.question_type,points=payload.points,position=payload.position); db.add(q); await db.commit(); await db.refresh(q)
    return {"id":q.id,"prompt":q.prompt}

@router.post("/questions/{question_id}/choices", status_code=201)
async def create_choice(question_id: UUID, payload: ChoiceCreate, user: User = Depends(require_roles("owner","admin","instructor")), db: AsyncSession = Depends(get_db)):
    membership=await get_membership(user,db)
    q=await db.scalar(select(Question).join(Assessment).join(Lesson).join(CourseModule).join(Course).where(Question.id==question_id,Course.organization_id==membership.organization_id))
    if not q: raise HTTPException(status_code=404,detail="Question not found")
    choice=QuestionChoice(question_id=question_id,label=payload.label,is_correct=payload.is_correct,position=payload.position); db.add(choice); await db.commit(); await db.refresh(choice)
    return {"id":choice.id,"label":choice.label}

@router.post("/assessments/{assessment_id}/submit", response_model=AssessmentResult)
async def submit_assessment(assessment_id: UUID, payload: AssessmentSubmission, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db)
    assessment = await db.scalar(select(Assessment).join(Lesson).join(CourseModule).join(Course).where(Assessment.id==assessment_id, Course.organization_id==membership.organization_id))
    if not assessment: raise HTTPException(status_code=404,detail="Assessment not found")
    enrolled=await db.scalar(select(Enrollment).join(Course).join(CourseModule, CourseModule.course_id==Course.id).join(Lesson, Lesson.module_id==CourseModule.id).where(Lesson.id==assessment.lesson_id,Enrollment.user_id==user.id,Enrollment.status=="active"))
    if not enrolled: raise HTTPException(status_code=403,detail="Enrollment required")
    questions=(await db.execute(select(Question).where(Question.assessment_id==assessment.id))).scalars().all()
    total=sum(q.points for q in questions) or 1; earned=0
    attempt=AssessmentAttempt(assessment_id=assessment.id,user_id=user.id); db.add(attempt); await db.flush()
    for q in questions:
        choice_id=payload.answers.get(q.id)
        choice=await db.scalar(select(QuestionChoice).where(QuestionChoice.id==choice_id,QuestionChoice.question_id==q.id)) if choice_id else None
        if choice and choice.is_correct: earned += q.points
        db.add(AssessmentAnswer(attempt_id=attempt.id,question_id=q.id,choice_id=choice.id if choice else None))
    score=round((earned/total)*100); attempt.score=score; attempt.passed=score>=assessment.passing_score; attempt.submitted_at=datetime.now(timezone.utc)
    await db.commit()
    return AssessmentResult(attempt_id=attempt.id,score=score,passed=attempt.passed)
