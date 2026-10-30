"""Append-only lifecycle ledger for calibration approval records.

The ledger provides tamper-evident ordering, not authenticated identity or immutable storage.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from services.rag.calibration_baseline import sha256_json

LEDGER_SCHEMA_VERSION = 1
_ACTIONS = {"approved", "revoked", "superseded"}


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("occurred_at must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("occurred_at must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("occurred_at must include a timezone offset")
    return value


def _event_payload(
    *,
    sequence: int,
    action: str,
    approval_record_sha256: str,
    actor_id: str,
    reason: str,
    occurred_at: str,
    previous_event_sha256: str | None,
    replacement_approval_sha256: str | None,
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "action": action,
        "approval_record_sha256": approval_record_sha256,
        "actor_id": actor_id.strip(),
        "reason": reason.strip(),
        "occurred_at": _timestamp(occurred_at),
        "previous_event_sha256": previous_event_sha256,
        "replacement_approval_sha256": replacement_approval_sha256,
    }


def _validate_digest(value: Any, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def new_ledger() -> dict[str, Any]:
    """Return an empty versioned lifecycle ledger."""
    return {"schema_version": LEDGER_SCHEMA_VERSION, "events": []}


def append_lifecycle_event(
    ledger: Any,
    *,
    action: str,
    approval_record_sha256: str,
    actor_id: str,
    reason: str,
    occurred_at: str,
    replacement_approval_sha256: str | None = None,
) -> dict[str, Any]:
    """Append an approval, revocation, or supersession event to a validated ledger."""
    checked = validate_ledger(ledger)
    return _append_validated(
        checked, action=action, approval_record_sha256=approval_record_sha256,
        actor_id=actor_id, reason=reason, occurred_at=occurred_at,
        replacement_approval_sha256=replacement_approval_sha256,
    )


def _append_validated(
    checked: dict[str, Any], *, action: str, approval_record_sha256: str,
    actor_id: str, reason: str, occurred_at: str,
    replacement_approval_sha256: str | None,
) -> dict[str, Any]:
    if action not in _ACTIONS:
        raise ValueError("action must be approved, revoked, or superseded")
    _validate_digest(approval_record_sha256, "approval_record_sha256")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError("actor_id must be a non-empty identifier")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a non-empty explanation")
    active = active_approvals(checked)
    if action == "approved":
        historical = {
            digest
            for event in checked["events"]
            for digest in (
                event["approval_record_sha256"], event["replacement_approval_sha256"]
            )
            if digest is not None
        }
        if approval_record_sha256 in historical:
            raise ValueError("approval record already appears in lifecycle history")
        if replacement_approval_sha256 is not None:
            raise ValueError("approved events cannot name a replacement approval")
    else:
        if approval_record_sha256 not in active:
            raise ValueError("only an active approval can be revoked or superseded")
        if action == "revoked" and replacement_approval_sha256 is not None:
            raise ValueError("revoked events cannot name a replacement approval")
        if action == "superseded":
            _validate_digest(replacement_approval_sha256, "replacement_approval_sha256")
            if replacement_approval_sha256 == approval_record_sha256:
                raise ValueError("replacement approval must differ from superseded approval")
            if replacement_approval_sha256 in active:
                raise ValueError("replacement approval is already active")
            historical = {
                digest
                for event in checked["events"]
                for digest in (
                    event["approval_record_sha256"], event["replacement_approval_sha256"]
                )
                if digest is not None
            }
            if replacement_approval_sha256 in historical:
                raise ValueError("replacement approval already appears in lifecycle history")

    events = list(checked["events"])
    previous = events[-1]["event_sha256"] if events else None
    payload = _event_payload(
        sequence=len(events) + 1,
        action=action,
        approval_record_sha256=approval_record_sha256,
        actor_id=actor_id,
        reason=reason,
        occurred_at=occurred_at,
        previous_event_sha256=previous,
        replacement_approval_sha256=replacement_approval_sha256,
    )
    events.append({**payload, "event_sha256": sha256_json(payload)})
    return {"schema_version": LEDGER_SCHEMA_VERSION, "events": events}


def validate_ledger(ledger: Any) -> dict[str, Any]:
    """Verify ledger schema, event hashes, ordering, and legal lifecycle transitions."""
    if not isinstance(ledger, dict) or set(ledger) != {"schema_version", "events"}:
        raise TypeError("ledger must contain only schema_version and events")
    version = ledger.get("schema_version")
    if isinstance(version, bool) or version != LEDGER_SCHEMA_VERSION:
        raise ValueError("unsupported approval ledger schema_version")
    events = ledger.get("events")
    if not isinstance(events, list):
        raise TypeError("ledger events must be a list")
    rebuilt = new_ledger()
    for event in events:
        if not isinstance(event, dict):
            raise TypeError("ledger event must be an object")
        expected_keys = {
            "sequence", "action", "approval_record_sha256", "actor_id", "reason",
            "occurred_at", "previous_event_sha256", "replacement_approval_sha256",
            "event_sha256",
        }
        if set(event) != expected_keys:
            raise ValueError("ledger event has missing or unexpected fields")
        sequence = event.get("sequence")
        if isinstance(sequence, bool) or sequence != len(rebuilt["events"]) + 1:
            raise ValueError("ledger event sequence is not contiguous")
        previous = rebuilt["events"][-1]["event_sha256"] if rebuilt["events"] else None
        if event.get("previous_event_sha256") != previous:
            raise ValueError("ledger event chain is broken")
        action = event.get("action")
        if not isinstance(event.get("actor_id"), str) or not isinstance(event.get("reason"), str):
            raise TypeError("ledger actor_id and reason must be strings")
        if action not in _ACTIONS:
            raise ValueError("ledger event has unsupported action")
        payload = _event_payload(
            sequence=sequence,
            action=action,
            approval_record_sha256=event.get("approval_record_sha256"),
            actor_id=event.get("actor_id"),
            reason=event.get("reason"),
            occurred_at=event.get("occurred_at"),
            previous_event_sha256=previous,
            replacement_approval_sha256=event.get("replacement_approval_sha256"),
        )
        _validate_digest(payload["approval_record_sha256"], "approval_record_sha256")
        if not payload["actor_id"] or not payload["reason"]:
            raise ValueError("ledger actor_id and reason must be non-empty")
        expected = {**payload, "event_sha256": sha256_json(payload)}
        if event != expected:
            raise ValueError("ledger event SHA-256 or canonical content does not match")
        rebuilt = _append_validated(
            rebuilt,
            action=action,
            approval_record_sha256=payload["approval_record_sha256"],
            actor_id=payload["actor_id"],
            reason=payload["reason"],
            occurred_at=payload["occurred_at"],
            replacement_approval_sha256=payload["replacement_approval_sha256"],
        )
    return ledger


def active_approvals(ledger: Any) -> set[str]:
    """Return approval digests whose latest lifecycle state is approved."""
    events = ledger.get("events") if isinstance(ledger, dict) else None
    if not isinstance(events, list):
        raise TypeError("ledger events must be a list")
    states: dict[str, str] = {}
    for event in events:
        action = event["action"]
        digest = event["approval_record_sha256"]
        states[digest] = action
        if action == "superseded":
            states[event["replacement_approval_sha256"]] = "approved"
    return {digest for digest, state in states.items() if state == "approved"}
