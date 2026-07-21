"""SQLite persistence helpers for VerifyVAT audit records."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from verifyvat_cli.core import VerificationResult

DEFAULT_AUDIT_DIR = Path.home() / ".verifyvat"
DEFAULT_AUDIT_DB_PATH = DEFAULT_AUDIT_DIR / "audit.db"

CREATE_VERIFICATION_LOGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS verification_logs (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_timestamp TEXT NOT NULL,
    consultation_receipt TEXT,
    raw_user_input TEXT NOT NULL,
    normalized_identifier TEXT NOT NULL,
    inferred_format_type TEXT,
    internal_resolution_state TEXT NOT NULL CHECK (
        internal_resolution_state IN ('VALID', 'INVALID', 'NETWORK_ERROR')
    ),
    verified_legal_entity TEXT,
    registered_address TEXT,
    raw_provider_payload TEXT NOT NULL
)
"""


def get_default_db_path() -> Path:
    """Return the default audit-database location."""

    return DEFAULT_AUDIT_DB_PATH


def ensure_database(db_path: Path | None = None) -> Path:
    """Create the parent directory and schema for the audit database."""

    resolved_path = (db_path or DEFAULT_AUDIT_DB_PATH).expanduser()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(resolved_path) as connection:
        connection.execute(CREATE_VERIFICATION_LOGS_TABLE_SQL)
        connection.commit()

    return resolved_path


def insert_audit_record(result: VerificationResult, db_path: Path | None = None) -> int:
    """Insert one immutable audit record and return its transaction id."""

    resolved_path = ensure_database(db_path)

    with _connect(resolved_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO verification_logs (
                execution_timestamp,
                consultation_receipt,
                raw_user_input,
                normalized_identifier,
                inferred_format_type,
                internal_resolution_state,
                verified_legal_entity,
                registered_address,
                raw_provider_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.execution_timestamp,
                result.consultation_receipt,
                result.raw_identifier,
                result.normalized_identifier,
                result.inferred_type,
                result.persisted_status,
                result.legal_name,
                result.address,
                result.provider_payload_json(),
            ),
        )
        connection.commit()

    row_id = cursor.lastrowid
    if row_id is None:
        raise sqlite3.DatabaseError("Failed to determine the inserted audit-record id.")
    return int(row_id)


def fetch_recent_audit_records(limit: int = 10, db_path: Path | None = None) -> list[dict[str, object]]:
    """Read recent audit records for future `audit` command work."""

    resolved_path = ensure_database(db_path)

    with _connect(resolved_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                transaction_id,
                execution_timestamp,
                consultation_receipt,
                raw_user_input,
                normalized_identifier,
                inferred_format_type,
                internal_resolution_state,
                verified_legal_entity,
                registered_address,
                raw_provider_payload
            FROM verification_logs
            ORDER BY transaction_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with a deterministic row factory."""

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection
