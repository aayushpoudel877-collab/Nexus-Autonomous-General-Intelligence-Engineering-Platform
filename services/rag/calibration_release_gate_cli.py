"""Run the approved grounding calibration release gate and emit a JSON decision."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from services.rag.calibration_release_gate import evaluate_release_gate_from_path


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read valid JSON from {path}: {exc}") from exc


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path, help="current report JSON")
    parser.add_argument("--output", required=True, type=Path, help="decision artifact JSON")
    parser.add_argument("--max-accuracy-drop", type=float, default=0.0)
    parser.add_argument("--max-macro-f1-drop", type=float, default=0.0)
    parser.add_argument("--max-class-f1-drop", type=float, default=0.0)
    parser.add_argument("--max-group-accuracy-drop", type=float, default=0.0)
    parser.add_argument("--allow-new-case-failures", action="store_true")
    args = parser.parse_args()

    try:
        current = _read_json(args.current)
        decision = evaluate_release_gate_from_path(
            str(args.baseline_manifest),
            current,
            max_accuracy_drop=args.max_accuracy_drop,
            max_macro_f1_drop=args.max_macro_f1_drop,
            max_class_f1_drop=args.max_class_f1_drop,
            max_group_accuracy_drop=args.max_group_accuracy_drop,
            fail_on_new_case_failures=not args.allow_new_case_failures,
        )
        exit_code = 0 if decision["decision"] == "pass" else 1
    except (OSError, TypeError, ValueError, KeyError) as exc:
        decision = {
            "schema_version": 1,
            "decision": "error",
            "error": str(exc),
            "interpretation": "No release approval was produced because gate inputs were invalid.",
        }
        exit_code = 2

    rendered = json.dumps(
        decision, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
    ) + "\n"
    try:
        _atomic_write(args.output, rendered)
    except OSError as exc:
        print(f"could not write release decision artifact: {exc}", file=sys.stderr)
        return 2

    print(rendered, end="")
    if exit_code == 1:
        print("calibration release gate failed:", file=sys.stderr)
        for regression in decision["regressions"]:
            print(f"- {regression}", file=sys.stderr)
    elif exit_code == 2:
        print(f"calibration release gate error: {decision['error']}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
