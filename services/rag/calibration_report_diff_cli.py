"""Compare two saved grounding calibration JSON reports."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from services.rag.calibration_report_diff import compare_reports, find_regressions


def _read_report(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON report {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path, help="baseline report JSON")
    parser.add_argument("--current", required=True, type=Path, help="current report JSON")
    parser.add_argument("--output", type=Path, help="optional path for the comparison JSON")
    parser.add_argument(
        "--max-accuracy-drop", type=float, default=0.0,
        help="maximum allowed accuracy drop (0 to 1; default 0)",
    )
    parser.add_argument(
        "--max-macro-f1-drop", type=float, default=0.0,
        help="maximum allowed macro-F1 drop (0 to 1; default 0)",
    )
    parser.add_argument(
        "--max-class-f1-drop", type=float, default=0.0,
        help="maximum allowed per-status F1 drop (0 to 1; default 0)",
    )
    parser.add_argument(
        "--max-group-accuracy-drop", type=float, default=0.0,
        help="maximum allowed category/language accuracy drop (0 to 1; default 0)",
    )
    parser.add_argument(
        "--allow-new-case-failures", action="store_true",
        help="do not fail only because previously passing cases now fail",
    )
    args = parser.parse_args()
    try:
        baseline = _read_report(args.baseline)
        current = _read_report(args.current)
        comparison = compare_reports(baseline, current)
        regressions = find_regressions(
            comparison,
            max_accuracy_drop=args.max_accuracy_drop,
            max_macro_f1_drop=args.max_macro_f1_drop,
            max_class_f1_drop=args.max_class_f1_drop,
            max_group_accuracy_drop=args.max_group_accuracy_drop,
            fail_on_new_case_failures=not args.allow_new_case_failures,
        )
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print(f"calibration report comparison failed: {exc}", file=sys.stderr)
        return 2
    comparison["regressions"] = regressions
    comparison["passed"] = not regressions
    rendered = json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"calibration report comparison failed to write output: {exc}", file=sys.stderr)
            return 2
    print(rendered, end="")
    if regressions:
        print("calibration report comparison detected regressions", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
