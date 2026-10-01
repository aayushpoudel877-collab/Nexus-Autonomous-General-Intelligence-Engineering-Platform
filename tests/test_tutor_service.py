import pytest
from pydantic import ValidationError

from services.api.app.core.config import Settings
from services.api.app.services.tutor import (
    LocalTutorProvider,
    TutorContext,
    estimate_tokens,
)


@pytest.mark.asyncio
async def test_local_tutor_uses_published_course_context():
    provider = LocalTutorProvider()
    reply = await provider.respond(
        "Explain photosynthesis",
        TutorContext(
            course_title="Biology",
            lesson_snippets=("Plants convert light energy into chemical energy.",),
        ),
    )

    assert reply.provider == "local"
    assert "Photosynthesis" in reply.content or "photosynthesis" in reply.content
    assert "Plants convert light energy" in reply.content
    assert "not a hosted language model" in reply.content


@pytest.mark.asyncio
async def test_local_tutor_discloses_missing_provider_without_context():
    reply = await LocalTutorProvider().respond("What is a variable?", TutorContext())

    assert "local fallback" in reply.content
    assert reply.model == "grounded-template"


@pytest.mark.asyncio
async def test_local_tutor_handles_blank_question():
    reply = await LocalTutorProvider().respond("   ", TutorContext())
    assert reply.content == "Please enter a question."


def test_token_estimate_is_bounded_to_at_least_one():
    assert estimate_tokens("") == 1
    assert estimate_tokens("12345678") == 2


def test_production_rejects_development_secret():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            nexus_env="production",
            nexus_secret_key="development-only-change-this-secret",
        )


def test_production_accepts_custom_secret():
    settings = Settings(
        _env_file=None,
        nexus_env="production",
        nexus_secret_key="a-unique-production-secret-value",
    )
    assert settings.is_production
