"""Focused tests for CLI routing and output discipline."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest
import verifyvat_cli.main as cli_main
from verifyvat_cli.core import ConfigError, DiscoveryResult, PersistedStatus, RuntimeStatus, VerificationResult


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
    assert "Recent Audit Records" in captured.out
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


def test_audit_json_returns_machine_readable_records(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Audit JSON mode should emit one stable machine-readable payload."""

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

    exit_code = cli_main.main(["audit", "--limit", "5", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["query"]["limit"] == 5
    assert payload["query"]["status"] is None
    assert payload["query"]["search"] is None
    assert payload["audit_result"]["status"] == "OK"
    assert payload["audit_result"]["record_count"] == 1
    assert payload["records"][0]["transaction_id"] == 2


def test_audit_json_reports_machine_readable_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Audit JSON mode should not print plain-text errors to stdout or stderr."""

    monkeypatch.setattr(cli_main, "get_default_db_path", lambda: tmp_path / "audit.db")

    def raise_db_error(*args: object, **kwargs: object) -> list[dict[str, object]]:
        del args, kwargs
        raise sqlite3.DatabaseError("database is locked")

    monkeypatch.setattr(cli_main, "fetch_recent_audit_records", raise_db_error)

    exit_code = cli_main.main(["audit", "--limit", "5", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 3
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["audit_result"]["status"] == "NETWORK_ERROR"
    assert payload["records"] == []
    assert payload["audit_result"]["diagnostics"] == ["database is locked"]


def test_audit_passes_status_and_search_filters_to_query_layer(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Audit CLI should pass the new filters to the DB layer and report them in JSON."""

    records = [
        {
            "transaction_id": 4,
            "execution_timestamp": "2026-07-23T00:00:00Z",
            "consultation_receipt": "receipt-4",
            "raw_identifier": "NO914778271",
            "normalized_identifier": "914778271",
            "inferred_type": "no_orgnr",
            "internal_status": "VALID",
            "legal_name": "Norsk Hydro ASA",
            "address": "Oslo",
            "provider_payload": '{"verification":{"ok":true}}',
        }
    ]

    monkeypatch.setattr(cli_main, "get_default_db_path", lambda: tmp_path / "audit.db")

    def fake_fetch_recent_audit_records(*args: object, **kwargs: object) -> list[dict[str, object]]:
        assert kwargs == {
            "limit": 5,
            "db_path": tmp_path / "audit.db",
            "status": "VALID",
            "search": "hydro",
        }
        return records

    monkeypatch.setattr(cli_main, "fetch_recent_audit_records", fake_fetch_recent_audit_records)

    exit_code = cli_main.main(["audit", "--limit", "5", "--status", "VALID", "--search", "hydro", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["query"]["status"] == "VALID"
    assert payload["query"]["search"] == "hydro"
    assert payload["audit_result"]["record_count"] == 1


def test_audit_help_mentions_filtering_example(capsys: pytest.CaptureFixture[str]) -> None:
    """Audit help should advertise the new filtering/search workflow."""

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["audit", "--help"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "verifyvat audit --status VALID --search hydro" in captured.out


def test_audit_limit_must_be_positive(capsys: pytest.CaptureFixture[str]) -> None:
    """Audit mode should reject non-positive limits at parse time."""

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["audit", "--limit", "0"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "greater than zero" in captured.err


def test_discovery_json_defaults_to_formats_and_sources(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Discovery JSON mode should emit one machine-readable payload with both sections."""

    class FakeDiscoveryService:
        """Minimal discovery service stub."""

        def discover(self, **kwargs: object) -> DiscoveryResult:
            """Return a stable discovery payload."""

            assert kwargs == {
                "include_formats": True,
                "include_sources": True,
                "country": "NO",
                "region": None,
            }
            return DiscoveryResult(
                execution_timestamp="2026-07-22T00:00:00Z",
                country="NO",
                region=None,
                include_formats=True,
                include_sources=True,
                formats=[{"id": "no_orgnr", "country": "NO", "region": "EMEA", "validation": "registry", "coverage": "full", "name": "Organisasjonsnummer"}],
                sources=[{"id": "no-brreg", "country": "NO", "active": True, "jurisdictions": ["NO"], "coverage": ["full"], "name": "Brreg"}],
            )

        def close(self) -> None:
            """Match the real cleanup interface."""

    monkeypatch.setattr(
        "verifyvat_cli.main.DiscoveryService.from_environment",
        lambda: FakeDiscoveryService(),
    )

    exit_code = cli_main.main(["discovery", "--country", "NO", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["query"]["include_formats"] is True
    assert payload["query"]["include_sources"] is True
    assert payload["formats"][0]["id"] == "no_orgnr"
    assert payload["sources"][0]["id"] == "no-brreg"


def test_discovery_table_can_show_sources_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Discovery table mode should honor section selection flags."""

    class FakeDiscoveryService:
        """Minimal discovery service stub."""

        def discover(self, **kwargs: object) -> DiscoveryResult:
            """Return only source data for the requested slice."""

            assert kwargs == {
                "include_formats": False,
                "include_sources": True,
                "country": None,
                "region": "EMEA",
            }
            return DiscoveryResult(
                execution_timestamp="2026-07-22T00:00:00Z",
                country=None,
                region="EMEA",
                include_formats=False,
                include_sources=True,
                formats=[],
                sources=[{"id": "no-brreg", "country": "NO", "active": True, "jurisdictions": ["NO"], "coverage": ["full"], "name": "Brreg"}],
            )

        def close(self) -> None:
            """Match the real cleanup interface."""

    monkeypatch.setattr(
        "verifyvat_cli.main.DiscoveryService.from_environment",
        lambda: FakeDiscoveryService(),
    )

    exit_code = cli_main.main(["discovery", "--sources", "--region", "EMEA"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "VerifyVAT Discovery" in captured.out
    assert "Registry Sources" in captured.out
    assert "Supported Formats" not in captured.out
    assert captured.err == ""


def test_discovery_json_reports_config_error_when_api_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Discovery JSON mode should return a machine-readable config error payload."""

    def raise_config_error() -> None:
        raise ConfigError("Missing VERIFYVAT_API_KEY. Export the environment variable and retry.")

    monkeypatch.setattr("verifyvat_cli.main.DiscoveryService.from_environment", raise_config_error)

    exit_code = cli_main.main(["discovery", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["discovery_result"]["status"] == "CONFIG_ERROR"
    assert "VERIFYVAT_API_KEY" in payload["discovery_result"]["diagnostics"][0]


def test_main_returns_invalid_exit_code_for_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """User interruption should not be classified as a network failure."""

    def raise_keyboard_interrupt(*args: object, **kwargs: object) -> VerificationResult:
        del args, kwargs
        raise KeyboardInterrupt

    monkeypatch.setattr(cli_main, "verify_once", raise_keyboard_interrupt)

    exit_code = cli_main.main(["check", "914778271"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Interrupted by user." in captured.err


def test_main_returns_config_exit_code_for_uncaught_config_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Top-level ConfigError fallback should stay distinct from network failures."""

    def raise_config_error(*args: object, **kwargs: object) -> VerificationResult:
        del args, kwargs
        raise ConfigError("Missing VERIFYVAT_API_KEY. Export the environment variable and retry.")

    monkeypatch.setattr(cli_main, "verify_once", raise_config_error)

    exit_code = cli_main.main(["check", "914778271"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "VERIFYVAT_API_KEY" in captured.err


def test_root_help_includes_examples(capsys: pytest.CaptureFixture[str]) -> None:
    """The root parser help should guide first-run usage with concrete examples."""

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["--help"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "Verify global business identifiers" in captured.out
    assert "verifyvat check 914778271 --type no_orgnr --json" in captured.out
    assert "verifyvat discovery --country NO --json" in captured.out


def test_discovery_help_explains_default_behavior(capsys: pytest.CaptureFixture[str]) -> None:
    """Discovery help should explain that the command shows both sections by default."""

    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["discovery", "--help"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "Defaults to showing both sections" in captured.out
    assert "verifyvat discovery --formats --country NO" in captured.out
