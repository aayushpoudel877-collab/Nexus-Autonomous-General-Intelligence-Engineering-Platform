from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    nexus_env: str = "development"
    database_url: str = "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"
    redis_url: str = "redis://localhost:6379/0"
    nexus_secret_key: str = Field(
        default="development-only-change-this-secret", min_length=16
    )
    jwt_access_minutes: int = Field(default=30, ge=1, le=1440)
    jwt_refresh_days: int = Field(default=14, ge=1, le=365)
    cors_origins: str = "http://localhost:3000"
    allowed_hosts: str = Field(
        default="localhost,127.0.0.1",
        validation_alias=AliasChoices("NEXUS_ALLOWED_HOSTS", "allowed_hosts"),
    )
    max_request_bytes: int = Field(default=10_485_760, ge=1024, le=104_857_600)
    artifact_root: str = Field(
        default="/var/lib/nexus/artifacts",
        validation_alias=AliasChoices("NEXUS_ARTIFACT_ROOT", "artifact_root"),
    )

    @model_validator(mode="after")
    def validate_production_security_settings(self) -> "Settings":
        normalized_secret = self.nexus_secret_key.strip().lower()
        placeholder_markers = (
            "development-only",
            "replace-with",
            "change-this",
            "your-secret",
            "example-secret",
            "placeholder",
        )
        if self.is_production and (
            self.nexus_secret_key.strip() != self.nexus_secret_key
            or len(normalized_secret) < 32
            or len(set(normalized_secret)) < 8
            or any(marker in normalized_secret for marker in placeholder_markers)
        ):
            raise ValueError(
                "NEXUS_SECRET_KEY must be a real, non-placeholder secret in production"
            )
        if "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS cannot contain '*' when credentials are enabled")
        if self.is_production and "*" in self.allowed_host_list:
            raise ValueError("NEXUS_ALLOWED_HOSTS cannot contain '*' in production")
        if self.is_production and not self.cors_origin_list:
            raise ValueError("CORS_ORIGINS must contain at least one origin in production")
        if self.is_production and not self.allowed_host_list:
            raise ValueError("NEXUS_ALLOWED_HOSTS must contain at least one host in production")
        if self.is_production and (
            not self.database_url.strip()
            or self.database_url == "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"
        ):
            raise ValueError("DATABASE_URL must be explicitly configured in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.nexus_env.strip().lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
