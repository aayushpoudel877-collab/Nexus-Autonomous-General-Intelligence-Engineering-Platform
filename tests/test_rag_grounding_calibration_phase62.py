from __future__ import annotations

from collections import Counter
from pathlib import Path

from services.rag.grounding_calibration import evaluate_cases, load_case_files

FIXTURES = Path("tests/fixtures/rag/grounding-calibration")


def test_phase62_boundary_corpus_has_expected_outcome_distribution():
    cases = load_case_files(FIXTURES)
    phase62 = [case for case in cases if case["case_id"].startswith("phase62-")]

    assert len(phase62) == 50
    report = evaluate_cases(phase62)

    assert report["failed"] == 0, report["failures"]
    assert report["case_count"] == 50
    assert report["accuracy"] == 1.0
    assert Counter(case["expected_status"] for case in phase62) == {
        "inconclusive": 10,
        "unsupported": 25,
        "grounded": 15,
    }


def test_phase62_unicode_fixtures_preserve_non_ascii_text():
    cases = load_case_files(FIXTURES)
    unicode_cases = [
        case for case in cases
        if case["case_id"].startswith("phase62-unicode-grounded-")
    ]

    assert len(unicode_cases) == 15
    assert any("नेक्सस" in case["claim"] for case in unicode_cases)
    assert any("東京" in case["claim"] for case in unicode_cases)
    assert all(case["claim"] == case["evidence"][0]["text"] for case in unicode_cases)
