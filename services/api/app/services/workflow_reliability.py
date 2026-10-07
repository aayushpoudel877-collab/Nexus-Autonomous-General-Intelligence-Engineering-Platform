"""Bounded retry and deterministic replay helpers for durable workflow nodes."""

import hashlib
import json
from datetime import datetime, timedelta, timezone


DEFAULT_MAX_ATTEMPTS = 1
MAX_RETRY_ATTEMPTS = 5
DEFAULT_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 300


def validate_retry_policy(policy: dict | None) -> dict:
    policy = dict(policy or {})
    allowed = {"max_attempts", "backoff_seconds", "retryable_errors"}
    unexpected = set(policy) - allowed
    if unexpected:
        raise ValueError("Retry policy contains unsupported fields")
    max_attempts = int(policy.get("max_attempts", DEFAULT_MAX_ATTEMPTS))
    backoff = int(policy.get("backoff_seconds", DEFAULT_BACKOFF_SECONDS))
    retryable = policy.get("retryable_errors", [])
    if not 1 <= max_attempts <= MAX_RETRY_ATTEMPTS:
        raise ValueError(f"max_attempts must be between 1 and {MAX_RETRY_ATTEMPTS}")
    if not 0 <= backoff <= MAX_BACKOFF_SECONDS:
        raise ValueError(f"backoff_seconds must be between 0 and {MAX_BACKOFF_SECONDS}")
    if not isinstance(retryable, list) or len(retryable) > 16 or any(not isinstance(item, str) or not item.strip() for item in retryable):
        raise ValueError("retryable_errors must contain at most 16 non-empty strings")
    return {
        "max_attempts": max_attempts,
        "backoff_seconds": backoff,
        "retryable_errors": sorted(set(item.strip() for item in retryable)),
    }


def retry_delay_seconds(policy: dict, attempt: int) -> int:
    normalized = validate_retry_policy(policy)
    exponent = max(0, attempt - 1)
    return min(MAX_BACKOFF_SECONDS, normalized["backoff_seconds"] * (2 ** exponent))


def retry_allowed(policy: dict, attempt: int, error_message: str) -> bool:
    normalized = validate_retry_policy(policy)
    if attempt >= normalized["max_attempts"]:
        return False
    retryable = normalized["retryable_errors"]
    return bool(retryable) and any(marker in error_message for marker in retryable)


def next_retry_at(now: datetime | None, policy: dict, attempt: int) -> datetime:
    base = now or datetime.now(timezone.utc)
    return base + timedelta(seconds=retry_delay_seconds(policy, attempt))


def replay_fingerprint(workflow_id: str, node_key: str, attempt: int, input_json: dict) -> str:
    payload = json.dumps(
        {"workflow_id": workflow_id, "node_key": node_key, "attempt": attempt, "input": input_json},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(payload).hexdigest()
