# VerifyVAT CLI Implementation Plan

## Purpose

This document captures the approved phase-1 implementation choices for the VerifyVAT Python CLI so the codebase, product docs, and future work remain aligned.

## Phase-1 Scope

The first implementation phase ships the Python CLI skeleton for:

- `verifyvat check`
- `verifyvat bulk`

The broader product surface still includes `audit` and `discovery`, but those commands remain follow-on work until their behavior is implemented.

## Locked Choices

- Use Python `>=3.13`.
- Use `pyproject.toml` as the packaging source of truth.
- Use `uv sync` for local setup.
- Use a `src/verifyvat_cli/` package layout.
- Use `argparse` for CLI parsing.
- Use the official `verifyvat_sdk`.
- Read `VERIFYVAT_API_KEY` only from `os.environ.get("VERIFYVAT_API_KEY")`.
- Persist audit evidence to `~/.verifyvat/audit.db`.
- Keep argument parsing and rendering in `main.py`, verification flow in `core.py`, and SQLite logic in `db.py`.

## Why These Choices

- `src/` packaging gives the project a clean installable `verifyvat` command surface.
- `pyproject.toml` plus `uv sync` matches the repository's Python 3.13 and `uv` direction better than an ad hoc `requirements.txt` flow.
- Limiting phase 1 to `check` and `bulk` keeps the implementation faithful to `docs/PROMPT.md` while still meeting the documented acceptance bar.
- Narrow module boundaries keep secret handling, audit writes, and rendering responsibilities explicit.

## Delivery Order

1. Add packaging and console-entry wiring.
2. Implement SQLite initialization and audit inserts.
3. Implement normalization, inference, verification, and error mapping.
4. Implement `check` rendering in human-readable and JSON modes.
5. Implement bulk CSV processing with per-row audit logging.
6. Add focused tests and verification commands.
7. Keep docs synced with the shipped command surface and setup flow.

## Phase-1 CSV Contract

Bulk mode expects:

- required column: `identifier`
- optional columns: `country`, `type`

Bulk mode writes the original columns plus:

- `normalized_identifier`
- `inferred_type`
- `internal_status`
- `legal_name`
- `address`
- `consultation_receipt`
- `diagnostics`
- `execution_timestamp`

## Security Notes

- Do not add an `--api-key` flag or any equivalent secret input path.
- Do not print API keys, auth headers, or secret-bearing request metadata.
- Keep `--json` stdout strictly machine-readable.
- Persist the audit record before rendering final user-facing verification output.
- Fold `CONFIG_ERROR` into the SQLite three-state model only for persistence; keep it distinct in user-facing results.

## Deferred Follow-On Work

- Add the `audit` command for local history reads and export.
- Add the `discovery` command for supported formats and registry/source inspection.
- Expand operational docs once those commands ship.
