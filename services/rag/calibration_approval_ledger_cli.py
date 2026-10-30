"""Append and inspect calibration approval lifecycle events."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from services.rag.calibration_approval_ledger import (
    active_approvals,
    append_lifecycle_event,
    new_ledger,
    validate_ledger,
)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read valid ledger JSON from {path}: {exc}") from exc


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    append = commands.add_parser("append", help="append a lifecycle event")
    append.add_argument("--ledger", required=True, type=Path)
    append.add_argument("--output", required=True, type=Path)
    append.add_argument("--action", required=True, choices=("approved", "revoked", "superseded"))
    append.add_argument("--approval-sha256", required=True)
    append.add_argument("--actor-id", required=True)
    append.add_argument("--reason", required=True)
    append.add_argument("--occurred-at", required=True, help="timezone-aware ISO-8601 timestamp")
    append.add_argument("--replacement-approval-sha256")
    verify = commands.add_parser("verify", help="verify the complete event chain")
    verify.add_argument("--ledger", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify" and not args.ledger.is_file():
            raise ValueError(f"ledger file does not exist: {args.ledger}")
        ledger = _read(args.ledger) if args.ledger.exists() else new_ledger()
        validate_ledger(ledger)
        if args.command == "append":
            updated = append_lifecycle_event(
                ledger,
                action=args.action,
                approval_record_sha256=args.approval_sha256,
                actor_id=args.actor_id,
                reason=args.reason,
                occurred_at=args.occurred_at,
                replacement_approval_sha256=args.replacement_approval_sha256,
            )
            _write(args.output, updated)
            ledger = updated
        else:
            validate_ledger(ledger)
        print(json.dumps({
            "valid": True,
            "event_count": len(ledger["events"]),
            "active_approval_sha256": sorted(active_approvals(ledger)),
            "head_event_sha256": (
                ledger["events"][-1]["event_sha256"] if ledger["events"] else None
            ),
        }, sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print(f"calibration approval ledger {args.command} failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
