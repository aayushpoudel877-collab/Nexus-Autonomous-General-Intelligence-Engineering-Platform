from __future__ import annotations

import pytest

from services.rag.calibration_baseline import sha256_json
from services.rag.calibration_governance import verify_github_review_receipt


HEAD = "a" * 40


def _receipt():
    body = {
        "schema_version": 1,
        "provider": "github",
        "repository": "owner/repo",
        "pull_request": 74,
        "head_sha": HEAD,
        "minimum_approvals": 2,
        "approval_reviewer_id": "reviewer-17",
        "review_decisions": [
            {
                "reviewer_login": "reviewer-17",
                "review_id": 11,
                "state": "APPROVED",
                "submitted_at": "2026-10-31T09:00:00Z",
                "head_sha": HEAD,
            },
            {
                "reviewer_login": "reviewer-22",
                "review_id": 12,
                "state": "APPROVED",
                "submitted_at": "2026-10-31T09:05:00Z",
                "head_sha": HEAD,
            },
        ],
    }
    return {
        **body,
        "approved_reviewers": ["reviewer-17", "reviewer-22"],
        "review_count": 2,
        "review_evidence_sha256": sha256_json(body),
    }


def test_versioned_review_receipt_verifies():
    assert verify_github_review_receipt(_receipt()) is True


def test_receipt_rejects_content_tampering_even_when_shape_is_valid():
    receipt = _receipt()
    receipt["repository"] = "attacker/other"
    with pytest.raises(ValueError, match="digest does not match"):
        verify_github_review_receipt(receipt)


@pytest.mark.parametrize("field", ["schema_version", "review_decisions", "review_evidence_sha256"])
def test_receipt_rejects_missing_required_fields(field):
    receipt = _receipt()
    del receipt[field]
    with pytest.raises(ValueError, match="invalid schema"):
        verify_github_review_receipt(receipt)


@pytest.mark.parametrize("version", [True, 0, 2, "1"])
def test_receipt_rejects_unsupported_schema_versions(version):
    receipt = _receipt()
    receipt["schema_version"] = version
    with pytest.raises(ValueError, match="version is unsupported"):
        verify_github_review_receipt(receipt)


def test_receipt_rejects_untrimmed_approval_identity():
    receipt = _receipt()
    receipt["approval_reviewer_id"] = " reviewer-17 "
    with pytest.raises(ValueError, match="reviewer is missing"):
        verify_github_review_receipt(receipt)


def test_receipt_rejects_unrecognized_fields():
    receipt = _receipt()
    receipt["unreviewed_metadata"] = "not covered by schema"
    with pytest.raises(ValueError, match="invalid schema"):
        verify_github_review_receipt(receipt)


def test_receipt_rejects_duplicate_review_ids():
    receipt = _receipt()
    receipt["review_decisions"][1]["review_id"] = 11
    with pytest.raises(ValueError, match="duplicate review ids"):
        verify_github_review_receipt(receipt)


def test_receipt_rejects_non_utc_timestamps():
    receipt = _receipt()
    receipt["review_decisions"][0]["submitted_at"] = "2026-10-31T11:00:00+02:00"
    with pytest.raises(ValueError, match="UTC-normalized"):
        verify_github_review_receipt(receipt)


def test_receipt_rejects_decision_bound_to_another_head():
    receipt = _receipt()
    receipt["review_decisions"][0]["head_sha"] = "b" * 40
    with pytest.raises(ValueError, match="another head"):
        verify_github_review_receipt(receipt)


def test_receipt_rejects_unsorted_or_duplicate_reviewer_decisions():
    receipt = _receipt()
    receipt["review_decisions"].reverse()
    with pytest.raises(ValueError, match="uniquely sorted"):
        verify_github_review_receipt(receipt)


def test_receipt_rejects_approval_summary_mismatch():
    receipt = _receipt()
    receipt["approved_reviewers"] = ["reviewer-17"]
    with pytest.raises(ValueError, match="list is inconsistent"):
        verify_github_review_receipt(receipt)


def test_receipt_rejects_digest_with_wrong_format():
    receipt = _receipt()
    receipt["review_evidence_sha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="digest is malformed"):
        verify_github_review_receipt(receipt)
