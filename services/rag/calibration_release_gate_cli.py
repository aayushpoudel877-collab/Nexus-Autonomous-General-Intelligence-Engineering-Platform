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
from services.rag.calibration_governance import (
    evaluate_governed_release,
    fetch_github_review_evidence,
)


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path, help="current report JSON")
    parser.add_argument("--output", required=True, type=Path, help="decision artifact JSON")
    parser.add_argument("--max-accuracy-drop", type=float, default=0.0)
    parser.add_argument("--max-macro-f1-drop", type=float, default=0.0)
    parser.add_argument("--max-class-f1-drop", type=float, default=0.0)
    parser.add_argument("--max-group-accuracy-drop", type=float, default=0.0)
    parser.add_argument("--allow-new-case-failures", action="store_true")
    parser.add_argument("--require-governance", action="store_true")
    parser.add_argument("--attestation", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--input", action="append", default=[], metavar="LABEL=PATH")
    parser.add_argument("--repository")
    parser.add_argument("--pull-request", type=int)
    parser.add_argument("--allowed-reviewer", action="append", default=[])
    parser.add_argument("--minimum-approvals", type=int, default=1)
    parser.add_argument(
        "--allow-case-set-change", action="store_true",
        help="allow added or removed calibration cases (requires explicit review)",
    )
    args = parser.parse_args(argv)

    try:
        current = _read_json(args.current)
        governance_args = [args.attestation, args.approval, args.ledger, args.repository, args.pull_request]
        if args.require_governance:
            if any(value is None for value in governance_args) or not args.allowed_reviewer or not args.input:
                raise ValueError("--require-governance needs attestation, approval, ledger, repository, pull request, allowlisted reviewer(s), and input(s)")
            if args.minimum_approvals < 1:
                raise ValueError("--minimum-approvals must be at least one")
            input_paths: dict[str, Path] = {}
            for item in args.input:
                if "=" not in item:
                    raise ValueError("each --input must use LABEL=PATH")
                label, raw_path = item.split("=", 1)
                if not label.strip() or not raw_path.strip() or label in input_paths:
                    raise ValueError("--input labels and paths must be non-empty and labels unique")
                input_paths[label] = Path(raw_path)
            manifest_data = _read_json(args.baseline_manifest)
            attestation_data = _read_json(args.attestation)
            approval_data = _read_json(args.approval)
            ledger_data = _read_json(args.ledger)
            github_evidence = fetch_github_review_evidence(
                repository=args.repository,
                pull_request_number=args.pull_request,
                expected_head_sha=attestation_data.get("source_revision"),
                approval_reviewer_id=approval_data.get("reviewer_id"),
                allowed_reviewers={name.strip() for value in args.allowed_reviewer for name in value.split(",") if name.strip()},
                token=os.environ.get("GITHUB_TOKEN", ""),
                minimum_approvals=args.minimum_approvals,
            )
            governance_decision = evaluate_governed_release(
                manifest=manifest_data,
                attestation=attestation_data,
                approval_record=approval_data,
                ledger=ledger_data,
                inputs=input_paths,
                github_evidence=github_evidence,
            )
        elif any(value is not None for value in governance_args) or args.allowed_reviewer or args.input:
            raise ValueError("governance evidence arguments require --require-governance")
        decision = evaluate_release_gate_from_path(
            str(args.baseline_manifest),
            current,
            max_accuracy_drop=args.max_accuracy_drop,
            max_macro_f1_drop=args.max_macro_f1_drop,
            max_class_f1_drop=args.max_class_f1_drop,
            max_group_accuracy_drop=args.max_group_accuracy_drop,
            fail_on_new_case_failures=not args.allow_new_case_failures,
            fail_on_case_set_change=not args.allow_case_set_change,
        )
        if args.require_governance:
            decision["governance"] = governance_decision
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
