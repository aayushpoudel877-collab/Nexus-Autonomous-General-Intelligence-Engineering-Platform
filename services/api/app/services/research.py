"""Validation and lifecycle rules for dependency-aware research tasks."""

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"ready", "blocked", "cancelled"},
    "ready": {"running", "cancelled"},
    "running": {"succeeded", "failed", "blocked", "cancelled"},
    "blocked": {"ready", "cancelled"},
    "failed": {"ready", "cancelled"},
    "succeeded": set(),
    "cancelled": set(),
}


def validate_dependencies(
    dependency_ids: list[str], available_ids: set[str], task_id: str | None = None
) -> None:
    if len(dependency_ids) != len(set(dependency_ids)):
        raise ValueError("A task cannot list the same dependency more than once")
    if task_id and task_id in dependency_ids:
        raise ValueError("A task cannot depend on itself")
    missing = set(dependency_ids) - available_ids
    if missing:
        raise ValueError("Dependencies must reference tasks in the same research plan")


def ensure_task_transition(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(
            f"Cannot change research task status from '{current}' to '{requested}'"
        )


def dependencies_succeeded(dependency_statuses: list[str]) -> bool:
    return all(status == "succeeded" for status in dependency_statuses)
