from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.rag.grounding_calibration import evaluate_cases, load_case_files

FIXTURES = Path("tests/fixtures/rag/grounding-calibration")


def test_grounding_calibration_corpus_matches_expected_labels():
    cases = load_case_files(FIXTURES)
    report = evaluate_cases(cases)
    assert report["case_count"] >= 40
    assert report["failed"] == 0
    assert report["accuracy"] == 1.0
    assert report["confusion"]
    assert report["interpretation"].startswith("Fixture agreement")


def test_corpus_case_ids_are_unique():
    cases = load_case_files(FIXTURES)
    assert len({case["case_id"] for case in cases}) == len(cases)


def test_missing_fixture_directory_fails_clearly(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        load_case_files(tmp_path / "missing")


def test_empty_fixture_directory_fails_clearly(tmp_path):
    with pytest.raises(ValueError, match="no JSON grounding fixtures"):
        load_case_files(tmp_path)


def test_malformed_json_fixture_fails_with_filename(tmp_path):
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.json"):
        load_case_files(tmp_path)


def test_invalid_expected_label_is_rejected():
    case = {
        "case_id": "invalid-label",
        "claim": "Nexus supports encrypted storage",
        "citations": ["E1"],
        "evidence": [{"evidence_id": "E1", "text": "Nexus supports encrypted storage"}],
        "expected_status": "probably",
    }
    with pytest.raises(ValueError, match="expected_status"):
        evaluate_cases([case])


def test_report_marks_a_regression_as_failure():
    case = {
        "case_id": "known-mismatch",
        "claim": "Nexus supports encrypted storage",
        "citations": ["E1"],
        "evidence": [{"evidence_id": "E1", "text": "Penguins swim in the ocean"}],
        "expected_status": "grounded",
    }
    report = evaluate_cases([case])
    assert report["failed"] == 1
    assert report["failures"][0]["case_id"] == "known-mismatch"


def test_unicode_fixtures_round_trip_without_ascii_escaping():
    cases = load_case_files(FIXTURES)
    serialized = json.dumps(cases, ensure_ascii=False)
    assert "नेक्सस" in serialized
    assert "東京" in serialized
