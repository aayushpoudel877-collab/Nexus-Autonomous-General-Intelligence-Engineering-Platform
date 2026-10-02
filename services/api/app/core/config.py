from functools import lru_cache

from pydantic import Field, model_validator
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
    allowed_hosts: str = "localhost,127.0.0.1"
    max_request_bytes: int = Field(default=10_485_760, ge=1024, le=104_857_600)

    @model_validator(mode="after")
    def validate_production_security_settings(self) -> "Settings":
        if self.is_production and self.nexus_secret_key == "development-only-change-this-secret":
            raise ValueError(
                "NEXUS_SECRET_KEY must be set to a unique secret in production"
            )
        if "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS cannot contain '*' when credentials are enabled")
        if self.is_production and "*" in self.allowed_host_list:
            raise ValueError("NEXUS_ALLOWED_HOSTS cannot contain '*' in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.nexus_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
