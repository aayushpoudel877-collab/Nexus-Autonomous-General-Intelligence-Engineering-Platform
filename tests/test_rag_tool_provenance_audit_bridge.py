import hashlib
from types import SimpleNamespace

import pytest

from services.rag.governance import build_tool_provenance_audit_details, stable_json
from services.rag.prompt_injection import DETECTOR_VERSION


def _record(text="tool result contains private source content"):
    return SimpleNamespace(
        tool_name="lexical_search",
        text=text,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        detector_version=DETECTOR_VERSION,
        injection_markers=("instruction_override",),
        output_chars=len(text),
        evidence_ids=("private-evidence-id",),
        untrusted=True,
    )


def test_audit_bridge_serializes_only_safe_tool_provenance_metadata():
    record = _record()
    payload = build_tool_provenance_audit_details((record,))

    assert payload["schema_version"] == 1
    assert len(payload["tool_outputs"]) == 1
    item = payload["tool_outputs"][0]
    assert item["content_sha256"] == record.content_sha256
    assert item["detector_version"] == DETECTOR_VERSION
    assert item["untrusted"] is True
    assert item["evidence_count"] == 1
    serialized = str(payload)
    assert record.text not in serialized
    assert "private-evidence-id" not in serialized
    assert "evidence_ids" not in serialized


def test_audit_bridge_rejects_tampered_tool_output():
    record = _record()
    record = SimpleNamespace(**{**vars(record), "text": "tampered after hashing"})
    with pytest.raises(ValueError, match="does not match"):
        build_tool_provenance_audit_details((record,))


def test_audit_bridge_enforces_provenance_batch_bound():
    record = _record()
    with pytest.raises(ValueError, match="record limit"):
        build_tool_provenance_audit_details((record,) * 13)


def test_audit_bridge_rejects_untrusted_flag_downgrade():
    record = _record()
    record = SimpleNamespace(**{**vars(record), "untrusted": False})
    with pytest.raises(ValueError, match="untrusted"):
        build_tool_provenance_audit_details((record,))


def test_audit_bridge_empty_batch_is_stable_and_versioned():
    payload = build_tool_provenance_audit_details(())
    assert payload == {"schema_version": 1, "tool_outputs": []}
    assert stable_json(payload) == '{"schema_version":1,"tool_outputs":[]}'


def test_audit_bridge_rejects_malformed_tool_identifier():
    record = _record()
    record = SimpleNamespace(**{**vars(record), "tool_name": "Invalid Tool Name"})
    with pytest.raises(ValueError, match="tool_name"):
        build_tool_provenance_audit_details((record,))
