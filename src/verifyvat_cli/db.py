"""SQLite persistence helpers for VerifyVAT audit records."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from verifyvat_cli.core import VerificationResult

DEFAULT_AUDIT_DIR = Path.home() / ".verifyvat"
DEFAULT_AUDIT_DB_PATH = DEFAULT_AUDIT_DIR / "audit.db"
AUDIT_EXPORT_COLUMNS = [
    "transaction_id",
    "execution_timestamp",
    "consultation_receipt",
    "raw_identifier",
    "normalized_identifier",
    "inferred_type",
    "internal_status",
    "legal_name",
    "address",
    "provider_payload",
]
AUDIT_FILTERABLE_STATUSES = ("VALID", "INVALID", "NETWORK_ERROR")

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

CREATE_RUNTIME_EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS runtime_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    raw_identifier TEXT NOT NULL,
    normalized_identifier TEXT NOT NULL,
    inferred_type TEXT,
    http_status INTEGER,
    error_code TEXT,
    endpoint TEXT,
    trace_id TEXT
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
        connection.execute(CREATE_RUNTIME_EVENTS_TABLE_SQL)
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


def insert_runtime_event(event: dict[str, object], db_path: Path | None = None) -> int:
    """Insert one runtime event row for operational tracking."""

    resolved_path = ensure_database(db_path)

    with _connect(resolved_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO runtime_events (
                event_timestamp,
                event_type,
                raw_identifier,
                normalized_identifier,
                inferred_type,
                http_status,
                error_code,
                endpoint,
                trace_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.get("event_timestamp"),
                event.get("event_type"),
                event.get("raw_identifier"),
                event.get("normalized_identifier"),
                event.get("inferred_type"),
                event.get("http_status"),
                event.get("error_code"),
                event.get("endpoint"),
                event.get("trace_id"),
            ),
        )
        connection.commit()

    row_id = cursor.lastrowid
    if row_id is None:
        raise sqlite3.DatabaseError("Failed to determine the inserted runtime-event id.")
    return int(row_id)


def fetch_recent_audit_records(
    limit: int = 10,
    db_path: Path | None = None,
    *,
    status: str | None = None,
    search: str | None = None,
) -> list[dict[str, object]]:
    """Read recent audit records using the CLI's canonical field names."""

    resolved_path = ensure_database(db_path)
    where_clauses: list[str] = []
    parameters: list[object] = []

    if status is not None:
        normalized_status = status.strip().upper()
        if normalized_status not in AUDIT_FILTERABLE_STATUSES:
            allowed_statuses = ", ".join(AUDIT_FILTERABLE_STATUSES)
            raise ValueError(f"Unsupported audit status: {status}. Expected one of: {allowed_statuses}")
        where_clauses.append("internal_resolution_state = ?")
        parameters.append(normalized_status)

    if search is not None:
        normalized_search = search.strip().casefold()
        if normalized_search:
            where_clauses.append(
                "("
                "LOWER(raw_user_input) LIKE ? OR "
                "LOWER(normalized_identifier) LIKE ? OR "
                "LOWER(COALESCE(verified_legal_entity, '')) LIKE ?"
                ")"
            )
            search_pattern = f"%{normalized_search}%"
            parameters.extend([search_pattern, search_pattern, search_pattern])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    parameters.append(limit)

    with _connect(resolved_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                transaction_id AS transaction_id,
                execution_timestamp AS execution_timestamp,
                consultation_receipt AS consultation_receipt,
                raw_user_input AS raw_identifier,
                normalized_identifier AS normalized_identifier,
                inferred_format_type AS inferred_type,
                internal_resolution_state AS internal_status,
                verified_legal_entity AS legal_name,
                registered_address AS address,
                raw_provider_payload AS provider_payload
            FROM verification_logs
            {where_sql}
            ORDER BY transaction_id DESC
            LIMIT ?
            """,
            tuple(parameters),
        ).fetchall()

    return [dict(row) for row in rows]


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with a deterministic row factory."""

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection
