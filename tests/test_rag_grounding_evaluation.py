from __future__ import annotations

import json

import pytest

from services.rag.grounding_evaluation import (
    GroundingEvaluationCase,
    evaluate_grounding_cases,
    load_grounding_dataset,
)


def test_grounding_benchmark_reports_false_positives_negatives_and_citation_validity():
    from pathlib import Path

    fixture = Path("tests/fixtures/rag/grounding.jsonl")
    cases = load_grounding_dataset(fixture)
    report = evaluate_grounding_cases(cases)
    assert report["case_count"] == 5
    assert report["confusion_matrix"] == {
        "true_positive": 1, "false_positive": 1, "true_negative": 1, "false_negative": 2
    }
    assert report["false_positive_case_ids"] == ["claim-false-positive-3"]
    assert report["false_negative_case_ids"] == ["claim-false-negative-4", "claim-invalid-citation-5"]
    assert report["citation_validity_rate"] == pytest.approx(0.8)
    assert "language" in report["slices"]
    assert "security" in report["slices"]["risk_category"]
    assert "do not establish semantic entailment" in report["interpretation"]


def test_invalid_citation_is_counted_as_failed_support_not_crashing():
    case = GroundingEvaluationCase(
        "bad-citation", "encrypted storage", "E1", "encrypted storage",
        ("E-UNKNOWN",), True,
    )
    report = evaluate_grounding_cases([case])
    assert report["citation_validity_rate"] == 0.0
    assert report["confusion_matrix"]["false_negative"] == 1


def test_grounding_loader_rejects_duplicate_case_ids_and_bad_types(tmp_path):
    row = {
        "case_id": "c1", "claim_text": "storage encrypted", "evidence_id": "E1",
        "evidence_text": "storage encrypted", "cited_evidence_ids": ["E1"],
        "expected_supported": True,
    }
    path = tmp_path / "grounding.jsonl"
    path.write_text(
        json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate grounding case_id"):
        load_grounding_dataset(path)
    path.write_text(json.dumps({**row, "expected_supported": "yes"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected_supported must be boolean"):
        load_grounding_dataset(path)


def test_grounding_evaluation_rejects_duplicate_ids_and_empty_cases():
    with pytest.raises(ValueError, match="at least one grounding case"):
        evaluate_grounding_cases([])
    item = GroundingEvaluationCase(
        "same", "claim text", "E1", "evidence text", ("E1",), True
    )
    with pytest.raises(ValueError, match="case IDs must be unique"):
        evaluate_grounding_cases([item, item])
