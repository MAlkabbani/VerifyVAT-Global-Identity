# VerifyVAT CLI Implementation Plan

## Related Docs

- Repository overview: [README.md](../README.md)
- Beginner onboarding: [GETTING_STARTED_GUIDE.md](./GETTING_STARTED_GUIDE.md)
- Follow-on work: [REFINEMENT_ROADMAP.md](./REFINEMENT_ROADMAP.md)
- Product and architecture context: [PRD.md](./PRD.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [DESIGN.md](./DESIGN.md), [SPECS.md](./SPECS.md)

## Purpose

This document captures the approved phase-1 implementation choices for the VerifyVAT Python CLI so the codebase, product docs, and future work remain aligned.

## Phase-1 Scope

The currently shipped implementation phase includes the Python CLI skeleton for:

- `verifyvat check`
- `verifyvat bulk`
- `verifyvat audit`
- `verifyvat discovery`

The broader product surface now centers on deepening the existing commands rather than adding another top-level slice.

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
- Shipping `audit` immediately after `check` and `bulk` closes the local compliance loop before expanding into remote metadata discovery.
- Shipping `discovery` with both sections by default keeps the first metadata slice practical while still allowing narrow `--formats` and `--sources` views.
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

- Expand discovery depth if the provider later exposes richer freshness metadata or if the team wants more filter surfaces.
- Add any future export or caching options only if the command contract requires them.
