"""Create and verify grounding calibration provenance sidecars."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import os
from pathlib import Path
from typing import Any

from services.rag.calibration_provenance import (
    build_attestation,
    validate_attestation,
    verify_input_files,
)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON from {path}: {exc}") from exc


def _write_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _input_args(values: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("each --input must use LABEL=PATH")
        label, path = value.split("=", 1)
        if not label.strip() or not path.strip() or label in parsed:
            raise ValueError("input labels and paths must be non-empty and labels unique")
        parsed[label] = Path(path)
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create a report provenance sidecar")
    create.add_argument("--report", required=True, type=Path)
    create.add_argument("--input", action="append", required=True, metavar="LABEL=PATH")
    create.add_argument("--source-revision", required=True)
    create.add_argument("--evaluator", required=True)
    create.add_argument("--output", required=True, type=Path)
    verify = commands.add_parser("verify", help="verify a report and its input evidence")
    verify.add_argument("--report", required=True, type=Path)
    verify.add_argument("--attestation", required=True, type=Path)
    verify.add_argument("--input", action="append", required=True, metavar="LABEL=PATH")
    args = parser.parse_args(argv)

    try:
        report = _read_json(args.report)
        inputs = _input_args(args.input)
        if args.command == "create":
            attestation = build_attestation(
                report,
                inputs=inputs,
                source_revision=args.source_revision,
                evaluator=args.evaluator,
            )
            _write_atomic(
                args.output,
                json.dumps(attestation, ensure_ascii=False, indent=2, sort_keys=True) + "\\n",
            )
            print(json.dumps({"created": True, "report_sha256": attestation["report_sha256"]}))
            return 0

        attestation = validate_attestation(_read_json(args.attestation), report)
        verify_input_files(attestation, inputs)
        print(json.dumps({
            "valid": True,
            "report_sha256": attestation["report_sha256"],
            "source_revision": attestation["source_revision"],
            "input_count": len(attestation["inputs"]),
        }, sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print(f"calibration provenance {args.command} failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
