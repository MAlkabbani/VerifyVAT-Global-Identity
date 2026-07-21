# VerifyVAT CLI Skeleton Implementation Plan

## Summary

This plan defines the first implementation phase for the VerifyVAT Python CLI from the current repo state, which contains documentation only and no Python source, packaging, or tests. The goal of this phase is to deliver an installable Python 3.13 CLI skeleton that implements the prompt-mandated `check` and `bulk` commands, persists audit records before final user-facing output, uses the official `verifyvat_sdk`, and preserves the repository's documented security and terminology contract.

This phase intentionally does not implement `audit` or `discovery` behavior yet. Those commands are documented in `docs/README.md`, `docs/DESIGN.md`, and `docs/SPECS.md`, but the direct implementation contract in `docs/PROMPT.md` narrows the initial build to `check` and `bulk`. The docs should be updated during execution to make that phasing explicit so the implementation and documentation align.

## Current State Analysis

### Repo Shape

- The repository currently contains only documentation under `docs/`.
- There are no Python files, no package directory, no `pyproject.toml`, and no dependency lock or requirements file.
- There is no existing `.trae/` workspace structure in the repository yet.

### Source Documents Reviewed

- `docs/PROMPT.md`
- `docs/PRD.md`
- `docs/SPECS.md`
- `docs/ARCHITECTURE.md`
- `docs/DESIGN.md`
- `docs/README.md`
- `docs/research.md`

### Confirmed Build Contract

- Python target is `>=3.13`.
- Dependency management should use `uv`.
- The implementation must use `VerifyVatClient`, `TypeInferrer`, `pick_best_inferred_id_type`, `Verifier.verify_id`, and `Verifier.describe_verification`.
- API credentials must be sourced only from `os.environ.get("VERIFYVAT_API_KEY")`.
- The runtime processing order is fixed:
  1. Validate configuration.
  2. Capture the raw identifier.
  3. Normalize input.
  4. Infer type when needed.
  5. Verify through the SDK.
  6. Map into an internal verification result.
  7. Persist the audit record.
  8. Render output.
- `main.py` owns CLI parsing and rendering.
- `core.py` owns normalization, inference, verification orchestration, and error mapping.
- `db.py` owns SQLite initialization and audit persistence.
- `--json` mode must emit only machine-readable data to stdout.
- Human-readable mode may render structured output and progress feedback.

### Document Tensions Resolved By This Plan

- Database path conflict:
  - `docs/PROMPT.md` requires `~/.verifyvat/audit.db`.
  - `docs/ARCHITECTURE.md` uses `~/.verifyvat/audit_logs.db` as an example.
  - Decision: implement `~/.verifyvat/audit.db` and update the architecture doc during execution to match the prompt.
- Command-surface conflict:
  - `docs/DESIGN.md`, `docs/SPECS.md`, and `docs/README.md` describe `check`, `bulk`, `audit`, and `discovery`.
  - `docs/PROMPT.md` sets the initial implementation bar to `check` and `bulk`.
  - Decision: implement `check` and `bulk` only in phase 1, and update docs to mark `audit` and `discovery` as planned follow-on work.
- Packaging conflict:
  - The docs say to use `uv`, but the repo has no `pyproject.toml`.
  - The current README installation snippet references `requirements.txt`, which does not exist.
  - Decision: standardize on `pyproject.toml` plus `uv sync`, then update docs accordingly.
- Output/UX breadth:
  - The docs allow human-readable output with progressive feedback and strict JSON mode.
  - Decision: include human-readable rendering and JSON-safe suppression behavior in phase 1; keep the renderer simple, deterministic, and secure. Use comments and docstrings to explain non-obvious flow and deferred ideas when warranted.

## Assumptions And Decisions

### Locked Decisions

- Package layout uses `src/verifyvat_cli/` rather than flat root modules.
- The first implementation phase includes only `check` and `bulk`.
- Packaging uses `pyproject.toml` as the source of truth and `uv sync` for setup.
- Code comments should be added for non-obvious logic, decision points, and deferred follow-up items, but remain succinct rather than noisy.
- Deferred concerns and future command work should be recorded in a docs-facing implementation plan during execution.

### Why These Choices

- `src/` packaging provides a clean installable `verifyvat` entry point without fighting import-path issues once tests are added.
- Limiting phase 1 to `check` and `bulk` stays faithful to the direct AI-coder contract in `docs/PROMPT.md` while still meeting the stated acceptance bar.
- `pyproject.toml` plus `uv sync` matches the documented Python 3.13 and `uv` direction better than inventing a one-off `requirements.txt` flow.
- A small number of purposeful comments will help future implementation and review without bloating a security-sensitive CLI codebase.

### Non-Goals For This Phase

- No hosted service behavior, billing flows, or account management.
- No alternate secret input path such as `--api-key`.
- No implementation of `audit` or `discovery` command behavior in this first slice.
- No speculative module explosion beyond what is needed to deliver a maintainable skeleton.

## Proposed Changes

### A1. Establish Packaging And CLI Entry Point

Files to create or update during execution:

- `pyproject.toml`
- `src/verifyvat_cli/__init__.py`
- `src/verifyvat_cli/main.py`

What to do:

- Create a minimal package definition for Python `>=3.13`.
- Add the official SDK dependency and the human-readable renderer dependency required by the chosen UX.
- Register a console script entry point so `verifyvat` resolves to the package CLI.
- Keep `main.py` responsible only for:
  - argument parsing,
  - command dispatch,
  - output-mode routing,
  - exit codes,
  - progress-display suppression when `--json` is enabled.

Why:

- The repo currently has no executable surface.
- The docs promise a terminal command named `verifyvat`.
- Packaging must exist before implementation can be tested through the real CLI path.

How:

- Build the CLI with `argparse` only.
- Define subcommands `check` and `bulk`.
- Support a global or shared `--debug` flag so clean user-facing errors can be upgraded to tracebacks only when explicitly requested.
- Support command-local flags required by the docs:
  - `check`: raw identifier argument, `--country`, `--type`, `--json`
  - `bulk`: input CSV path, `--output`, optional `--delay`, `--json` only if a stable bulk JSON contract is intentionally defined during implementation
- Choose deterministic exit codes for success, invalid identifier, configuration error, and network/runtime error.

### A2. Implement SQLite Audit Storage

Files to create or update during execution:

- `src/verifyvat_cli/db.py`

What to do:

- Initialize `~/.verifyvat/audit.db`.
- Ensure the parent directory exists before opening SQLite.
- Create the `verification_logs` table if it does not exist.
- Add typed helpers to insert one audit record per attempted verification and to query records later without implementing the `audit` command yet.

Why:

- Audit persistence is a first-class product invariant.
- The implementation order in the docs starts with SQLite initialization and audit-write path.
- Rendering must happen only after persistence succeeds for verification commands.

How:

- Use only the standard library `sqlite3`.
- Match the documented schema closely, using SQLite-compatible types:
  - `transaction_id`
  - `execution_timestamp`
  - `consultation_receipt`
  - `raw_user_input`
  - `normalized_identifier`
  - `inferred_format_type`
  - `internal_resolution_state`
  - `verified_legal_entity`
  - `registered_address`
  - `raw_provider_payload`
- Store the provider payload as a JSON string, not as a Python repr.
- Persist only `VALID`, `INVALID`, or `NETWORK_ERROR` in SQLite.
- Keep configuration failures distinguishable in memory and user output without persisting secrets or unsafe traceback content.
- Add clear comments around any place where SQLite's three-state persistence model differs from the in-memory error model.

### A3. Implement Core Verification Flow

Files to create or update during execution:

- `src/verifyvat_cli/core.py`

What to do:

- Implement the domain flow for one verification attempt.
- Normalize user input into a normalized identifier.
- Validate configuration before any network attempt.
- When `--type` is absent, call the SDK inference flow and select the best inferred type.
- Call the verification flow through the SDK and shape the result into a stable internal structure.
- Map handled failures into consistent categories and redact any secret-bearing details.

Why:

- `core.py` is the contract boundary between CLI parsing/rendering and persistence.
- It must preserve the repo's canonical terminology and processing order.
- This layer is where correctness, safety, and audit ordering are easiest to enforce.

How:

- Define typed result structures in `core.py` using standard-library dataclasses or similarly narrow typed structures so `main.py` and `db.py` exchange explicit data instead of ad hoc dictionaries.
- Read `VERIFYVAT_API_KEY` only in the SDK integration path inside `core.py`.
- Instantiate `VerifyVatClient` with the environment-backed key and explicit timeout configuration if the SDK supports it directly; otherwise centralize timeout-related behavior at the closest supported call boundary and document the limitation in code comments.
- Use `TypeInferrer.infer_id_type` with the normalized identifier and optional country hint.
- Use `pick_best_inferred_id_type` to produce the inferred type.
- Use `Verifier.verify_id` and `Verifier.describe_verification`.
- Preserve the distinction between:
  - raw identifier,
  - normalized identifier,
  - inferred type,
  - verification result,
  - audit metadata,
  - provider payload.
- Handle `None` values for legal name and address gracefully.
- Catch SDK-specific exceptions, timeouts, transport failures, and JSON parsing issues and translate them into a safe result model.
- Return structured data that can be rendered directly in both human-readable and JSON modes.

### A4. Implement Human-Readable And JSON Rendering

Files to create or update during execution:

- `src/verifyvat_cli/main.py`

What to do:

- Render deterministic human-readable output for single verification and bulk summaries.
- Render strict machine-readable JSON for commands that opt into `--json`.
- Suppress spinners, tables, colors, and progress text from stdout when JSON mode is enabled.

Why:

- The docs treat JSON mode as a first-class integration contract.
- Human-readable mode must remain concise but operationally useful.
- Output safety is part of the security baseline.

How:

- In human-readable `check` mode, display:
  - final status,
  - supplied or inferred type,
  - legal name when available,
  - address when available,
  - consultation receipt when available,
  - concise diagnostics for invalid or network cases.
- In JSON mode, emit exactly one result object to stdout and redirect any warnings or progress noise to stderr or suppress it entirely.
- Keep secret-bearing values out of all render paths.
- Use concise code comments at the JSON/human-readable branch points to make the output contract obvious to future maintainers.

### A5. Implement Bulk CSV Processing

Files to create or update during execution:

- `src/verifyvat_cli/main.py`
- `src/verifyvat_cli/core.py`

What to do:

- Read an input CSV row by row.
- Extract one raw identifier per row from a clearly documented input contract defined during execution.
- Run the same verification path used by `check`.
- Write an enriched CSV output file with both original and derived columns.
- Persist an audit record for every attempted row.
- Continue across recoverable row-level failures and summarize results at the end.

Why:

- Bulk processing is a mandatory acceptance criterion.
- Reusing the same verification pipeline reduces drift between single and bulk behavior.
- Row-level persistence ensures audit completeness even when the batch has mixed outcomes.

How:

- Define and document a minimal CSV contract during implementation:
  - required identifier column name,
  - optional country/type columns if supported in phase 1,
  - enriched output columns.
- Fail early for unreadable input files, missing required columns, or unwritable output destinations.
- Treat per-row invalid identifiers and network errors as recoverable row outcomes when possible.
- If `--delay` is implemented in phase 1, apply it only between rows and document its purpose clearly.
- Decide during implementation whether bulk `--json` is omitted in phase 1 or implemented with a stable summary/result schema; do not add a half-specified JSON shape.

### A6. Align Docs With The Chosen First Phase

Files to create or update during execution:

- `docs/README.md`
- `docs/ARCHITECTURE.md`
- `docs/DESIGN.md`
- `docs/SPECS.md`
- `docs/PRD.md` only if wording changes are required for phasing clarity
- `docs/IMPLEMENTATION_PLAN.md` as the future-facing copy of this plan

What to do:

- Update docs so the implemented skeleton and the written contract say the same thing.
- Add a permanent implementation-plan document under `docs/` for future reference, since this planning phase is currently limited to the internal plan file.

Why:

- The user explicitly asked for a docs-resident implementation plan.
- Several docs currently describe a broader command surface or slightly conflicting runtime details.
- The implementation phase should not begin until the docs reflect the intended first shipped state.

How:

- Update installation guidance from `requirements.txt` to `pyproject.toml` plus `uv sync`.
- Clarify that phase 1 delivers `check` and `bulk`, while `audit` and `discovery` remain documented follow-on slices unless the docs are later expanded again.
- Standardize the SQLite path to `~/.verifyvat/audit.db`.
- Keep canonical terminology unchanged.
- Record the rationale for those choices in the new `docs/IMPLEMENTATION_PLAN.md`, including brief comments on why the narrower command scope is intentional.

### A7. Add Focused Tests

Files to create or update during execution:

- `tests/test_db.py`
- `tests/test_core.py`
- `tests/test_main.py`

What to do:

- Add high-signal tests around the invariants most likely to regress.

Why:

- The repo currently has no validation harness.
- The logic spans configuration handling, persistence ordering, output contracts, and row-by-row error isolation.

How:

- Test `db.py` schema initialization and audit insertion using temporary filesystem paths.
- Test `core.py` normalization, inference selection, error mapping, and result shaping with SDK calls mocked at the boundary.
- Test `main.py` argument parsing and JSON-mode stdout discipline.
- Add at least one test proving that rendering occurs only after the audit-write path succeeds, using mocks/spies around persistence and renderer boundaries.
- Add at least one bulk-path test that verifies recoverable row failures do not abort the whole batch.

## Logical Order Checklist

### Phase B1. Packaging And Docs Baseline

- Create `pyproject.toml`.
- Create `src/verifyvat_cli/` package scaffold.
- Add console entry point for `verifyvat`.
- Add or update docs to explain `uv sync`.
- Add `docs/IMPLEMENTATION_PLAN.md` as the durable, user-facing implementation roadmap.

### Phase B2. Storage First

- Create `db.py`.
- Implement SQLite path creation and schema initialization.
- Implement audit insert helper.
- Verify local audit file creation at `~/.verifyvat/audit.db`.

### Phase B3. Core Verification Path

- Create `core.py`.
- Implement environment validation and safe config errors.
- Implement input normalization.
- Implement inference flow.
- Implement verification flow.
- Implement safe error mapping and provider-payload serialization.

### Phase B4. Single-Check CLI

- Create `main.py` CLI parser and dispatcher.
- Implement `check` subcommand.
- Implement human-readable renderer.
- Implement JSON renderer with stdout-only machine output.
- Verify audit-before-render ordering.

### Phase B5. Bulk CLI

- Implement CSV input parsing and output writing.
- Reuse core verification path per row.
- Persist one audit record per row.
- Add recoverable row-failure handling and end-of-run summary.

### Phase B6. Verification And Polish

- Add focused tests.
- Run diagnostics on edited Python files.
- Verify no secrets are printed or persisted.
- Verify clean non-traceback failures by default.
- Verify docs and code reference the same command scope, setup steps, database path, and terminology.

## Verification Steps

### Static And Structural Verification

- Run language diagnostics on all edited Python files.
- Verify imports, entry points, and package metadata resolve cleanly.
- Confirm doc examples and command help text use the same flag names and terminology.

### Functional Verification

- Install the project with `uv sync`.
- Run `verifyvat check <id> --type <format>` with mocked SDK coverage in tests.
- Run `verifyvat check <id> --country <ISO>` with inference mocked in tests.
- Run `verifyvat check ... --json` and confirm stdout contains only machine-readable JSON.
- Run `verifyvat bulk <input.csv> --output <output.csv>` on a controlled fixture and confirm enriched output plus per-row audit persistence.

### Persistence Verification

- Confirm the SQLite database is created at `~/.verifyvat/audit.db`.
- Confirm one audit record exists for each attempted verification, including handled invalid and network-failure cases.
- Confirm API keys, auth headers, and other secrets are not written to SQLite.

### Security Verification

- Confirm there is no `--api-key` argument or equivalent secret input path.
- Confirm missing `VERIFYVAT_API_KEY` yields an actionable, non-traceback error by default.
- Confirm debug mode, if enabled, still redacts secrets.
- Confirm JSON mode does not leak spinner text, warnings, or debug noise to stdout.

## Ready-To-Execute Outcome

When this plan is executed, the repository should move from documentation-only to an installable, typed, and test-backed Python CLI skeleton that:

- exposes `verifyvat check` and `verifyvat bulk`,
- uses the official SDK through a narrow `core.py` boundary,
- persists audit records before rendering final user-facing output,
- preserves the repo's canonical terminology and security rules,
- standardizes packaging on `pyproject.toml` plus `uv sync`,
- and leaves `audit` and `discovery` clearly documented as deferred follow-on work rather than silently omitted behavior.
