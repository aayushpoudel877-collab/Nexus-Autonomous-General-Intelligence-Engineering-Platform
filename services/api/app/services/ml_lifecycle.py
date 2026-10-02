"""Lifecycle policy for ML runs, evaluations and human-reviewed model records."""

from datetime import datetime, timezone

_RUN_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}

_MODEL_TRANSITIONS: dict[str, set[str]] = {
    "candidate": {"validated", "archived"},
    "validated": {"approved", "archived"},
    "approved": {"archived"},
    "archived": set(),
}

_EVALUATION_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "cancelled"},
    "running": {"passed", "failed", "cancelled"},
    "passed": set(),
    "failed": set(),
    "cancelled": set(),
}


def _ensure_transition(current: str, requested: str, transitions: dict[str, set[str]], label: str) -> None:
    if current == requested:
        return
    if requested not in transitions.get(current, set()):
        raise ValueError(f"Cannot change {label} status from '{current}' to '{requested}'")


def ensure_run_transition(current: str, requested: str) -> None:
    _ensure_transition(current, requested, _RUN_TRANSITIONS, "training run")


def ensure_model_transition(current: str, requested: str) -> None:
    _ensure_transition(current, requested, _MODEL_TRANSITIONS, "model")


def ensure_evaluation_transition(current: str, requested: str) -> None:
    _ensure_transition(current, requested, _EVALUATION_TRANSITIONS, "evaluation")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
