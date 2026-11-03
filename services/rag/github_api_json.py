"""Strict JSON decoding for untrusted GitHub API response bodies."""
from __future__ import annotations

import json
from typing import Any


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key is not allowed: {key}")
        result[key] = value
    return result


def loads_github_json(payload: bytes) -> Any:
    """Decode UTF-8 JSON while rejecting duplicate keys and non-standard constants."""
    try:
        text = payload.decode("utf-8")
        return json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ValueError(f"GitHub API returned invalid JSON: {exc}") from exc
