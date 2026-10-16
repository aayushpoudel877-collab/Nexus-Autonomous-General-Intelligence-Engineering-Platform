from pathlib import Path

import pytest

from services.rag import tool_plan_evaluation
from services.rag.tool_plan_evaluation import (
    ToolPlanEvaluationCase,
    evaluate_tool_plan_cases,
)
from services.rag.tool_plan_evaluation_cli import load_tool_plan_cases


def test_tool_plan_evaluation_reports_selection_quality_and_forbidden_attempts():
    fixture = Path(__file__).parent / "fixtures" / "rag" / "tool-plan-eval.jsonl"
    cases = load_tool_plan_cases(fixture)
    report = evaluate_tool_plan_cases(cases)
    aggregate = report["aggregate"]

    assert report["case_count"] == 6
    assert aggregate["true_positive"] == 4
    assert aggregate["false_positive"] == 3
    assert aggregate["false_negative"] == 2
    assert aggregate["forbidden_tool_attempts"] == 2
    assert aggregate["forbidden_tool_case_ids"] == ["nepali-external-fetch", "shell-attempt"]
    assert report["by_language"]["ne"]["false_negative"] == 1
    assert report["by_risk_category"]["prompt_injection"]["forbidden_tool_attempts"] == 1


def test_tool_plan_contract_rejects_unknown_tools_in_expected_labels_and_duplicates():
    with pytest.raises(ValueError, match="expected tools"):
        ToolPlanEvaluationCase(
            "invalid",
            ("shell",),
            ("shell",),
            ("lexical_search",),
        )
    case = ToolPlanEvaluationCase("same", (), (), ("lexical_search",))
    with pytest.raises(ValueError, match="unique"):
        evaluate_tool_plan_cases([case, case])
    with pytest.raises(ValueError, match="at least one"):
        evaluate_tool_plan_cases([])


def test_tool_plan_jsonl_loader_rejects_unknown_fields(tmp_path):
    dataset = tmp_path / "tool-plan.jsonl"
    dataset.write_text(
        '{"case_id":"x","expected_tool_names":[],"proposed_tool_names":[],"allowed_tool_names":[],"query":"private"}' + chr(10),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown or missing fields"):
        load_tool_plan_cases(dataset)


def test_tool_plan_evaluation_case_count_is_bounded(monkeypatch):
    monkeypatch.setattr(tool_plan_evaluation, "MAX_TOOL_PLAN_CASES", 1)
    case = ToolPlanEvaluationCase("one", (), (), ("lexical_search",))
    with pytest.raises(ValueError, match="case count"):
        evaluate_tool_plan_cases([case, ToolPlanEvaluationCase("two", (), (), ())])



def test_synthetic_tool_plan_fixture_runs_through_bounded_loader():
    fixture = Path(__file__).parent / "fixtures" / "rag" / "tool-plan-eval.jsonl"
    cases = load_tool_plan_cases(fixture)
    report = evaluate_tool_plan_cases(cases)
    assert len(cases) == 6
    assert report["case_count"] == 6
    assert report["aggregate"]["forbidden_tool_attempts"] == 2
    assert report["aggregate"]["forbidden_tool_case_ids"] == [
        "nepali-external-fetch",
        "shell-attempt",
    ]
