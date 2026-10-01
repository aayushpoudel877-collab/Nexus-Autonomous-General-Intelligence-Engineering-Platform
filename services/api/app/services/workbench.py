"""Domain rules for reproducible workbench experiment tracking."""

from fastapi import HTTPException, status

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"queued", "cancelled"},
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


def ensure_status_transition(current: str, requested: str) -> None:
    """Reject invalid experiment lifecycle transitions with an HTTP conflict."""
    if requested == current:
        return
    if requested not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot change experiment status from '{current}' to '{requested}'",
        )
