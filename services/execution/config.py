from functools import lru_cache
import os
import socket
from uuid import uuid4


def _positive_float(name: str, default: float, minimum: float, maximum: float) -> float:
    value = float(os.getenv(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = int(os.getenv(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "true" if default else "false").strip().lower()
    if raw not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError(f"{name} must be a boolean")
    return raw in {"true", "1", "yes"}


class WorkerSettings:
    def __init__(self) -> None:
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus",
        )
        self.artifact_root = os.getenv(
            "NEXUS_ARTIFACT_ROOT",
            "/var/lib/nexus/artifacts",
        )
        self.runtime_root = os.getenv(
            "NEXUS_RUNTIME_ROOT",
            "/var/lib/nexus/runtime",
        )
        self.sandbox_image = os.getenv("NEXUS_SANDBOX_IMAGE", "").strip()
        self.docker_binary = os.getenv("NEXUS_DOCKER_BINARY", "docker").strip() or "docker"
        self.secret_provider_command = os.getenv(
            "NEXUS_SECRET_PROVIDER_COMMAND",
            "",
        ).strip()
        self.sandbox_launch_enabled = _bool_env(
            "NEXUS_SANDBOX_LAUNCH_ENABLED",
            False,
        )
        self.sandbox_stop_grace_seconds = _bounded_int(
            "NEXUS_SANDBOX_STOP_GRACE_SECONDS",
            3,
            1,
            30,
        )
        self.sandbox_cancellation_poll_seconds = _positive_float(
            "NEXUS_SANDBOX_CANCELLATION_POLL_SECONDS",
            0.5,
            0.1,
            10.0,
        )
        self.worker_id = os.getenv(
            "NEXUS_WORKER_ID", f"{socket.gethostname()}-{uuid4().hex[:12]}"
        )[:160]
        self.poll_seconds = _positive_float("NEXUS_WORKER_POLL_SECONDS", 2.0, 0.1, 30.0)
        self.lease_seconds = _bounded_int("NEXUS_WORKER_LEASE_SECONDS", 60, 5, 600)


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()


settings = get_worker_settings()
