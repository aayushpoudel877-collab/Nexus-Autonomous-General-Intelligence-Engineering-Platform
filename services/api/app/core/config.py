from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    nexus_env: str = "development"
    database_url: str = "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"
    redis_url: str = "redis://localhost:6379/0"
    nexus_secret_key: str = Field(min_length=16)
    jwt_access_minutes: int = 30
    jwt_refresh_days: int = 14
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.nexus_env.lower() == "production"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
