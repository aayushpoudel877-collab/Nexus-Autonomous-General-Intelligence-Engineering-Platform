"""Create and verify explicit grounding calibration approval records."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from services.rag.calibration_provenance import verify_input_files\nfrom services.rag.calibration_approval import (
    build_approval_record,
    validate_approval_record,
)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON from {path}: {exc}") from exc


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
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
    create = commands.add_parser("create", help="record an explicit human review decision")
    create.add_argument("--manifest", required=True, type=Path)
    create.add_argument("--attestation", required=True, type=Path)
    create.add_argument("--reviewer-id", required=True)
    create.add_argument("--review-reason", required=True)
    create.add_argument("--reviewed-at", required=True, help="timezone-aware ISO-8601 timestamp")
    create.add_argument("--output", required=True, type=Path)
    verify = commands.add_parser("verify", help="verify an approval against manifest and evidence")
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--attestation", required=True, type=Path)
    verify.add_argument("--approval", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        manifest = _read_json(args.manifest)
        attestation = _read_json(args.attestation)
        if args.command == "create":
            record = build_approval_record(
                manifest,
                attestation,
                reviewer_id=args.reviewer_id,
                review_reason=args.review_reason,
                reviewed_at=args.reviewed_at,
            )
            _atomic_write(
                args.output,
                json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )
            print(json.dumps({
                "created": True,
                "approval_record_sha256": record["approval_record_sha256"],
                "baseline_version": record["baseline_version"],
            }, sort_keys=True))
            return 0

        record = validate_approval_record(_read_json(args.approval), manifest, attestation)
        print(json.dumps({
            "valid": True,
            "reviewer_id": record["reviewer_id"],
            "reviewed_at": record["reviewed_at"],
            "baseline_version": record["baseline_version"],
            "approval_record_sha256": record["approval_record_sha256"],
        }, sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print(f"calibration approval {args.command} failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
