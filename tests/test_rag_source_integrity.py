from hashlib import sha256

import pytest

from services.rag.source_integrity import (
    MAX_ARTIFACT_BYTES,
    IntegrityReceipt,
    verify_artifact,
    verify_batch,
)


def test_verifies_matching_source_bytes_without_exposing_content():
    content = b"private source text"
    receipt = verify_artifact("doc-1", sha256(content).hexdigest(), content)

    assert receipt == IntegrityReceipt(
        artifact_id="doc-1",
        expected_sha256=sha256(content).hexdigest(),
        observed_sha256=sha256(content).hexdigest(),
        status="verified",
        size_bytes=len(content),
    )
    assert content.decode() not in repr(receipt)


def test_reports_changed_source_as_mismatch():
    expected = sha256(b"original").hexdigest()

    receipt = verify_artifact("doc-2", expected, b"changed")

    assert receipt.status == "mismatch"
    assert receipt.reason == "sha256_mismatch"
    assert receipt.observed_sha256 == sha256(b"changed").hexdigest()


def test_missing_source_is_unavailable_not_a_mismatch():
    receipt = verify_artifact("doc-3", sha256(b"").hexdigest(), None)

    assert receipt.status == "unavailable"
    assert receipt.observed_sha256 is None
    assert receipt.reason == "source_bytes_unavailable"


def test_oversized_source_is_not_hashed():
    receipt = verify_artifact(
        "doc-4", sha256(b"").hexdigest(), b"12345", max_bytes=4
    )

    assert receipt.status == "not_checked"
    assert receipt.observed_sha256 is None
    assert receipt.reason == "artifact_exceeds_size_limit"


@pytest.mark.parametrize(
    "artifact_id,digest,content",
    [
        ("", sha256(b"x").hexdigest(), b"x"),
        ("doc", "bad-digest", b"x"),
        ("doc", sha256(b"x").hexdigest(), "not-bytes"),
    ],
)
def test_rejects_invalid_input(artifact_id, digest, content):
    with pytest.raises((ValueError, TypeError)):
        verify_artifact(artifact_id, digest, content)


def test_rejects_unreasonable_limits():
    with pytest.raises(ValueError):
        verify_artifact("doc", sha256(b"x").hexdigest(), b"x", max_bytes=0)
    with pytest.raises(ValueError):
        verify_artifact(
            "doc", sha256(b"x").hexdigest(), b"x", max_bytes=MAX_ARTIFACT_BYTES + 1
        )


def test_batch_verifies_each_item_and_preserves_order():
    first = b"first"
    second = b"second"
    receipts = verify_batch(
        [
            ("a", sha256(first).hexdigest(), first),
            ("b", sha256(b"expected").hexdigest(), second),
        ]
    )

    assert [receipt.artifact_id for receipt in receipts] == ["a", "b"]
    assert [receipt.status for receipt in receipts] == ["verified", "mismatch"]


def test_batch_rejects_excess_items_and_malformed_records():
    with pytest.raises(ValueError, match="exceeds"):
        verify_batch(
            [
                ("a", sha256(b"a").hexdigest(), b"a"),
                ("b", sha256(b"b").hexdigest(), b"b"),
            ],
            max_items=1,
        )
    with pytest.raises(ValueError, match="tuple"):
        verify_batch([("not", "a", "valid", "record")])
