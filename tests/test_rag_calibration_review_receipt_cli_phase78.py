from __future__ import annotations

import json

import pytest

from services.rag.calibration_baseline import sha256_json
from services.rag.calibration_review_receipt_cli import (
    main,
    read_receipt,
    verify_receipt_file,
)

HEAD = "a" * 40


def _receipt():
    body = {
        "schema_version": 1,
        "provider": "github",
        "repository": "owner/repo",
        "pull_request": 78,
        "head_sha": HEAD,
        "minimum_approvals": 1,
        "approval_reviewer_id": "reviewer-1",
        "review_decisions": [
            {
                "reviewer_login": "reviewer-1",
                "review_id": 1001,
                "state": "APPROVED",
                "submitted_at": "2026-11-01T10:00:00Z",
                "head_sha": HEAD,
            }
        ],
    }
    return {
        **body,
        "approved_reviewers": ["reviewer-1"],
        "review_count": 1,
        "review_evidence_sha256": sha256_json(body),
    }


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_read_receipt_accepts_valid_json_object(tmp_path):
    path = _write(tmp_path / "receipt.json", _receipt())
    assert read_receipt(path)["repository"] == "owner/repo"


def test_verify_receipt_file_returns_minimal_summary(tmp_path):
    path = _write(tmp_path / "receipt.json", _receipt())
    result = verify_receipt_file(path)
    assert result == {
        "valid": True,
        "schema_version": 1,
        "repository": "owner/repo",
        "pull_request": 78,
        "head_sha": HEAD,
        "review_count": 1,
        "approved_reviewer_count": 1,
        "review_evidence_sha256": _receipt()["review_evidence_sha256"],
    }
    assert "review_decisions" not in result


@pytest.mark.parametrize("payload", ["[]", "null", '"receipt"', "42"])
def test_read_receipt_rejects_non_object_json(tmp_path, payload):
    path = tmp_path / "receipt.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(TypeError, match="JSON object"):
        read_receipt(path)


@pytest.mark.parametrize("payload", ["{", '{"x": NaN}', '{"x": Infinity}'])
def test_read_receipt_rejects_malformed_or_non_finite_json(tmp_path, payload):
    path = tmp_path / "receipt.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match="valid review receipt JSON"):
        read_receipt(path)


def test_read_receipt_rejects_invalid_utf8(tmp_path):
    path = tmp_path / "receipt.json"
    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="valid review receipt JSON"):
        read_receipt(path)


def test_read_receipt_rejects_missing_file(tmp_path):
    with pytest.raises(ValueError, match="cannot read review receipt"):
        read_receipt(tmp_path / "missing.json")


def test_read_receipt_enforces_byte_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "services.rag.calibration_review_receipt_cli._MAX_RECEIPT_BYTES", 8
    )
    path = tmp_path / "large.json"
    path.write_bytes(b'{"x": "too large"}')
    with pytest.raises(ValueError, match="1000000-byte limit|byte limit"):
        read_receipt(path)


def test_verifier_rejects_tampered_receipt(tmp_path):
    receipt = _receipt()
    receipt["repository"] = "other/repo"
    path = _write(tmp_path / "receipt.json", receipt)
    with pytest.raises(ValueError, match="digest does not match"):
        verify_receipt_file(path)


def test_cli_emits_json_and_returns_zero(tmp_path, capsys):
    path = _write(tmp_path / "receipt.json", _receipt())
    assert main(["--receipt", str(path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is True
    assert output["pull_request"] == 78


def test_cli_returns_two_for_invalid_receipt(tmp_path, capsys):
    path = _write(tmp_path / "receipt.json", {"invalid": True})
    assert main(["--receipt", str(path)]) == 2
    assert "verification failed" in capsys.readouterr().err
