from __future__ import annotations

import json

import pytest

from services.rag.calibration_approval import build_approval_record
from services.rag.calibration_approval_ledger import append_lifecycle_event, new_ledger
from services.rag.calibration_baseline import build_manifest
from services.rag.calibration_governance import evaluate_governed_release
from services.rag.calibration_provenance import build_attestation


def _report():
    return {
        "schema_version": 1,
        "case_count": 1,
        "passed": 1,
        "failed": 0,
        "accuracy": 1.0,
        "macro_f1": 1.0,
        "confusion": {"grounded->grounded": 1},
        "status_metrics": {
            "grounded": {"support": 1, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            "unsupported": {"support": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0},
            "contradictory": {"support": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0},
            "inconclusive": {"support": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0},
        },
        "breakdown": {"category": {"security": {"case_count": 1, "accuracy": 1.0}}},
        "case_results": [
            {"case_id": "case-1", "expected": "grounded", "actual": "grounded", "passed": True}
        ],
    }


def _bundle(tmp_path):
    source = tmp_path / "dataset.jsonl"
    source.write_text('{"case_id":"case-1"}\n', encoding="utf-8")
    report = _report()
    manifest = build_manifest(report, version=1, reason="reviewed baseline")
    attestation = build_attestation(
        report, inputs={"dataset": source}, source_revision="a" * 40,
        evaluator="offline-calibration",
    )
    approval = build_approval_record(
        manifest, attestation, reviewer_id="reviewer-17",
        review_reason="reviewed the calibration evidence",
        reviewed_at="2026-10-31T09:00:00Z",
    )
    ledger = append_lifecycle_event(
        new_ledger(), action="approved",
        approval_record_sha256=approval["approval_record_sha256"],
        actor_id="reviewer-17", reason="reviewed evidence",
        occurred_at="2026-10-31T09:01:00Z",
    )
    evidence = {
        "provider": "github",
        "repository": "owner/repo",
        "pull_request": 74,
        "head_sha": "a" * 40,
        "approved_reviewers": ["reviewer-17"],
        "minimum_approvals": 1,
        "approval_reviewer_id": "reviewer-17",
    }
    return manifest, attestation, approval, ledger, {"dataset": source}, evidence


def test_governed_release_requires_active_approval_and_exact_github_reviewer(tmp_path):
    manifest, attestation, approval, ledger, inputs, evidence = _bundle(tmp_path)
    result = evaluate_governed_release(
        manifest=manifest, attestation=attestation, approval_record=approval,
        ledger=ledger, inputs=inputs, github_evidence=evidence,
    )
    assert result["verified"] is True
    assert result["approval_record_sha256"] == approval["approval_record_sha256"]


def test_governed_release_rejects_revoked_approval(tmp_path):
    manifest, attestation, approval, ledger, inputs, evidence = _bundle(tmp_path)
    ledger = append_lifecycle_event(
        ledger, action="revoked",
        approval_record_sha256=approval["approval_record_sha256"],
        actor_id="reviewer-17", reason="approval withdrawn",
        occurred_at="2026-10-31T10:00:00Z",
    )
    with pytest.raises(ValueError, match="not active"):
        evaluate_governed_release(
            manifest=manifest, attestation=attestation, approval_record=approval,
            ledger=ledger, inputs=inputs, github_evidence=evidence,
        )


def test_governed_release_rejects_github_head_mismatch(tmp_path):
    manifest, attestation, approval, ledger, inputs, evidence = _bundle(tmp_path)
    evidence["head_sha"] = "b" * 40
    with pytest.raises(ValueError, match="source revision"):
        evaluate_governed_release(
            manifest=manifest, attestation=attestation, approval_record=approval,
            ledger=ledger, inputs=inputs, github_evidence=evidence,
        )


def test_governed_release_rejects_reviewer_identity_mismatch(tmp_path):
    manifest, attestation, approval, ledger, inputs, evidence = _bundle(tmp_path)
    evidence["approval_reviewer_id"] = "other-reviewer"
    with pytest.raises(ValueError, match="does not match"):
        evaluate_governed_release(
            manifest=manifest, attestation=attestation, approval_record=approval,
            ledger=ledger, inputs=inputs, github_evidence=evidence,
        )


def test_governed_release_rejects_changed_input_bytes(tmp_path):
    manifest, attestation, approval, ledger, inputs, evidence = _bundle(tmp_path)
    inputs["dataset"].write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="input mismatch"):
        evaluate_governed_release(
            manifest=manifest, attestation=attestation, approval_record=approval,
            ledger=ledger, inputs=inputs, github_evidence=evidence,
        )


def test_governed_release_rejects_malformed_github_evidence(tmp_path):
    manifest, attestation, approval, ledger, inputs, evidence = _bundle(tmp_path)
    evidence["approval_reviewer_id"] = None
    with pytest.raises(ValueError, match="reviewer"):
        evaluate_governed_release(
            manifest=manifest, attestation=attestation, approval_record=approval,
            ledger=ledger, inputs=inputs, github_evidence=evidence,
        )
