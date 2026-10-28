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
    assert report["failed"] == 0, report["failures"]
    assert report["accuracy"] == 1.0
    assert report["confusion"]
    assert report["interpretation"].startswith("Fixture agreement")
    assert report["breakdown"]["category"]
    assert report["breakdown"]["language"]


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
        "category": "storage",
        "language": "en",
    }
    report = evaluate_cases([case])
    assert report["failed"] == 1
    assert report["failures"][0]["case_id"] == "known-mismatch"
    assert report["breakdown"]["category"]["storage"]["failed"] == 1
    assert report["breakdown"]["language"]["en"]["accuracy"] == 0.0


def test_unicode_fixtures_round_trip_without_ascii_escaping():
    cases = load_case_files(FIXTURES)
    serialized = json.dumps(cases, ensure_ascii=False)
    assert "नेक्सस" in serialized
    assert "東京" in serialized


def test_category_and_language_breakdowns_are_deterministic():
    cases = [
        {
            "case_id": "group-a",
            "claim": "Nexus stores encrypted records",
            "citations": ["E1"],
            "evidence": [{"evidence_id": "E1", "text": "Nexus stores encrypted records"}],
            "expected_status": "grounded",
            "category": "security",
            "language": "en",
        },
        {
            "case_id": "group-b",
            "claim": "Nexus stores encrypted records",
            "citations": ["E1"],
            "evidence": [{"evidence_id": "E1", "text": "Penguins swim in oceans"}],
            "expected_status": "unsupported",
            "category": "security",
            "language": "en",
        },
    ]
    report = evaluate_cases(cases)
    assert report["breakdown"]["category"]["security"] == {
        "case_count": 2, "passed": 2, "failed": 0, "accuracy": 1.0
    }
    assert report["breakdown"]["language"]["en"]["case_count"] == 2


def test_invalid_optional_group_metadata_is_rejected():
    case = {
        "case_id": "bad-category",
        "claim": "Nexus stores encrypted records",
        "citations": ["E1"],
        "evidence": [{"evidence_id": "E1", "text": "Nexus stores encrypted records"}],
        "expected_status": "grounded",
        "category": " ",
    }
    with pytest.raises(ValueError, match="category must be a non-empty string"):
        evaluate_cases([case])



def test_duplicate_evidence_identifiers_are_rejected():
    case = {
        "case_id": "duplicate-evidence",
        "claim": "Nexus stores encrypted records",
        "citations": ["E1"],
        "evidence": [
            {"evidence_id": "E1", "text": "Nexus stores encrypted records"},
            {"evidence_id": "E1", "text": "Nexus stores encrypted records"},
        ],
        "expected_status": "grounded",
    }
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        evaluate_cases([case])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("citations", [""], "citations must be a list of non-empty strings"),
        ("citations", ["E1", "E1"], "citations must not contain duplicate"),
        ("evidence", [{"evidence_id": "", "text": "valid text"}],
         "non-empty string evidence_id"),
        ("evidence", [{"evidence_id": "E1", "text": " "}],
         "non-empty string text"),
    ],
)
def test_invalid_evidence_and_citation_values_are_rejected(field, value, message):
    case = {
        "case_id": "invalid-schema",
        "claim": "Nexus stores encrypted records",
        "citations": ["E1"],
        "evidence": [{"evidence_id": "E1", "text": "Nexus stores encrypted records"}],
        "expected_status": "grounded",
    }
    case[field] = value
    with pytest.raises(ValueError, match=message):
        evaluate_cases([case])
