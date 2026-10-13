"""CLI for reproducible offline RAG retrieval evaluation."""
from __future__ import annotations

import argparse
import sys

from .evaluation import (
    EvaluationThresholds,
    build_evaluation_report,
    load_golden_dataset,
    load_predictions,
    write_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="Reviewed golden-set JSONL path")
    parser.add_argument("--predictions", required=True, help="Ranked predictions JSONL path")
    parser.add_argument("--output", required=True, help="Destination for JSON evaluation report")
    parser.add_argument("--k", type=int, default=5, help="Ranking cutoff (1..100)")
    parser.add_argument("--baseline", help="Name of the baseline run")
    parser.add_argument("--candidate", help="Name of the candidate run")
    parser.add_argument("--max-precision-drop", type=float, default=0.05)
    parser.add_argument("--max-recall-drop", type=float, default=0.05)
    parser.add_argument("--max-ndcg-drop", type=float, default=0.05)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        cases = load_golden_dataset(args.dataset)
        predictions = load_predictions(args.predictions)
        thresholds = EvaluationThresholds(
            max_precision_drop=args.max_precision_drop,
            max_recall_drop=args.max_recall_drop,
            max_ndcg_drop=args.max_ndcg_drop,
        )
        report = build_evaluation_report(
            cases,
            predictions,
            k=args.k,
            baseline_name=args.baseline,
            candidate_name=args.candidate,
            thresholds=thresholds,
        )
        write_report(report, args.output)
    except (OSError, ValueError) as exc:
        print(f"evaluation failed: {exc}", file=sys.stderr)
        return 2
    gate = report.get("release_gate")
    if gate is not None and not gate["passed"]:
        print(f"release gate failed; report written to {args.output}", file=sys.stderr)
        return 1
    print(f"evaluation report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
