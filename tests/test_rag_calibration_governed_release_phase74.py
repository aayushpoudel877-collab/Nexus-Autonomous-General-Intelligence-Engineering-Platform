from __future__ import annotations

import json

import pytest

from services.rag import calibration_governance, calibration_release_gate_cli
from services.rag.calibration_approval import build_approval_record
from services.rag.calibration_approval_ledger import append_lifecycle_event, new_ledger
from services.rag.calibration_baseline import build_manifest
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


def _install_review_fetch(monkeypatch, evidence):
    def fake_fetch(**kwargs):
        assert kwargs["expected_head_sha"] == "a" * 40
        assert kwargs["approval_reviewer_id"] == "reviewer-17"
        return evidence

    monkeypatch.setattr(calibration_governance, "fetch_github_review_evidence", fake_fetch)


def _evaluate(monkeypatch, bundle):
    manifest, attestation, approval, ledger, inputs, evidence = bundle
    _install_review_fetch(monkeypatch, evidence)
    return calibration_governance.evaluate_governed_release(
        manifest=manifest, attestation=attestation, approval_record=approval,
        ledger=ledger, inputs=inputs, repository="owner/repo",
        pull_request_number=74, allowed_reviewers={"reviewer-17"},
        token="test-token", minimum_approvals=1,
    )


def test_governed_release_requires_active_approval_and_exact_github_reviewer(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path)
    result = _evaluate(monkeypatch, bundle)
    assert result["verified"] is True
    assert result["approval_record_sha256"] == bundle[2]["approval_record_sha256"]


def test_governed_release_rejects_revoked_approval(tmp_path, monkeypatch):
    bundle = list(_bundle(tmp_path))
    approval, ledger = bundle[2], bundle[3]
    bundle[3] = append_lifecycle_event(
        ledger, action="revoked",
        approval_record_sha256=approval["approval_record_sha256"],
        actor_id="reviewer-17", reason="approval withdrawn",
        occurred_at="2026-10-31T10:00:00Z",
    )
    with pytest.raises(ValueError, match="not active"):
        _evaluate(monkeypatch, tuple(bundle))


def test_governed_release_rejects_changed_input_bytes(tmp_path, monkeypatch):
    bundle = list(_bundle(tmp_path))
    bundle[4]["dataset"].write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="input mismatch"):
        _evaluate(monkeypatch, tuple(bundle))


def test_release_gate_cli_can_require_trusted_governance(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path)
    manifest, attestation, approval, ledger, inputs, evidence = bundle
    baseline_path = tmp_path / "baseline.json"
    attestation_path = tmp_path / "attestation.json"
    approval_path = tmp_path / "approval.json"
    ledger_path = tmp_path / "ledger.json"
    current_path = tmp_path / "current.json"
    output_path = tmp_path / "decision.json"
    baseline_path.write_text(json.dumps(manifest), encoding="utf-8")
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    current_path.write_text(json.dumps(_report()), encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    _install_review_fetch(monkeypatch, evidence)
    result = calibration_release_gate_cli.main([
        "--baseline-manifest", str(baseline_path),
        "--current", str(current_path),
        "--output", str(output_path),
        "--require-governance",
        "--attestation", str(attestation_path),
        "--approval", str(approval_path),
        "--ledger", str(ledger_path),
        "--input", f"dataset={inputs['dataset']}",
        "--repository", "owner/repo",
        "--pull-request", "74",
        "--allowed-reviewer", "reviewer-17",
    ])
    decision = json.loads(output_path.read_text(encoding="utf-8"))
    assert result == 0
    assert decision["decision"] == "pass"
    assert decision["governance"]["verified"] is True


def test_release_gate_cli_fails_closed_when_governance_inputs_are_incomplete(tmp_path):
    current = tmp_path / "current.json"
    current.write_text(json.dumps(_report()), encoding="utf-8")
    result = calibration_release_gate_cli.main([
        "--baseline-manifest", str(tmp_path / "missing-manifest.json"),
        "--current", str(current),
        "--output", str(tmp_path / "decision.json"),
        "--require-governance",
    ])
    assert result == 2
    decision = json.loads((tmp_path / "decision.json").read_text(encoding="utf-8"))
    assert decision["decision"] == "error"
    assert "needs attestation" in decision["error"]
