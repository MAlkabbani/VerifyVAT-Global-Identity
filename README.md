# VerifyVAT Global Identity CLI

```text
+--------------------------------------------------+
| VerifyVAT Global Identity CLI                    |
| Independent open-source CLI for VerifyVAT SDK    |
+--------------------------------------------------+
```

VerifyVAT CLI is a Python command-line application for validating and enriching business identifiers through the official VerifyVAT SDK. It supports single checks, CSV bulk processing, local audit evidence, and metadata discovery for supported formats and registries.

This README uses the upstream product name only to describe SDK compatibility and intended integration. It does not imply endorsement, partnership, or official branding by the upstream provider.

<p>
  <a href="https://buymeacoffee.com/webeworx" target="_blank" rel="noopener noreferrer">
    <img
      src="https://img.shields.io/badge/Support%20This%20Project-Coffee%20Fund-f59e0b?style=for-the-badge&labelColor=111827&color=fbbf24"
      alt="Support this project"
    />
  </a>
</p>

## Start Here

If you are new to the repository:

- Read the beginner-friendly guide: [GETTING_STARTED_GUIDE.md](docs/GETTING_STARTED_GUIDE.md)
- Review the shipped implementation scope: [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)
- Review the next refinement phases: [REFINEMENT_ROADMAP.md](docs/REFINEMENT_ROADMAP.md)

## What It Does

- Deterministic validation: checks syntax and registry-backed status for supported identifiers
- Type inference: infers the best VerifyVAT type from a raw identifier plus a country hint
- Local audit logging: writes verification evidence to SQLite for review and export
- Bulk processing: reads identifiers from CSV and writes enriched output CSVs
- Discovery: inspects supported identifier formats and source registries
- Automation-safe JSON: keeps `--json` output machine-readable on stdout

## Command Surface

The currently shipped commands are:

- `verifyvat check`
- `verifyvat bulk`
- `verifyvat audit`
- `verifyvat discovery`

The root parser also exposes `verifyvat --version` so operators can confirm the installed release quickly.

## Canonical Terminology

Use the following terms consistently across the repository:

- Raw identifier: The exact identifier string provided by the user or input file.
- Normalized identifier: The sanitized identifier string sent to the SDK or API.
- Inferred type: The best-matched VerifyVAT format type selected by inference.
- Verification result: The structured result returned after a verification attempt.
- Audit record: The local SQLite row written for each verification attempt.
- Provider payload: The raw response body returned by VerifyVAT or an upstream registry.

## Installation and Environment Setup

This repository requires Python `3.13` or higher. We recommend `uv`, but a standard `venv` and `pip` path is also fully supported.

1. Clone the repository:

```bash
git clone https://github.com/MAlkabbani/VerifyVAT-Global-Identity.git
cd VerifyVAT-Global-Identity
```

2. Preferred setup path:

```bash
uv sync
source .venv/bin/activate
```

3. Fallback setup path when `uv` is not installed:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

4. Confirm the repo-local CLI works:

```bash
verifyvat --help
verifyvat --version
```

If you prefer not to activate the virtual environment, use the local entrypoint directly:

```bash
./.venv/bin/verifyvat --help
```

## Security and Authentication Configuration

The VerifyVAT CLI uses environment-based credential management. Do not hardcode your API key into scripts or pass it as a raw command-line argument.

Obtain your API key from the VerifyVAT dashboard and export it to your operating system environment:

```bash
export VERIFYVAT_API_KEY="your_secure_api_key_here"
```

The official VerifyVAT authentication docs note that the API can accept credentials by header, JSON field, or query parameter. For this CLI, use the SDK with `VERIFYVAT_API_KEY` from the environment so requests authenticate through the recommended header-based flow.

If you accidentally paste or expose a live key in terminal history, screenshots, or chat logs, rotate it immediately before further testing.

## API Security Baseline

- Read the API key only from environment variables or a secret manager.
- Do not support `--api-key` style CLI flags because they leak into shell history and process listings.
- Do not print the API key, auth headers, or secret-bearing payload fragments to stdout, stderr, logs, or SQLite.
- Use HTTPS for all remote calls and fail fast with a clear error if the API key is missing.
- Prefer header-based authentication and do not place secrets in URLs, query strings, or copied example commands.
- Redact secrets from debug output, error reports, and exported diagnostics.

For a fuller onboarding flow, use [GETTING_STARTED_GUIDE.md](docs/GETTING_STARTED_GUIDE.md).

## Operational Usage

### Quick Smoke Test

This is the shortest working end-to-end local smoke test:

```bash
cd /path/to/VerifyVAT-Global-Identity
source .venv/bin/activate
export VERIFYVAT_API_KEY="your_secure_api_key_here"
verifyvat check 914778271 --type no_orgnr --json
verifyvat check 914778271 --country NO --json
verifyvat discovery --country NO --json
```

The first command verifies a documented Norwegian organization number directly. The second command exercises inference. The third confirms the discovery endpoints.

For a repeatable repo-local check flow, use:

```bash
./scripts/smoke_test.sh --offline
./scripts/smoke_test.sh --live
```

The live mode requires `VERIFYVAT_API_KEY`. The offline mode checks the installed CLI, local audit-read behavior, and docs alignment without calling the remote API. The helper prefers the repo-local `.venv` binaries when present and falls back to the active environment's `verifyvat` and `python` executables in CI-style installs.

### Validating a Single Identifier

If the exact jurisdiction is unknown, provide the ID and a geographic hint. The CLI will infer the optimal format and execute the query.

```bash
verifyvat check 914778271 --country NO --json
```

### Validating an Identifier with a Known Format

Bypass the inference engine for faster execution when the format is already known.

```bash
verifyvat check 914778271 --type no_orgnr --json
```

### Validating a Real Company VAT ID

Use one of these two paths:

- If you know the exact VerifyVAT type already, prefer `--type`.
- If you only know the country, use `--country` and let the CLI infer the best type.

Known-type template:

```bash
verifyvat check "<REAL_IDENTIFIER>" --type "<EXACT_VERIFYVAT_TYPE>" --json
```

Inference template:

```bash
verifyvat check "<REAL_IDENTIFIER>" --country "<ISO2_COUNTRY>" --json
```

Important usage note:

- The demo identifier `914778271` is a Norwegian organization number, so its exact type is `no_orgnr`.
- A real VAT number may use a different exact type than the base business-registration identifier.
- For example, the provider payload for the Norwegian demo entity also includes a VAT identifier of type `no_vat`, which is different from `no_orgnr`.
- If your real company test fails with a known type, first confirm you are using the correct identifier family for that jurisdiction and not mixing a VAT ID with a company-registration ID.

What to inspect in the JSON result:

- `verification_result.status`
- `verification_result.legal_name`
- `verification_result.address`
- `normalized_identifier`
- `inferred_type`
- `provider_payload.verification.process.output.outcome`
- `audit_record.execution_timestamp`

### Executing Bulk Validations

Ingest a CSV containing raw identifiers and output an enriched dataset.

```bash
verifyvat bulk ./fixtures/sample_bulk_input.csv --output ./outputs/sample_bulk_output.csv --json
```

Phase 1 bulk mode expects an input CSV with an `identifier` column. Optional `country` and `type` columns may be supplied per row. The output CSV preserves the original columns and appends `normalized_identifier`, `inferred_type`, `internal_status`, `legal_name`, `address`, `consultation_receipt`, `diagnostics`, and `execution_timestamp`.

A sample fixture is included at `./fixtures/sample_bulk_input.csv` so contributors can run a known-good bulk path without first creating their own CSV.

### Retrieving Audit Evidence

The CLI writes audit records to `~/.verifyvat/audit.db` for every handled `check` result and every attempted bulk row. We shipped `audit` before `discovery` because it closes the local compliance loop using the existing SQLite evidence store without expanding the remote provider surface.

```bash
verifyvat audit --limit 10
```

To export the same selected rows as CSV:

```bash
verifyvat audit --limit 10 --export-csv ./exports/audit-history.csv
```

To emit machine-readable audit history:

```bash
verifyvat audit --limit 10 --json
```

To filter the local audit history:

```bash
verifyvat audit --status VALID --search hydro
```

The `audit` command is intentionally local-only:

- It reads from SQLite and does not call the VerifyVAT API.
- It supports human-readable table output by default.
- It supports `--json` for automation-safe audit reads.
- It supports exact `--status` filtering and case-insensitive `--search` across raw identifier, normalized identifier, and legal name.
- It can export the selected rows as CSV for downstream review.

### Inspecting Supported Formats and Sources

The `discovery` command lists supported identifier formats and registry sources through the official SDK discovery endpoints. We shipped both sections by default so operators can inspect the format catalog and the backing registries in one pass, while still allowing narrower views with flags.

Show both supported formats and sources:

```bash
verifyvat discovery
```

Show only formats for one jurisdiction:

```bash
verifyvat discovery --formats --country NO
```

Show only sources for one region:

```bash
verifyvat discovery --sources --region EMEA
```

Emit machine-readable JSON:

```bash
verifyvat discovery --country NO --json
```

The `discovery` command in this slice:

- uses `--formats` and `--sources` to narrow the output, while defaulting to both sections when neither flag is supplied.
- supports `--country` and `--region` filters for a practical first-pass lookup surface.
- exposes richer per-format source coverage and per-source supported-type detail in both table and JSON output.
- supports `--json` and writes exactly one machine-readable object to stdout.
- does not write to the local audit database because it is metadata inspection, not a verification event.
- does not currently expose registry freshness timestamps because that metadata is not present in the current SDK discovery payloads.

## Junior Developer Notes

If you are onboarding to this repository for the first time:

- use the local `.venv` path first instead of assuming a global install
- use `verifyvat --version` to confirm which installed release you are exercising
- use the documented sample before testing a real company identifier
- prefer `--type` when you know the exact VerifyVAT type
- use `--country` when you need inference
- inspect `audit` when you want proof of what was persisted locally

## Repeatable Checks

Use these repository-local helpers when validating changes:

- `./scripts/smoke_test.sh --offline`: runs local-only smoke checks, including `verifyvat --version`, CLI help, audit JSON, and docs alignment; it prefers repo-local `.venv` binaries but falls back to the active environment when needed.
- `./scripts/smoke_test.sh --live`: adds real VerifyVAT API calls and a bulk-fixture pass when `VERIFYVAT_API_KEY` is exported.
- `./scripts/check_docs_alignment.py`: verifies the high-signal docs stay aligned with the shipped command surface and helper workflow.

## Documentation Map

- Beginner onboarding and full usage guide: [GETTING_STARTED_GUIDE.md](docs/GETTING_STARTED_GUIDE.md)
- Shipped implementation contract: [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)
- Next refinement phases: [REFINEMENT_ROADMAP.md](docs/REFINEMENT_ROADMAP.md)
- Product and architecture context: [PRD.md](docs/PRD.md), [ARCHITECTURE.md](docs/ARCHITECTURE.md), [DESIGN.md](docs/DESIGN.md), [SPECS.md](docs/SPECS.md)
- Original implementation prompt and research context: [PROMPT.md](docs/PROMPT.md), [research.md](docs/research.md)

## Licensing and Contributions

This software is released under the GNU Affero General Public License v3.0 or later (`AGPL-3.0-or-later`). See [LICENSE](LICENSE) for the full text.

> For commercial licensing inquiries, please contact support@webeworx.com.

Contributions, bug reports, and feature requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, validation, and submission expectations.
