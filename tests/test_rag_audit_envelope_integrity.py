from copy import deepcopy

import pytest

from services.rag.governance import (
    seal_tool_provenance_audit_details,
    verify_tool_provenance_audit_details,
)


def _details():
    return {
        "schema_version": 1,
        "tool_outputs": [
            {
                "tool_name": "lexical_search",
                "content_sha256": "a" * 64,
                "detector_version": "markers-v1",
                "injection_markers": ["instruction_override"],
                "output_chars": 128,
                "evidence_count": 2,
                "untrusted": True,
            }
        ],
    }


def test_audit_envelope_seal_is_deterministic_and_verifiable():
    first = seal_tool_provenance_audit_details(_details())
    second = seal_tool_provenance_audit_details(_details())

    assert first == second
    assert len(first["payload_sha256"]) == 64
    assert verify_tool_provenance_audit_details(first)


@pytest.mark.parametrize("path,value", [
    (("tool_outputs", 0, "output_chars"), 129),
    (("tool_outputs", 0, "untrusted"), False),
    (("tool_outputs", 0, "content_sha256"), "b" * 64),
])
def test_audit_envelope_detects_metadata_tampering(path, value):
    envelope = seal_tool_provenance_audit_details(_details())
    changed = deepcopy(envelope)
    changed[path[0]][path[1]][path[2]] = value

    assert not verify_tool_provenance_audit_details(changed)


def test_audit_envelope_rejects_raw_output_fields():
    details = _details()
    details["tool_outputs"][0]["text"] = "raw confidential tool output"

    with pytest.raises(ValueError, match="metadata-only"):
        seal_tool_provenance_audit_details(details)


def test_audit_envelope_rejects_invalid_untrusted_metadata():
    details = _details()
    details["tool_outputs"][0]["untrusted"] = False

    with pytest.raises(ValueError, match="remain untrusted"):
        seal_tool_provenance_audit_details(details)


def test_audit_envelope_verification_fails_closed_for_extra_keys():
    envelope = seal_tool_provenance_audit_details(_details())
    envelope["raw_output"] = "should never be present"

    assert not verify_tool_provenance_audit_details(envelope)


def test_audit_envelope_rejects_noncanonical_or_unbounded_payloads():
    with pytest.raises(ValueError, match="bounded list"):
        seal_tool_provenance_audit_details({
            "schema_version": 1,
            "tool_outputs": [_details()["tool_outputs"][0]] * 13,
        })
    with pytest.raises(ValueError, match="schema_version"):
        seal_tool_provenance_audit_details({"schema_version": 2, "tool_outputs": []})


def test_audit_envelope_rejects_boolean_counts():
    details = _details()
    details["tool_outputs"][0]["output_chars"] = True

    with pytest.raises(ValueError, match="output_chars"):
        seal_tool_provenance_audit_details(details)

def test_audit_envelope_rejects_boolean_schema_version():
    with pytest.raises(ValueError, match="schema_version"):
        seal_tool_provenance_audit_details({"schema_version": True, "tool_outputs": []})


def test_audit_envelope_rejects_non_string_markers_cleanly():
    details = _details()
    details["tool_outputs"][0]["injection_markers"] = [["instruction_override"]]

    with pytest.raises(ValueError, match="injection markers"):
        seal_tool_provenance_audit_details(details)

