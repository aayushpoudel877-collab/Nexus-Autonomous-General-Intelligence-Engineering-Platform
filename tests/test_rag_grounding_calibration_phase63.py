from __future__ import annotations

from collections import Counter
from pathlib import Path

from services.rag.grounding_calibration import evaluate_cases, load_case_files

FIXTURES = Path("tests/fixtures/rag/grounding-calibration")


def test_phase63_corpus_has_fifty_cases_and_expected_labels():
    cases = load_case_files(FIXTURES)
    phase63 = [case for case in cases if case["case_id"].startswith("phase63-")]

    assert len(phase63) == 50
    report = evaluate_cases(phase63)
    assert report["failed"] == 0, report["failures"]
    assert report["case_count"] == 50
    assert report["accuracy"] == 1.0
    assert Counter(case["expected_status"] for case in phase63) == {
        "grounded": 43,
        "unsupported": 7,
    }


def test_phase63_reports_have_deterministic_group_breakdowns():
    cases = load_case_files(FIXTURES)
    phase63 = [case for case in cases if case["case_id"].startswith("phase63-")]

    first = evaluate_cases(phase63)
    second = evaluate_cases(list(reversed(phase63)))

    assert first["confusion"] == second["confusion"]
    assert first["breakdown"] == second["breakdown"]
    assert first["interpretation"].startswith("Fixture agreement")


def test_phase63_includes_unicode_and_boundary_cases():
    cases = load_case_files(FIXTURES)
    phase63 = [case for case in cases if case["case_id"].startswith("phase63-")]

    assert any(case.get("language") == "ne" for case in phase63)
    assert any(case.get("language") == "ja" for case in phase63)
    assert any(not case["citations"] for case in phase63)
    assert any(case["expected_status"] == "unsupported" for case in phase63)
