"""Focused tests for SQLite audit persistence."""

from __future__ import annotations

import json
import sqlite3

from pathlib import Path

from verifyvat_cli.core import VerificationResult
from verifyvat_cli.db import ensure_database, insert_audit_record


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
