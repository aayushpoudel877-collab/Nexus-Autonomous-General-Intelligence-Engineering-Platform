from __future__ import annotations

import copy

import pytest

from services.rag.calibration_approval_ledger import (
    active_approvals,
    append_lifecycle_event,
    new_ledger,
    validate_ledger,
)


A = "a" * 64
B = "b" * 64
C = "c" * 64
WHEN = "2026-10-30T10:00:00Z"


def _append(ledger, action, digest, **kwargs):
    return append_lifecycle_event(
        ledger,
        action=action,
        approval_record_sha256=digest,
        actor_id="reviewer-1",
        reason="reviewed evidence",
        occurred_at=WHEN,
        **kwargs,
    )


def test_ledger_records_approval_and_validates_hash_chain():
    ledger = _append(new_ledger(), "approved", A)
    ledger = _append(ledger, "approved", B)
    assert validate_ledger(ledger) == ledger
    assert active_approvals(ledger) == {A, B}
    assert ledger["events"][1]["previous_event_sha256"] == ledger["events"][0]["event_sha256"]


def test_ledger_revocation_removes_approval_from_active_set():
    ledger = _append(new_ledger(), "approved", A)
    ledger = _append(ledger, "revoked", A)
    assert validate_ledger(ledger) == ledger
    assert active_approvals(ledger) == set()


def test_ledger_supersession_retires_old_and_activates_replacement():
    ledger = _append(new_ledger(), "approved", A)
    ledger = _append(
        ledger, "superseded", A, replacement_approval_sha256=B
    )
    assert validate_ledger(ledger) == ledger
    assert active_approvals(ledger) == {B}


def test_ledger_rejects_revoking_unknown_or_inactive_approval():
    with pytest.raises(ValueError, match="active approval"):
        _append(new_ledger(), "revoked", A)
    ledger = _append(new_ledger(), "approved", A)
    ledger = _append(ledger, "revoked", A)
    with pytest.raises(ValueError, match="active approval"):
        _append(ledger, "revoked", A)


def test_ledger_rejects_duplicate_active_approval_and_bad_supersession():
    ledger = _append(new_ledger(), "approved", A)
    with pytest.raises(ValueError, match="already appears"):
        _append(ledger, "approved", A)
    with pytest.raises(ValueError, match="must differ"):
        _append(ledger, "superseded", A, replacement_approval_sha256=A)
    with pytest.raises(ValueError, match="replacement_approval_sha256"):
        _append(ledger, "superseded", A)


def test_ledger_detects_event_tampering_and_broken_chain():
    ledger = _append(new_ledger(), "approved", A)
    ledger = _append(ledger, "approved", B)
    tampered = copy.deepcopy(ledger)
    tampered["events"][0]["reason"] = "rewritten"
    with pytest.raises(ValueError, match="SHA-256"):
        validate_ledger(tampered)
    broken = copy.deepcopy(ledger)
    broken["events"][1]["previous_event_sha256"] = C
    with pytest.raises(ValueError, match="chain is broken"):
        validate_ledger(broken)


def test_ledger_rejects_non_contiguous_sequence_and_naive_timestamp():
    ledger = _append(new_ledger(), "approved", A)
    malformed = copy.deepcopy(ledger)
    malformed["events"][0]["sequence"] = 2
    with pytest.raises(ValueError, match="sequence"):
        validate_ledger(malformed)
    with pytest.raises(ValueError, match="timezone"):
        append_lifecycle_event(
            new_ledger(), action="approved", approval_record_sha256=A,
            actor_id="reviewer", reason="reviewed", occurred_at="2026-10-30T10:00:00",
        )


def test_ledger_rejects_boolean_schema_version():
    with pytest.raises(ValueError, match="schema_version"):
        validate_ledger({"schema_version": True, "events": []})



def test_ledger_does_not_allow_replaying_a_revoked_approval():
    ledger = _append(new_ledger(), "approved", A)
    ledger = _append(ledger, "revoked", A)
    with pytest.raises(ValueError, match="already appears"):
        _append(ledger, "approved", A)
