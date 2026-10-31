from __future__ import annotations

import pytest

from services.rag import calibration_governance
from services.rag.calibration_governance import validate_github_review_payload

REPOSITORY = "aayushpoudel877-collab/Nexus-Autonomous-General-Intelligence-Engineering-Platform"
HEAD = "a" * 40


def _pr(**overrides):
    value = {
        "number": 74,
        "state": "closed",
        "merged": True,
        "merged_at": "2026-10-31T10:00:00Z",
        "base": {"repo": {"full_name": REPOSITORY}},
        "head": {"sha": HEAD},
    }
    value.update(overrides)
    return value


def _review(login="reviewer-17", state="APPROVED", *, commit=HEAD, submitted="2026-10-31T09:00:00Z"):
    return {
        "user": {"login": login},
        "state": state,
        "commit_id": commit,
        "submitted_at": submitted,
    }


def _validate(pr=None, reviews=None, **overrides):
    args = {
        "repository": REPOSITORY,
        "pull_request_number": 74,
        "expected_head_sha": HEAD,
        "approval_reviewer_id": "reviewer-17",
        "allowed_reviewers": {"reviewer-17", "reviewer-22"},
        "minimum_approvals": 1,
    }
    args.update(overrides)
    return validate_github_review_payload(
        pr if pr is not None else _pr(),
        reviews if reviews is not None else [_review()],
        **args,
    )


def test_github_review_evidence_accepts_allowlisted_approval_for_merged_head():
    result = _validate()
    assert result["provider"] == "github"
    assert result["approved_reviewers"] == ["reviewer-17"]
    assert result["head_sha"] == HEAD


def test_github_review_evidence_requires_allowlisted_reviewers():
    with pytest.raises(ValueError, match="below required"):
        _validate(reviews=[_review(login="untrusted-user")])


def test_github_review_evidence_rejects_stale_head_reviews():
    with pytest.raises(ValueError, match="below required"):
        _validate(reviews=[_review(commit="b" * 40)])


def test_latest_review_state_wins_and_dismissal_revokes_approval():
    reviews = [
        _review(state="APPROVED", submitted="2026-10-31T09:00:00Z"),
        _review(state="DISMISSED", submitted="2026-10-31T09:30:00Z"),
    ]
    with pytest.raises(ValueError, match="below required"):
        _validate(reviews=reviews)


def test_latest_changes_requested_overrides_earlier_approval():
    reviews = [
        _review(state="APPROVED", submitted="2026-10-31T09:00:00Z"),
        _review(state="CHANGES_REQUESTED", submitted="2026-10-31T09:30:00Z"),
    ]
    with pytest.raises(ValueError, match="below required"):
        _validate(reviews=reviews)


def test_distinct_allowlisted_approvals_satisfy_threshold():
    result = _validate(
        reviews=[
            _review(),
            _review(login="reviewer-22", submitted="2026-10-31T09:15:00Z"),
        ],
        minimum_approvals=2,
    )
    assert result["approved_reviewers"] == ["reviewer-17", "reviewer-22"]


@pytest.mark.parametrize(
    ("pr", "message"),
    [
        (_pr(number=73), "number"),
        (_pr(base={"repo": {"full_name": "someone/else"}}), "different repository"),
        (_pr(head={"sha": "b" * 40}), "head does not match"),
        (_pr(state="open", merged=False, merged_at=None), "must be merged"),
        (_pr(merged_at=None), "merged_at"),
    ],
)
def test_github_review_evidence_rejects_wrong_pr_context(pr, message):
    with pytest.raises(ValueError, match=message):
        _validate(pr=pr)


def test_github_review_evidence_rejects_naive_review_timestamp():
    with pytest.raises(ValueError, match="timezone"):
        _validate(reviews=[_review(submitted="2026-10-31T09:00:00")])


def test_github_review_evidence_requires_valid_sha_and_allowlist():
    with pytest.raises(ValueError, match="full lowercase commit SHA"):
        _validate(expected_head_sha="short")
    with pytest.raises(ValueError, match="allowlisted"):
        _validate(allowed_reviewers=set())



def test_github_review_fetch_requires_api_token():
    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        calibration_governance.fetch_github_review_evidence(
            repository="owner/repo",
            pull_request_number=74,
            expected_head_sha=HEAD,
            approval_reviewer_id="reviewer-17",
            allowed_reviewers={"reviewer-17"},
            token="",
        )


def test_github_review_fetch_paginates_all_review_pages(monkeypatch):
    calls = []

    def fake_get(url, token):
        calls.append((url, token))
        if url.endswith("/pulls/74"):
            return _pr()
        if "page=1" in url:
            return [_review()] + [
                _review(login="noise-reviewer", state="COMMENTED")
                for _ in range(99)
            ]
        if "page=2" in url:
            return [_review(login="reviewer-22", submitted="2026-10-31T09:15:00Z")]
        raise AssertionError(f"unexpected API request: {url}")

    monkeypatch.setattr(calibration_governance, "_github_get", fake_get)
    result = calibration_governance.fetch_github_review_evidence(
        repository=REPOSITORY,
        pull_request_number=74,
        expected_head_sha=HEAD,
        approval_reviewer_id="reviewer-17",
        allowed_reviewers={"reviewer-17", "reviewer-22"},
        token="api-token",
        minimum_approvals=2,
    )
    assert result["approved_reviewers"] == ["reviewer-17", "reviewer-22"]
    assert len(calls) == 3
    assert all(token == "api-token" for _, token in calls)
