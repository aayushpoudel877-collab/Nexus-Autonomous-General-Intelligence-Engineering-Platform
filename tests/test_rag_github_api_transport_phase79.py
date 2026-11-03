from __future__ import annotations

import pytest

from services.rag import calibration_governance


class _Response:
    status = 200

    def __init__(self, payload: bytes, headers=None):
        self.payload = payload
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.payload[:size]


@pytest.mark.parametrize(
    "payload",
    [
        b'{"number": 7, "number": 8}',
        b'{"merged": NaN}',
        b'{"state": Infinity}',
        b'\xff',
        b'{"truncated": ',
    ],
)
def test_github_get_rejects_ambiguous_or_invalid_json(monkeypatch, payload):
    monkeypatch.setattr(
        calibration_governance.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _Response(payload),
    )
    with pytest.raises(ValueError, match="GitHub API returned invalid JSON"):
        calibration_governance._github_get("https://api.github.com/test", "token")


def test_github_get_accepts_valid_json_object(monkeypatch):
    monkeypatch.setattr(
        calibration_governance.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _Response(b'{"number": 7, "merged": true}'),
    )
    assert calibration_governance._github_get(
        "https://api.github.com/test", "token"
    ) == {"number": 7, "merged": True}


def test_github_review_fetch_rejects_non_object_pull_request_before_review_fetch(monkeypatch):
    calls = []

    def fake_get(url, token):
        calls.append(url)
        return []

    monkeypatch.setattr(calibration_governance, "_github_get", fake_get)
    with pytest.raises(TypeError, match="pull request endpoint returned an invalid object"):
        calibration_governance.fetch_github_review_evidence(
            repository="owner/repo",
            pull_request_number=7,
            expected_head_sha="a" * 40,
            approval_reviewer_id="reviewer",
            allowed_reviewers={"reviewer"},
            token="test-token",
        )
    assert len(calls) == 1
