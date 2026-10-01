"""Provider-neutral tutor boundary with a safe local fallback.

A hosted model adapter can replace LocalTutorProvider without changing API contracts.
The fallback deliberately makes no claim that an external model was called.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class TutorContext:
    course_title: str | None = None
    lesson_snippets: tuple[str, ...] = ()

@dataclass(frozen=True)
class TutorReply:
    content: str
    provider: str = "local"
    model: str = "grounded-template"

class LocalTutorProvider:
    async def respond(self, question: str, context: TutorContext) -> TutorReply:
        clean = question.strip()
        if not clean:
            return TutorReply("Please enter a question.")
        if context.lesson_snippets:
            sources = "\n".join(f"- {item[:700]}" for item in context.lesson_snippets[:4])
            return TutorReply(
                "Here is an explanation based on the available course material.\n\n"
                f"**Your question:** {clean}\n\n**Relevant course material:**\n{sources}\n\n"
                "I can explain these notes, but this local fallback is not a hosted language model. "
                "If the material does not answer your question, ask your instructor to add the relevant lesson content."
            )
        topic = f" in **{context.course_title}**" if context.course_title else ""
        return TutorReply(
            f"I've received your question{topic}: **{clean}**\n\n"
            "The AI provider is not configured yet, so this is a local fallback rather than a generated AI answer. "
            "Connect an approved provider to enable full tutoring. You can still use the course lessons and assessments while setup is pending."
        )

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
