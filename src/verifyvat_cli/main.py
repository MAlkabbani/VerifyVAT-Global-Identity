"""CLI entry point and rendering for the VerifyVAT CLI."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from verifyvat_cli.core import (
    ConfigError,
    VerificationResult,
    VerificationService,
    verify_once,
)
from verifyvat_cli.db import ensure_database, get_default_db_path, insert_audit_record

SUCCESS_EXIT_CODE = 0
INVALID_EXIT_CODE = 1
CONFIG_EXIT_CODE = 2
NETWORK_EXIT_CODE = 3

CHECK_HUMAN_STATUS_LABELS = {
    "VALID": "[green]VALID[/green]",
    "INVALID": "[red]INVALID[/red]",
    "NETWORK_ERROR": "[yellow]NETWORK_ERROR[/yellow]",
    "CONFIG_ERROR": "[yellow]CONFIG_ERROR[/yellow]",
}

BULK_REQUIRED_COLUMNS = {"identifier"}
BULK_OUTPUT_COLUMNS = [
    "normalized_identifier",
    "inferred_type",
    "internal_status",
    "legal_name",
    "address",
    "consultation_receipt",
    "diagnostics",
    "execution_timestamp",
]


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level CLI parser."""

    parser = argparse.ArgumentParser(prog="verifyvat")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug tracebacks for unexpected failures.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Verify one raw identifier.")
    check_parser.add_argument("identifier", help="Raw identifier to verify.")
    check_parser.add_argument("--country", help="Optional ISO country hint.")
    check_parser.add_argument("--type", dest="explicit_type", help="Known exact identifier type.")
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="Write only machine-readable JSON to stdout.",
    )
    check_parser.set_defaults(handler=handle_check)

    bulk_parser = subparsers.add_parser("bulk", help="Verify identifiers from a CSV file.")
    bulk_parser.add_argument("input_file", help="Path to the input CSV file.")
    bulk_parser.add_argument("--output", required=True, help="Path to the enriched output CSV file.")
    bulk_parser.add_argument(
        "--delay",
        type=_non_negative_float,
        default=0.0,
        help="Optional delay in seconds between row verifications.",
    )
    bulk_parser.add_argument(
        "--json",
        action="store_true",
        help="Write only a machine-readable bulk summary to stdout.",
    )
    bulk_parser.set_defaults(handler=handle_bulk)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the VerifyVAT CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.handler(args))
    except KeyboardInterrupt:
        _print_error("Interrupted by user.")
        return NETWORK_EXIT_CODE
    except Exception as exc:
        if args.debug:
            traceback.print_exc(file=sys.stderr)
        else:
            _print_error(_sanitize_cli_error(str(exc)))
        return NETWORK_EXIT_CODE


def handle_check(args: argparse.Namespace) -> int:
    """Execute the single-identifier verification flow."""

    stdout_console = Console()
    stderr_console = Console(stderr=True)
    db_path = get_default_db_path()

    if args.json:
        result = verify_once(
            args.identifier,
            country=args.country,
            explicit_type=args.explicit_type,
        )
        persistence_error = _persist_result(result, db_path)
        if persistence_error is not None:
            _emit_json(
                _build_runtime_error_payload(
                    message=persistence_error,
                    db_path=db_path,
                )
            )
            return NETWORK_EXIT_CODE

        _emit_json(result.to_json_dict(audit_db_path=str(db_path)))
        return _status_to_exit_code(result.status)

    with stderr_console.status("Verifying identifier..."):
        result = verify_once(
            args.identifier,
            country=args.country,
            explicit_type=args.explicit_type,
        )
        persistence_error = _persist_result(result, db_path)

    if persistence_error is not None:
        _print_error(persistence_error)
        return NETWORK_EXIT_CODE

    _render_check_result(result, stdout_console)
    return _status_to_exit_code(result.status)


def handle_bulk(args: argparse.Namespace) -> int:
    """Execute bulk verification over an input CSV file."""

    input_path = Path(args.input_file).expanduser()
    output_path = Path(args.output).expanduser()
    db_path = get_default_db_path()
    stdout_console = Console()
    stderr_console = Console(stderr=True)

    try:
        fieldnames, rows = _load_bulk_rows(input_path)
    except (OSError, ValueError) as exc:
        if args.json:
            _emit_json(
                _build_runtime_error_payload(
                    message=str(exc),
                    db_path=db_path,
                )
            )
        else:
            _print_error(str(exc))
        return CONFIG_EXIT_CODE

    try:
        service = VerificationService.from_environment()
    except ConfigError as exc:
        if args.json:
            _emit_json(
                _build_runtime_error_payload(
                    message=str(exc),
                    db_path=db_path,
                )
            )
        else:
            _print_error(str(exc))
        return CONFIG_EXIT_CODE

    output_path.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()

    try:
        if args.json:
            summary = _run_bulk(
                input_path=input_path,
                fieldnames=fieldnames,
                rows=rows,
                output_path=output_path,
                db_path=db_path,
                delay_seconds=args.delay,
                service=service,
                show_status=False,
                status_console=stderr_console,
            )
            _emit_json(summary)
            return int(summary["exit_code"])

        with stderr_console.status(f"Processing {input_path.name}..."):
            summary = _run_bulk(
                input_path=input_path,
                fieldnames=fieldnames,
                rows=rows,
                output_path=output_path,
                db_path=db_path,
                delay_seconds=args.delay,
                service=service,
                show_status=True,
                status_console=stderr_console,
            )

        counts.update(summary["counts"])
        _render_bulk_summary(
            input_path=input_path,
            output_path=output_path,
            counts=counts,
            console=stdout_console,
        )
        return int(summary["exit_code"])
    except (OSError, sqlite3.DatabaseError) as exc:
        if args.json:
            _emit_json(
                _build_runtime_error_payload(
                    message=str(exc),
                    db_path=db_path,
                )
            )
        else:
            _print_error(str(exc))
        return NETWORK_EXIT_CODE
    finally:
        service.close()


def _run_bulk(
    *,
    input_path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    output_path: Path,
    db_path: Path,
    delay_seconds: float,
    service: VerificationService,
    show_status: bool,
    status_console: Console,
) -> dict[str, Any]:
    """Process bulk verification and return a stable summary payload."""

    counts: Counter[str] = Counter()
    output_fieldnames = fieldnames + [name for name in BULK_OUTPUT_COLUMNS if name not in fieldnames]

    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=output_fieldnames)
        writer.writeheader()

        for row in rows:
            result = service.verify_identifier(
                row.get("identifier", ""),
                country=row.get("country"),
                explicit_type=row.get("type"),
            )
            persistence_error = _persist_result(result, db_path)
            if persistence_error is not None:
                raise sqlite3.DatabaseError(persistence_error)

            counts.update([result.status])
            writer.writerow(_build_bulk_output_row(row, result))

            if show_status and delay_seconds > 0:
                status_console.print(
                    f"Queued delay of {delay_seconds:.2f}s after {result.raw_identifier!r}.",
                    style="dim",
                )
            if delay_seconds > 0:
                time.sleep(delay_seconds)

    exit_code = _bulk_counts_to_exit_code(counts)
    return {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "row_count": sum(counts.values()),
        "counts": dict(counts),
        "exit_code": exit_code,
        "audit_database": str(db_path),
    }


def _load_bulk_rows(input_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Load the input CSV and validate the minimum contract."""

    if not input_path.is_file():
        raise OSError(f"Input CSV not found: {input_path}")

    with input_path.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError("Input CSV must include a header row.")

        missing_columns = BULK_REQUIRED_COLUMNS.difference(reader.fieldnames)
        if missing_columns:
            missing_list = ", ".join(sorted(missing_columns))
            raise ValueError(f"Input CSV is missing required columns: {missing_list}")

        rows = [dict(row) for row in reader]

    return list(reader.fieldnames), rows


def _persist_result(result: VerificationResult, db_path: Path) -> str | None:
    """Persist a verification result before any user-facing output is rendered."""

    try:
        ensure_database(db_path)
        insert_audit_record(result, db_path)
        return None
    except sqlite3.DatabaseError as exc:
        return f"Failed to persist the audit record: {exc}"


def _render_check_result(result: VerificationResult, console: Console) -> None:
    """Render a human-readable verification result."""

    table = Table(title="VerifyVAT Check Result")
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    table.add_row("Status", CHECK_HUMAN_STATUS_LABELS[result.status])
    table.add_row("Raw Identifier", result.raw_identifier)
    table.add_row("Normalized Identifier", result.normalized_identifier or "(empty)")
    table.add_row("Inferred Type", result.inferred_type or "(none)")
    table.add_row("Legal Name", result.legal_name or "(not available)")
    table.add_row("Address", result.address or "(not available)")
    table.add_row("Consultation Receipt", result.consultation_receipt or "(not available)")
    table.add_row("Diagnostics", "; ".join(result.diagnostics) or "(none)")
    console.print(table)


def _render_bulk_summary(
    *,
    input_path: Path,
    output_path: Path,
    counts: Counter[str],
    console: Console,
) -> None:
    """Render a concise human-readable bulk summary."""

    table = Table(title="VerifyVAT Bulk Summary")
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    table.add_row("Input File", str(input_path))
    table.add_row("Output File", str(output_path))
    table.add_row("VALID", str(counts.get("VALID", 0)))
    table.add_row("INVALID", str(counts.get("INVALID", 0)))
    table.add_row("NETWORK_ERROR", str(counts.get("NETWORK_ERROR", 0)))
    table.add_row("CONFIG_ERROR", str(counts.get("CONFIG_ERROR", 0)))
    table.add_row("Total Rows", str(sum(counts.values())))
    console.print(table)


def _build_bulk_output_row(row: dict[str, str], result: VerificationResult) -> dict[str, str]:
    """Append the enriched verification fields to one bulk output row."""

    enriched_row = dict(row)
    enriched_row.update(
        {
            "normalized_identifier": result.normalized_identifier,
            "inferred_type": result.inferred_type or "",
            "internal_status": result.status,
            "legal_name": result.legal_name or "",
            "address": result.address or "",
            "consultation_receipt": result.consultation_receipt or "",
            "diagnostics": "; ".join(result.diagnostics),
            "execution_timestamp": result.execution_timestamp,
        }
    )
    return enriched_row


def _build_runtime_error_payload(*, message: str, db_path: Path) -> dict[str, Any]:
    """Build a machine-readable error payload for JSON mode."""

    return {
        "verification_result": {
            "status": "NETWORK_ERROR",
            "diagnostics": [message],
        },
        "audit_record": {
            "database_path": str(db_path),
        },
    }


def _emit_json(payload: dict[str, Any]) -> None:
    """Write one machine-readable JSON object to stdout."""

    print(json.dumps(payload, default=str, sort_keys=True))


def _status_to_exit_code(status: str) -> int:
    """Map one runtime status to a deterministic exit code."""

    if status == "VALID":
        return SUCCESS_EXIT_CODE
    if status == "INVALID":
        return INVALID_EXIT_CODE
    if status == "CONFIG_ERROR":
        return CONFIG_EXIT_CODE
    return NETWORK_EXIT_CODE


def _bulk_counts_to_exit_code(counts: Counter[str]) -> int:
    """Pick the most severe exit code from a mixed bulk batch."""

    if counts.get("NETWORK_ERROR", 0) > 0:
        return NETWORK_EXIT_CODE
    if counts.get("CONFIG_ERROR", 0) > 0:
        return CONFIG_EXIT_CODE
    if counts.get("INVALID", 0) > 0:
        return INVALID_EXIT_CODE
    return SUCCESS_EXIT_CODE


def _sanitize_cli_error(message: str) -> str:
    """Return a concise CLI-safe error message."""

    return message.strip() or "An unexpected runtime error occurred."


def _print_error(message: str) -> None:
    """Write a human-readable error line to stderr."""

    print(message, file=sys.stderr)


def _non_negative_float(value: str) -> float:
    """Parse a non-negative float for the `--delay` argument."""

    parsed_value = float(value)
    if parsed_value < 0:
        raise argparse.ArgumentTypeError("--delay must be non-negative.")
    return parsed_value


if __name__ == "__main__":
    raise SystemExit(main())
