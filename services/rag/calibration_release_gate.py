"""Evaluate a current grounding report against an approved calibration baseline."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from services.rag.calibration_baseline import load_manifest, sha256_json
from services.rag.calibration_report_diff import compare_reports, find_regressions


def evaluate_release_gate(
    baseline_manifest: Mapping[str, Any],
    current_report: Any,
    *,
    max_accuracy_drop: float = 0.0,
    max_macro_f1_drop: float = 0.0,
    max_class_f1_drop: float = 0.0,
    max_group_accuracy_drop: float = 0.0,
    fail_on_new_case_failures: bool = True,
    fail_on_case_set_change: bool = True,
) -> dict[str, Any]:
    """Return a deterministic, auditable release decision from a validated manifest."""
    from services.rag.calibration_baseline import validate_manifest

    manifest = validate_manifest(dict(baseline_manifest))
    comparison = compare_reports(manifest["report"], current_report)
    policy = {
        "max_accuracy_drop": max_accuracy_drop,
        "max_macro_f1_drop": max_macro_f1_drop,
        "max_class_f1_drop": max_class_f1_drop,
        "max_group_accuracy_drop": max_group_accuracy_drop,
        "fail_on_new_case_failures": fail_on_new_case_failures,
        "fail_on_case_set_change": fail_on_case_set_change,
    }
    regressions = find_regressions(comparison, **{
        key: value for key, value in policy.items() if key != "fail_on_case_set_change"
    })
    case_changes = comparison.get("case_changes") or {}
    case_set_changes = {
        "added": case_changes.get("added", []),
        "removed": case_changes.get("removed", []),
    }
    if fail_on_case_set_change:
        for case_id in case_set_changes["added"]:
            regressions.append(f"calibration case added: {case_id}")
        for case_id in case_set_changes["removed"]:
            regressions.append(f"calibration case removed: {case_id}")
    return {
        "schema_version": 1,
        "decision": "fail" if regressions else "pass",
        "baseline": {
            "version": manifest["baseline_version"],
            "report_sha256": manifest["report_sha256"],
            "case_set_sha256": manifest["case_set_sha256"],
            "approval_reason": manifest["approval_reason"],
        },
        "current": {
            "report_sha256": sha256_json(current_report),
            "case_count": current_report["case_count"],
        },
        "policy": policy,
        "regressions": regressions,
        "case_set_changes": case_set_changes,
        "comparison": comparison,
        "interpretation": (
            "This gate checks fixture regression policy only; passing does not establish "
            "semantic entailment, factual correctness, or production safety."
        ),
    }


def evaluate_release_gate_from_path(
    baseline_path: str,
    current_report: Any,
    **policy: Any,
) -> dict[str, Any]:
    """Load and verify a reviewed manifest before evaluating a release candidate."""
    return evaluate_release_gate(load_manifest(baseline_path), current_report, **policy)
