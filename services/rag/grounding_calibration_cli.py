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
    args = parser.parse_args()
    try:
        report = evaluate_cases(load_case_files(args.fixtures))
    except (OSError, ValueError) as exc:
        print(f"grounding calibration failed to load: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
