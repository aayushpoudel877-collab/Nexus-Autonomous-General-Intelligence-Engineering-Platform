"""Approve and verify content-addressed grounding calibration baseline manifests."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from services.rag.calibration_baseline import (
    build_manifest,
    load_manifest,
)


def _read_report(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read calibration report {path}: {exc}") from exc


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    approve = subparsers.add_parser("approve", help="create or explicitly update an approved baseline")
    approve.add_argument("--report", required=True, type=Path, help="calibration report JSON")
    approve.add_argument("--output", required=True, type=Path, help="manifest output path")
    approve.add_argument("--version", required=True, type=int, help="positive baseline version")
    approve.add_argument("--reason", required=True, help="reviewed reason for approving this baseline")
    approve.add_argument(
        "--expected-current-report-sha",
        help="required when replacing an existing manifest; guards against stale updates",
    )
    verify = subparsers.add_parser("verify", help="validate a manifest and its embedded report")
    verify.add_argument("--manifest", required=True, type=Path, help="baseline manifest JSON")
    args = parser.parse_args()

    try:
        if args.command == "verify":
            manifest = load_manifest(args.manifest)
            print(json.dumps({
                "valid": True,
                "baseline_version": manifest["baseline_version"],
                "report_sha256": manifest["report_sha256"],
                "case_set_sha256": manifest["case_set_sha256"],
                "approval_reason": manifest["approval_reason"],
            }, ensure_ascii=False, indent=2, sort_keys=True))
            return 0

        if args.output.exists():
            current = load_manifest(args.output)
            expected = args.expected_current_report_sha
            if not expected:
                raise ValueError(
                    "baseline already exists; supply --expected-current-report-sha "
                    "to explicitly approve a replacement"
                )
            if expected != current["report_sha256"]:
                raise ValueError("existing baseline changed; expected report SHA-256 does not match")
            if args.version <= current["baseline_version"]:
                raise ValueError("replacement baseline version must be greater than current version")
        elif args.expected_current_report_sha:
            raise ValueError("expected-current-report-sha was supplied but no baseline exists")

        report = _read_report(args.report)
        manifest = build_manifest(report, version=args.version, reason=args.reason)
        rendered = json.dumps(
            manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
        ) + "\n"
        _atomic_write(args.output, rendered)
        print(json.dumps({
            "approved": True,
            "baseline_version": manifest["baseline_version"],
            "report_sha256": manifest["report_sha256"],
            "case_set_sha256": manifest["case_set_sha256"],
            "output": str(args.output),
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print(f"calibration baseline {args.command} failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
