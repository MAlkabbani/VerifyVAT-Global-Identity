"""Focused tests for SQLite audit persistence."""

from __future__ import annotations

import json
import sqlite3

from pathlib import Path

from verifyvat_cli.core import VerificationResult
from verifyvat_cli.db import ensure_database, fetch_recent_audit_records, insert_audit_record


def test_ensure_database_and_insert_audit_record(tmp_path: Path) -> None:
    """The database schema should be created and accept one audit insert."""

    db_path = tmp_path / "audit.db"
    ensure_database(db_path)

    result = VerificationResult(
        raw_identifier="NO914778271",
        normalized_identifier="NO914778271",
        inferred_type="no_orgnr",
        status="VALID",
        persisted_status="VALID",
        execution_timestamp="2026-07-21T00:00:00Z",
        consultation_receipt="receipt-123",
        legal_name="Example Org",
        address="Oslo",
        diagnostics=["confirmed"],
        provider_payload={"verification": {"ok": True}},
    )

    row_id = insert_audit_record(result, db_path)

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                transaction_id,
                raw_user_input,
                normalized_identifier,
                inferred_format_type,
                internal_resolution_state,
                raw_provider_payload
            FROM verification_logs
            WHERE transaction_id = ?
            """,
            (row_id,),
        ).fetchone()

    assert row is not None
    assert row[1] == "NO914778271"
    assert row[2] == "NO914778271"
    assert row[3] == "no_orgnr"
    assert row[4] == "VALID"
    assert json.loads(row[5]) == {"verification": {"ok": True}}


def test_fetch_recent_audit_records_returns_canonical_keys_and_limit(tmp_path: Path) -> None:
    """Recent audit reads should expose the CLI field names in descending order."""

    db_path = tmp_path / "audit.db"
    ensure_database(db_path)

    first_result = VerificationResult(
        raw_identifier="NO000000001",
        normalized_identifier="NO000000001",
        inferred_type="no_vat",
        status="INVALID",
        persisted_status="INVALID",
        execution_timestamp="2026-07-21T00:00:00Z",
        consultation_receipt=None,
        legal_name=None,
        address=None,
        diagnostics=["missing"],
        provider_payload={"verification": {"ok": False}},
    )
    second_result = VerificationResult(
        raw_identifier="NO000000002",
        normalized_identifier="NO000000002",
        inferred_type="no_orgnr",
        status="VALID",
        persisted_status="VALID",
        execution_timestamp="2026-07-22T00:00:00Z",
        consultation_receipt="receipt-2",
        legal_name="Example Org",
        address="Oslo",
        diagnostics=["confirmed"],
        provider_payload={"verification": {"ok": True}},
    )

    insert_audit_record(first_result, db_path)
    insert_audit_record(second_result, db_path)

    records = fetch_recent_audit_records(limit=1, db_path=db_path)

    assert len(records) == 1
    assert records[0]["raw_identifier"] == "NO000000002"
    assert records[0]["normalized_identifier"] == "NO000000002"
    assert records[0]["inferred_type"] == "no_orgnr"
    assert records[0]["internal_status"] == "VALID"
    assert records[0]["legal_name"] == "Example Org"
    assert json.loads(str(records[0]["provider_payload"])) == {"verification": {"ok": True}}
