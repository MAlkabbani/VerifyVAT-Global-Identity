"""Focused tests for CLI routing and output discipline."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import verifyvat_cli.main as cli_main
from verifyvat_cli.core import PersistedStatus, RuntimeStatus, VerificationResult


def make_result(*, status: RuntimeStatus = "VALID") -> VerificationResult:
    """Create a reusable verification result fixture."""

    persisted_status: PersistedStatus = "NETWORK_ERROR" if status == "CONFIG_ERROR" else status

    return VerificationResult(
        raw_identifier="914778271",
        normalized_identifier="914778271",
        inferred_type="no_orgnr",
        status=status,
        persisted_status=persisted_status,
        execution_timestamp="2026-07-21T00:00:00Z",
        consultation_receipt="receipt-123",
        legal_name="Example Org",
        address="Oslo",
        diagnostics=["ok"] if status == "VALID" else [status.lower()],
        provider_payload={"verification": {"status": status}},
    )


def test_check_json_stdout_contains_only_machine_readable_payload(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """`--json` mode should write only the JSON result to stdout."""

    monkeypatch.setattr(cli_main, "get_default_db_path", lambda: tmp_path / "audit.db")
    monkeypatch.setattr(cli_main, "verify_once", lambda *args, **kwargs: make_result())
    monkeypatch.setattr(cli_main, "_persist_result", lambda *args, **kwargs: None)

    exit_code = cli_main.main(["check", "914778271", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out)["raw_identifier"] == "914778271"


def test_check_persists_before_rendering(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The CLI should never render a check result before the audit write completes."""

    call_order: list[str] = []

    monkeypatch.setattr(cli_main, "get_default_db_path", lambda: tmp_path / "audit.db")
    monkeypatch.setattr(
        cli_main,
        "verify_once",
        lambda *args, **kwargs: make_result(),
    )
    def persist_result(*args: object, **kwargs: object) -> None:
        """Record that persistence happened before rendering."""

        del args, kwargs
        call_order.append("persist")

    monkeypatch.setattr(cli_main, "_persist_result", persist_result)
    monkeypatch.setattr(
        cli_main,
        "_render_check_result",
        lambda *args, **kwargs: call_order.append("render"),
    )

    exit_code = cli_main.main(["check", "914778271"])

    assert exit_code == 0
    assert call_order == ["persist", "render"]


def test_bulk_continues_when_rows_fail_but_errors_are_recoverable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Bulk mode should keep processing rows when per-row outcomes are mixed."""

    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    input_path.write_text("identifier\nbad-id\n914778271\n", encoding="utf-8")

    results = [make_result(status="INVALID"), make_result(status="VALID")]

    class FakeService:
        """Minimal bulk service stub."""

        def verify_identifier(self, *args: object, **kwargs: object) -> VerificationResult:
            """Return the next queued result."""

            del args, kwargs
            return results.pop(0)

        def close(self) -> None:
            """Match the real service cleanup interface."""

    monkeypatch.setattr(cli_main, "get_default_db_path", lambda: tmp_path / "audit.db")
    monkeypatch.setattr("verifyvat_cli.main.VerificationService.from_environment", lambda: FakeService())
    monkeypatch.setattr(cli_main, "_persist_result", lambda *args, **kwargs: None)

    exit_code = cli_main.main(["bulk", str(input_path), "--output", str(output_path), "--json"])
    captured = capsys.readouterr()

    assert exit_code == 1
    summary = json.loads(captured.out)
    assert summary["row_count"] == 2
    assert summary["counts"] == {"INVALID": 1, "VALID": 1}
    assert output_path.is_file()

    with output_path.open("r", encoding="utf-8", newline="") as output_file:
        output_rows = list(csv.DictReader(output_file))

    assert len(output_rows) == 2
    assert output_rows[0]["internal_status"] == "INVALID"
    assert output_rows[1]["internal_status"] == "VALID"


def test_audit_renders_recent_history_and_can_export_csv(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Audit mode should read local history and optionally export the same records."""

    export_path = tmp_path / "exports" / "audit.csv"
    records = [
        {
            "transaction_id": 2,
            "execution_timestamp": "2026-07-22T00:00:00Z",
            "consultation_receipt": "receipt-2",
            "raw_identifier": "NO000000002",
            "normalized_identifier": "NO000000002",
            "inferred_type": "no_orgnr",
            "internal_status": "VALID",
            "legal_name": "Example Org",
            "address": "Oslo",
            "provider_payload": '{"verification":{"ok":true}}',
        }
    ]

    monkeypatch.setattr(cli_main, "get_default_db_path", lambda: tmp_path / "audit.db")
    monkeypatch.setattr(cli_main, "fetch_recent_audit_records", lambda *args, **kwargs: records)

    exit_code = cli_main.main(["audit", "--limit", "5", "--export-csv", str(export_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert "VerifyVAT Audit History" in captured.out
    assert "Example Org" in captured.out
    assert export_path.is_file()

    with export_path.open("r", encoding="utf-8", newline="") as export_file:
        export_rows = list(csv.DictReader(export_file))

    assert export_rows == [
        {
            "transaction_id": "2",
            "execution_timestamp": "2026-07-22T00:00:00Z",
            "consultation_receipt": "receipt-2",
            "raw_identifier": "NO000000002",
            "normalized_identifier": "NO000000002",
            "inferred_type": "no_orgnr",
            "internal_status": "VALID",
            "legal_name": "Example Org",
            "address": "Oslo",
            "provider_payload": '{"verification":{"ok":true}}',
        }
    ]


def test_audit_limit_must_be_positive(capsys: pytest.CaptureFixture[str]) -> None:
    """Audit mode should reject non-positive limits at parse time."""

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["audit", "--limit", "0"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "greater than zero" in captured.err
