import pytest
from pydantic import ValidationError

from services.api.app.core.config import Settings

VALID_PRODUCTION_SECRET = "K9m!pQ7v#2xR8sL4wN6cT1zY5bH3dF0a"


@pytest.mark.parametrize(
    "secret",
    [
        "development-only-change-this-secret",
        "replace-with-a-development-secret",
        "replace-with-a-long-random-secret",
        "short-but-not-a-placeholder-secret",
        "a" * 32,
        "  " + VALID_PRODUCTION_SECRET + "  ",
    ],
)
def test_production_rejects_placeholder_or_padded_secrets(secret):
    with pytest.raises(ValidationError, match="NEXUS_SECRET_KEY"):
        Settings(
            nexus_env="production",
            nexus_secret_key=secret,
            cors_origins="https://app.example.com",
            allowed_hosts="api.example.com",
        )


def test_production_environment_detection_trims_whitespace():
    with pytest.raises(ValidationError, match="NEXUS_SECRET_KEY"):
        Settings(
            nexus_env=" Production ",
            nexus_secret_key="replace-with-a-development-secret",
            cors_origins="https://app.example.com",
            allowed_hosts="api.example.com",
        )


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            nexus_env="production",
            nexus_secret_key=VALID_PRODUCTION_SECRET,
            cors_origins="*",
            allowed_hosts="api.example.com",
        )


def test_production_rejects_wildcard_hosts():
    with pytest.raises(ValidationError, match="NEXUS_ALLOWED_HOSTS"):
        Settings(
            nexus_env="production",
            nexus_secret_key=VALID_PRODUCTION_SECRET,
            cors_origins="https://app.example.com",
            allowed_hosts="*",
        )


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"database_url": "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"}, "DATABASE_URL"),
        ({"cors_origins": ""}, "CORS_ORIGINS"),
        ({"allowed_hosts": ""}, "NEXUS_ALLOWED_HOSTS"),
    ],
)
def test_production_rejects_missing_deployment_settings(overrides, message):
    values = {
        "nexus_env": "production",
        "database_url": "postgresql+asyncpg://nexus:strong-db-password@db.example.com:5432/nexus",
        "nexus_secret_key": VALID_PRODUCTION_SECRET,
        "cors_origins": "https://app.example.com",
        "allowed_hosts": "api.example.com",
    }
    values.update(overrides)
    with pytest.raises(ValidationError, match=message):
        Settings(**values)


def test_nexus_prefixed_environment_aliases_are_respected():
    settings = Settings(
        NEXUS_ALLOWED_HOSTS="api.example.com,admin.example.com",
        NEXUS_ARTIFACT_ROOT="/tmp/nexus-custom-artifacts",
    )
    assert settings.allowed_host_list == ["api.example.com", "admin.example.com"]
    assert settings.artifact_root == "/tmp/nexus-custom-artifacts"


def test_production_accepts_explicit_origins_and_hosts():
    settings = Settings(
        nexus_env="production",
        database_url="postgresql+asyncpg://nexus:strong-db-password@db.example.com:5432/nexus",
        nexus_secret_key=VALID_PRODUCTION_SECRET,
        cors_origins="https://app.example.com,https://admin.example.com",
        allowed_hosts="api.example.com,admin.example.com",
    )
    assert settings.cors_origin_list == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
    assert settings.allowed_host_list == ["api.example.com", "admin.example.com"]
