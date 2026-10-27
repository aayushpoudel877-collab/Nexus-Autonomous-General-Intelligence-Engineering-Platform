"""Command-line runner for the offline grounding calibration corpus."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.rag.grounding_calibration import evaluate_cases, load_case_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=Path("tests/fixtures/rag/grounding-calibration"),
        help="directory containing one JSON grounding case per file",
    )
    parser.add_argument("--output", type=Path, help="optional path for the JSON report")
    parser.add_argument("--category", action="append", help="include category; repeatable")
    parser.add_argument("--language", action="append", help="include language; repeatable")
    parser.add_argument(
        "--status",
        action="append",
        choices=("grounded", "unsupported", "contradictory", "inconclusive"),
        help="include expected status; repeatable",
    )
    parser.add_argument("--case-prefix", help="include case IDs with this prefix")
    parser.add_argument(
        "--min-accuracy",
        type=float,
        help="exit with status 1 when accuracy is below this threshold (0 to 1)",
    )
    args = parser.parse_args()
    if args.min_accuracy is not None and not 0.0 <= args.min_accuracy <= 1.0:
        parser.error("--min-accuracy must be between 0 and 1")
    try:
        cases = load_case_files(args.fixtures)
        if args.category:
            wanted = set(args.category)
            cases = [case for case in cases if case.get("category") in wanted]
        if args.language:
            wanted = set(args.language)
            cases = [case for case in cases if case.get("language") in wanted]
        if args.status:
            wanted = set(args.status)
            cases = [case for case in cases if case["expected_status"] in wanted]
        if args.case_prefix:
            cases = [case for case in cases if case["case_id"].startswith(args.case_prefix)]
        if not cases:
            print("grounding calibration failed: filters selected zero cases", file=sys.stderr)
            return 2
        report = evaluate_cases(cases)
    except (OSError, TypeError, ValueError) as exc:
        print(f"grounding calibration failed to load: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"grounding calibration failed to write report: {exc}", file=sys.stderr)
            return 2
    print(rendered, end="")
    if report["failed"]:
        return 1
    if args.min_accuracy is not None and report["accuracy"] < args.min_accuracy:
        print(
            f"grounding calibration accuracy {report['accuracy']:.3f} is below "
            f"minimum {args.min_accuracy:.3f}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
