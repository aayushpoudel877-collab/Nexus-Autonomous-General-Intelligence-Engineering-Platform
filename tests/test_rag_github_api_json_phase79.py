from __future__ import annotations

import pytest

from services.rag.github_api_json import loads_github_json


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b'{"number": 1, "number": 2}', "duplicate JSON object key"),
        (b'{"score": NaN}', "non-finite JSON number"),
        (b'{"score": Infinity}', "non-finite JSON number"),
        (b'{"score": -Infinity}', "non-finite JSON number"),
        (b'{"broken": ', "invalid JSON"),
        (b'\xff', "invalid JSON"),
    ],
)
def test_github_json_decoder_rejects_ambiguous_or_invalid_payloads(payload, message):
    with pytest.raises(ValueError, match=message):
        loads_github_json(payload)


def test_github_json_decoder_preserves_valid_nested_objects_and_arrays():
    assert loads_github_json(
        b'{"pull_request": {"number": 9}, "reviews": [{"id": 1}, {"id": 2}]}'
    ) == {
        "pull_request": {"number": 9},
        "reviews": [{"id": 1}, {"id": 2}],
    }


def test_github_json_decoder_rejects_duplicate_nested_keys():
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        loads_github_json(b'{"outer": {"id": 1, "id": 2}}')
