import json
import subprocess
import sys

CLI = [sys.executable, "-m", "services.rag.calibration_approval_ledger_cli"]
A = "a" * 64


def _run(*args):
    return subprocess.run(CLI + list(args), capture_output=True, text=True, check=False)


def test_ledger_cli_appends_and_verifies_lifecycle(tmp_path):
    source = tmp_path / "missing-ledger.json"
    output = tmp_path / "ledger.json"
    created = _run(
        "append", "--ledger", str(source), "--output", str(output),
        "--action", "approved", "--approval-sha256", A,
        "--actor-id", "reviewer", "--reason", "reviewed",
        "--occurred-at", "2026-10-30T10:00:00Z",
    )
    verified = _run("verify", "--ledger", str(output))
    assert created.returncode == 0, created.stderr
    assert json.loads(created.stdout)["event_count"] == 1
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["active_approval_sha256"] == [A]


def test_ledger_cli_rejects_forged_event_chain(tmp_path):
    ledger = tmp_path / "ledger.json"
    output = tmp_path / "next.json"
    ledger.write_text(json.dumps({
        "schema_version": 1,
        "events": [{
            "sequence": 1,
            "action": "approved",
            "approval_record_sha256": A,
            "actor_id": "reviewer",
            "reason": "approved baseline",
            "occurred_at": "2026-10-30T10:00:00Z",
            "previous_event_sha256": None,
            "replacement_approval_sha256": None,
            "event_sha256": "0" * 64,
        }],
    }), encoding="utf-8")
    result = _run(
        "append", "--ledger", str(ledger), "--output", str(output),
        "--action", "revoked", "--approval-sha256", A,
        "--actor-id", "reviewer", "--reason", "revoke",
        "--occurred-at", "2026-10-30T11:00:00Z",
    )
    assert result.returncode == 2
    assert "SHA-256" in result.stderr


def test_ledger_cli_verify_requires_existing_file(tmp_path):
    result = _run("verify", "--ledger", str(tmp_path / "absent.json"))
    assert result.returncode == 2
