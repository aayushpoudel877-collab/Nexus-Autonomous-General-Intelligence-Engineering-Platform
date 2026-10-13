from __future__ import annotations

import json

import pytest

from services.rag.evaluation import (
    EvaluationCase,
    EvaluationPrediction,
    EvaluationThresholds,
    build_evaluation_report,
    compare_runs,
    evaluate_golden_runs,
    load_golden_dataset,
    load_predictions,
    write_report,
)


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return path


def sample_cases():
    return [
        EvaluationCase("q1", "tenant-a", "encryption settings", ("chunk-a",), "en", "security"),
        EvaluationCase("q2", "tenant-b", "document storage", ("chunk-b",), "ne", "general"),
    ]


def test_golden_set_and_predictions_load_from_jsonl(tmp_path):
    dataset = write_jsonl(tmp_path / "golden.jsonl", [
        {"case_id": "q1", "tenant_id": "tenant-a", "query": "encryption settings",
         "relevant_chunk_ids": ["chunk-a"], "language": "en", "risk_category": "security"}
    ])
    predictions = write_jsonl(tmp_path / "runs.jsonl", [
        {"run_name": "baseline", "case_id": "q1", "ranked_chunk_ids": ["chunk-a"]}
    ])
    assert load_golden_dataset(dataset)[0].case_id == "q1"
    assert load_predictions(predictions)[0].run_name == "baseline"


def test_dataset_rejects_duplicate_case_ids_and_unknown_fields(tmp_path):
    duplicate = {
        "case_id": "q1", "tenant_id": "tenant-a", "query": "q",
        "relevant_chunk_ids": ["chunk-a"],
    }
    with pytest.raises(ValueError, match="duplicate case_id"):
        load_golden_dataset(write_jsonl(tmp_path / "dupe.jsonl", [duplicate, duplicate]))
    with pytest.raises(ValueError, match="unknown or missing"):
        load_golden_dataset(write_jsonl(tmp_path / "unknown.jsonl", [
            {**duplicate, "production_user_email": "must-not-be-in-fixtures"}
        ]))


def test_dataset_rejects_empty_labels_and_bad_json(tmp_path):
    with pytest.raises(ValueError, match="at least one relevant"):
        load_golden_dataset(write_jsonl(tmp_path / "empty.jsonl", [
            {"case_id": "q", "tenant_id": "t", "query": "query", "relevant_chunk_ids": []}
        ]))
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{broken\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_golden_dataset(bad)


def test_predictions_reject_duplicate_run_case_and_unknown_case():
    cases = sample_cases()
    repeated = [
        EvaluationPrediction("run", "q1", ("chunk-a",)),
        EvaluationPrediction("run", "q1", ("chunk-a",)),
    ]
    with pytest.raises(ValueError, match="duplicate prediction"):
        build_evaluation_report(cases, repeated)
    with pytest.raises(ValueError, match="unknown case IDs"):
        evaluate_golden_runs(cases, [EvaluationPrediction("run", "missing", ("chunk-a",))])


def test_metrics_include_missing_predictions_as_empty_and_emit_slices():
    cases = sample_cases()
    predictions = [EvaluationPrediction("baseline", "q1", ("chunk-a",))]
    report = evaluate_golden_runs(cases, predictions, k=1)
    aggregate = report["runs"]["baseline"]["aggregate"]
    assert aggregate["precision_at_k"] == 0.5
    assert aggregate["recall_at_k"] == 0.5
    assert aggregate["empty_result_rate"] == 0.5
    assert report["runs"]["baseline"]["slices"]["language"]["ne"]["empty_result_rate"] == 1.0
    assert report["runs"]["baseline"]["slices"]["tenant_id"]["tenant-b"]["case_count"] == 1


def test_release_gate_passes_improvement_and_fails_large_regression():
    cases = sample_cases()
    predictions = [
        EvaluationPrediction("baseline", "q1", ("wrong",)),
        EvaluationPrediction("baseline", "q2", ("chunk-b",)),
        EvaluationPrediction("candidate", "q1", ("chunk-a",)),
        EvaluationPrediction("candidate", "q2", ("chunk-b",)),
    ]
    report = evaluate_golden_runs(cases, predictions, k=1)
    passing = compare_runs(report, baseline_name="baseline", candidate_name="candidate")
    assert passing["passed"] is True
    failing_predictions = [
        EvaluationPrediction("baseline", "q1", ("chunk-a",)),
        EvaluationPrediction("baseline", "q2", ("chunk-b",)),
        EvaluationPrediction("candidate", "q1", ()),
        EvaluationPrediction("candidate", "q2", ()),
    ]
    failing_report = evaluate_golden_runs(cases, failing_predictions, k=1)
    failed = compare_runs(
        failing_report, baseline_name="baseline", candidate_name="candidate",
        thresholds=EvaluationThresholds(0.0, 0.0, 0.0),
    )
    assert failed["passed"] is False
    assert all(not check["passed"] for check in failed["checks"].values())


def test_report_requires_baseline_and_candidate_together():
    with pytest.raises(ValueError, match="provided together"):
        build_evaluation_report(
            sample_cases(),
            [EvaluationPrediction("run", "q1", ("chunk-a",))],
            baseline_name="run",
        )


def test_thresholds_and_cutoff_are_bounded():
    with pytest.raises(ValueError, match="max_recall_drop"):
        EvaluationThresholds(max_recall_drop=float("nan"))
    with pytest.raises(ValueError, match="k must be"):
        evaluate_golden_runs(
            sample_cases(), [EvaluationPrediction("run", "q1", ("chunk-a",))], k=0
        )


def test_report_json_is_stable(tmp_path):
    report = build_evaluation_report(
        sample_cases(),
        [
            EvaluationPrediction("baseline", "q1", ("chunk-a",)),
            EvaluationPrediction("baseline", "q2", ("chunk-b",)),
        ],
        k=1,
    )
    output = tmp_path / "report.json"
    write_report(report, output)
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == 1
