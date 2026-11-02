"""Independently verify a serialized GitHub review-evidence receipt."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from services.rag.calibration_governance import verify_github_review_receipt

_MAX_RECEIPT_BYTES = 1_000_000


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def read_receipt(path: Path) -> dict[str, Any]:
    """Read one bounded JSON object and reject ambiguous or malformed input."""
    try:
        with path.open("rb") as stream:
            payload = stream.read(_MAX_RECEIPT_BYTES + 1)
    except OSError as exc:
        raise ValueError(f"cannot read review receipt from {path}: {exc}") from exc
    if len(payload) > _MAX_RECEIPT_BYTES:
        raise ValueError("review receipt exceeds the 1000000-byte limit")
    try:
        value = json.loads(payload.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read valid review receipt JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TypeError("review receipt must be a JSON object")
    return value


def verify_receipt_file(path: Path) -> dict[str, Any]:
    """Verify a receipt and return a minimal, non-sensitive result summary."""
    receipt = read_receipt(path)
    verify_github_review_receipt(receipt)
    return {
        "valid": True,
        "schema_version": receipt["schema_version"],
        "repository": receipt["repository"],
        "pull_request": receipt["pull_request"],
        "head_sha": receipt["head_sha"],
        "review_count": receipt["review_count"],
        "approved_reviewer_count": len(receipt["approved_reviewers"]),
        "review_evidence_sha256": receipt["review_evidence_sha256"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path, help="serialized review receipt JSON")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify_receipt_file(args.receipt), sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print(f"GitHub review receipt verification failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
