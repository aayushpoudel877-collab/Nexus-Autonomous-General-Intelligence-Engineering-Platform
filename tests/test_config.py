import pytest
from pydantic import ValidationError

from services.api.app.core.config import Settings


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            nexus_env="production",
            nexus_secret_key="a" * 32,
            cors_origins="*",
            allowed_hosts="api.example.com",
        )


def test_production_rejects_wildcard_hosts():
    with pytest.raises(ValidationError, match="NEXUS_ALLOWED_HOSTS"):
        Settings(
            nexus_env="production",
            nexus_secret_key="a" * 32,
            cors_origins="https://app.example.com",
            allowed_hosts="*",
        )


def test_production_accepts_explicit_origins_and_hosts():
    settings = Settings(
        nexus_env="production",
        nexus_secret_key="a" * 32,
        cors_origins="https://app.example.com,https://admin.example.com",
        allowed_hosts="api.example.com,admin.example.com",
    )
    assert settings.cors_origin_list == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
    assert settings.allowed_host_list == ["api.example.com", "admin.example.com"]
