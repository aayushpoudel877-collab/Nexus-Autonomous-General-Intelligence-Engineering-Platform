"""CLI for reproducible offline RAG retrieval evaluation."""
from __future__ import annotations

import argparse
import sys

from .grounding_evaluation import evaluate_grounding_cases, load_grounding_dataset
from .multilingual_evaluation import build_multilingual_ablation_report
from .multimodal_evaluation import evaluate_multimodal_slices, load_modality_map
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
    parser.add_argument("--grounding-dataset", help="Optional human-labeled claim grounding JSONL path")
    parser.add_argument("--output", required=True, help="Destination for JSON evaluation report")
    parser.add_argument("--k", type=int, default=5, help="Ranking cutoff (1..100)")
    parser.add_argument("--baseline", help="Name of the baseline run")
    parser.add_argument("--candidate", help="Name of the candidate run")
    parser.add_argument("--max-precision-drop", type=float, default=0.05)
    parser.add_argument("--max-recall-drop", type=float, default=0.05)
    parser.add_argument("--max-ndcg-drop", type=float, default=0.05)
    parser.add_argument("--bootstrap-samples", type=int, default=1000, help="Per-language paired bootstrap samples (100..5000)")
    parser.add_argument("--bootstrap-seed", type=int, default=37, help="Non-negative reproducibility seed")
    parser.add_argument("--confidence", type=float, default=0.95, help="Confidence level for percentile intervals (0.5..1)")
    parser.add_argument("--modality-map", help="Optional JSONL mapping case_id to modality for modality-sliced metrics")
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
        if args.baseline is not None and args.candidate is not None:
            report["multilingual_ablation"] = build_multilingual_ablation_report(
                cases, predictions, baseline_name=args.baseline, candidate_name=args.candidate,
                k=args.k, bootstrap_samples=args.bootstrap_samples,
                confidence=args.confidence, seed=args.bootstrap_seed,
            )
        if args.modality_map:
            report["multimodal_evaluation"] = evaluate_multimodal_slices(
                cases, predictions, load_modality_map(args.modality_map), k=args.k,
            )
        if args.grounding_dataset:
            report["grounding_evaluation"] = evaluate_grounding_cases(
                load_grounding_dataset(args.grounding_dataset)
            )
        write_report(report, args.output)
    except (OSError, TypeError, ValueError) as exc:
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
