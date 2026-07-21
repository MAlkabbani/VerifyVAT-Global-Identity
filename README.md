# VerifyVAT Global Identity CLI

An enterprise-grade, terminal-based application designed to validate and enrich global business identifiers (VAT, GST, TRN) by cross-referencing official government registries in real time. Built upon the official VerifyVAT Python SDK, this tool provides instant syntactical checks, registry status verification, and automatic local audit logging to support strict financial compliance for cross-border B2B transactions.

## Strategic Capabilities

- Deterministic Validation: Replaces guesswork with registry-backed proof, validating syntax and checking active status directly against authoritative sources.
- Intelligent Type Inference: Automatically deduces the jurisdiction and format type of raw strings while handling messy user input gracefully.
- Immutable Audit Logging: Preserves timestamps, consultation receipts, and raw provider payloads in an embedded SQLite database for audit readiness.
- Bulk Operations: Processes CSV files containing thousands of legacy IDs and generates enriched datasets with legal names and addresses for ERP ingestion.
- Automation Ready: Emits structured JSON payloads via the `--json` flag for integration into CI/CD pipelines, backend cron jobs, or shell scripts.

## Canonical Terminology

Use the following terms consistently across the repository:

- Raw identifier: The exact identifier string provided by the user or input file.
- Normalized identifier: The sanitized identifier string sent to the SDK or API.
- Inferred type: The best-matched VerifyVAT format type selected by inference.
- Verification result: The structured result returned after a verification attempt.
- Audit record: The local SQLite row written for each verification attempt.
- Provider payload: The raw response body returned by VerifyVAT or an upstream registry.

## Installation and Environment Setup

This application requires Python 3.13 or higher. We recommend using the uv package manager for dependency resolution.

The currently shipped command surface includes `check`, `bulk`, `audit`, and `discovery`.

1. Clone the repository:

   ```bash
   git clone https://github.com/MAlkabbani/VerifyVAT-Global-Identity.git
   cd VerifyVAT-Global-Identity
   ```

2. Create the virtual environment and install dependencies:

   ```bash
   uv sync
   ```

3. Activate the local virtual environment so the repo-local `verifyvat` command is available:

   ```bash
   source .venv/bin/activate
   ```

If `uv` is not installed on your machine, use the standard-library fallback that matches the working local setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

After activation, you can run the CLI as:

```bash
verifyvat --help
```

If you do not want to activate the virtual environment, invoke the local entrypoint directly:

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

## Operational Usage

### Quick Smoke Test

This is the shortest working end-to-end flow for the local CLI:

```bash
cd /path/to/VerifyVAT-Global-Identity
source .venv/bin/activate
export VERIFYVAT_API_KEY="your_secure_api_key_here"
verifyvat check 914778271 --type no_orgnr --json
verifyvat check 914778271 --country NO --json
```

The first command verifies the documented Norwegian organization number directly. The second command exercises the infer-then-verify path using a country hint.

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
verifyvat bulk ./inputs/legacy_suppliers.csv --output ./enriched_suppliers.csv --json
```

Phase 1 bulk mode expects an input CSV with an `identifier` column. Optional `country` and `type` columns may be supplied per row. The output CSV preserves the original columns and appends `normalized_identifier`, `inferred_type`, `internal_status`, `legal_name`, `address`, `consultation_receipt`, `diagnostics`, and `execution_timestamp`.

### Retrieving Audit Evidence

The CLI writes audit records to `~/.verifyvat/audit.db` for every handled `check` result and every attempted bulk row. We shipped `audit` before `discovery` because it closes the local compliance loop using the existing SQLite evidence store without expanding the remote provider surface.

```bash
verifyvat audit --limit 10
```

To export the same selected rows as CSV:

```bash
verifyvat audit --limit 10 --export-csv ./exports/audit-history.csv
```

The `audit` command is intentionally local-only:

- It reads from SQLite and does not call the VerifyVAT API.
- It supports human-readable table output by default.
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
- supports `--json` and writes exactly one machine-readable object to stdout.
- does not write to the local audit database because it is metadata inspection, not a verification event.

The remaining follow-on work after this slice is discovery-depth expansion, such as richer freshness metadata or additional filter surfaces, if the provider contract requires them.

## Licensing and Contributions

This software is released under the MIT License. Contributions, bug reports, and feature requests are welcome.
