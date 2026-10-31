from __future__ import annotations

from services.rag import calibration_governance


def test_github_get_rejects_declared_response_over_byte_limit(monkeypatch):
    class Response:
        status = 200
        headers = {"Content-Length": "9"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            raise AssertionError("oversized declared response must not be read")

    monkeypatch.setattr(calibration_governance, "_MAX_GITHUB_RESPONSE_BYTES", 8)
    monkeypatch.setattr(calibration_governance.urllib.request, "urlopen", lambda *a, **k: Response())

    try:
        calibration_governance._github_get("https://api.github.com/test", "token")
    except ValueError as exc:
        assert "byte limit" in str(exc)
    else:
        raise AssertionError("expected oversized response to be rejected")


def test_github_get_rejects_streamed_response_over_byte_limit(monkeypatch):
    class Response:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            assert size == 9
            return b"x" * size

    monkeypatch.setattr(calibration_governance, "_MAX_GITHUB_RESPONSE_BYTES", 8)
    monkeypatch.setattr(calibration_governance.urllib.request, "urlopen", lambda *a, **k: Response())

    try:
        calibration_governance._github_get("https://api.github.com/test", "token")
    except ValueError as exc:
        assert "byte limit" in str(exc)
    else:
        raise AssertionError("expected streamed oversized response to be rejected")


def test_github_review_fetch_rejects_total_review_count_over_limit(monkeypatch):
    head = "a" * 40
    repository = "owner/repo"
    calls = []

    def review(login, state="COMMENTED"):
        return {
            "user": {"login": login},
            "state": state,
            "commit_id": head,
            "submitted_at": "2026-10-31T09:00:00Z",
        }

    def fake_get(url, token):
        calls.append(url)
        if url.endswith("/pulls/7"):
            return {
                "number": 7,
                "state": "closed",
                "merged": True,
                "merged_at": "2026-10-31T10:00:00Z",
                "base": {"repo": {"full_name": repository}},
                "head": {"sha": head},
            }
        if url.endswith("page=1"):
            return [review("reviewer") for _ in range(100)]
        if url.endswith("page=2"):
            return [review("reviewer")]
        raise AssertionError(f"unexpected API request: {url}")

    monkeypatch.setattr(calibration_governance, "_MAX_GITHUB_REVIEWS", 100)
    monkeypatch.setattr(calibration_governance, "_github_get", fake_get)

    try:
        calibration_governance.fetch_github_review_evidence(
            repository=repository,
            pull_request_number=7,
            expected_head_sha=head,
            approval_reviewer_id="reviewer",
            allowed_reviewers={"reviewer"},
            token="test-token",
        )
    except ValueError as exc:
        assert "total review limit" in str(exc)
    else:
        raise AssertionError("expected review count overflow to be rejected")
    assert len(calls) == 3
