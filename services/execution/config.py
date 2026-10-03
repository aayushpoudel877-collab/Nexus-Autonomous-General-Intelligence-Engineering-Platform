from functools import lru_cache
import os
import socket


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


class WorkerSettings:
    def __init__(self) -> None:
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus",
        )
        self.worker_id = os.getenv("NEXUS_WORKER_ID", socket.gethostname())[:160]
        self.poll_seconds = _positive_float("NEXUS_WORKER_POLL_SECONDS", 2.0, 0.1, 30.0)
        self.lease_seconds = _bounded_int("NEXUS_WORKER_LEASE_SECONDS", 60, 5, 600)


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()


settings = get_worker_settings()
