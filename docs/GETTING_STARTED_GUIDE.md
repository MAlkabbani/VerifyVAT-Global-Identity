# VerifyVAT CLI Getting Started Guide

## Related Docs

- Start with the repository overview in [README.md](../README.md).
- Review shipped scope in [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md).
- Review follow-on phases in [REFINEMENT_ROADMAP.md](./REFINEMENT_ROADMAP.md).
- Review product and architecture context in [PRD.md](./PRD.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [DESIGN.md](./DESIGN.md), and [SPECS.md](./SPECS.md).

## Who This Guide Is For

This guide is for developers who are new to the repository, new to the VerifyVAT product, or new to command-line Python applications in general. It focuses on the practical path: how to set up the project, how to run it locally, how to understand the main commands, and how to avoid the most common mistakes.

## What This CLI Does

The VerifyVAT CLI verifies global business identifiers through the official VerifyVAT SDK and writes local audit evidence to SQLite.

The main commands are:

- `check`: verify one identifier
- `bulk`: verify many identifiers from a CSV file
- `audit`: review local audit history
- `discovery`: inspect supported identifier formats and source registries

## Core Terms

These terms appear throughout the docs and CLI:

- Raw identifier: the exact string provided by a user or input file
- Normalized identifier: the cleaned string actually sent to VerifyVAT
- Inferred type: the best VerifyVAT type selected when the CLI infers the format
- Verification result: the structured response returned after verification
- Audit record: the local SQLite record written for a verification attempt
- Provider payload: the raw upstream response returned by VerifyVAT

## Before You Start

You need:

- Python `3.13` or higher
- a local checkout of this repository
- a VerifyVAT API key exported as `VERIFYVAT_API_KEY`

Recommended repository path:

```bash
git clone https://github.com/MAlkabbani/VerifyVAT-Global-Identity.git
cd VerifyVAT-Global-Identity
```

## Setup Paths

### Recommended: `uv`

If you already use `uv`, this is the preferred setup path:

```bash
uv sync
source .venv/bin/activate
verifyvat --help
verifyvat --version
```

### Fallback: Standard `venv` and `pip`

If `uv` is not installed, use the fallback that also works with this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
verifyvat --help
verifyvat --version
```

### Direct Local Entrypoint

If you do not want to activate the virtual environment, call the repo-local executable directly:

```bash
./.venv/bin/verifyvat --help
./.venv/bin/verifyvat --version
```

## Authentication

Export your key before running any command that talks to the remote API:

```bash
export VERIFYVAT_API_KEY="your_secure_api_key_here"
```

Important rules:

- do not pass API keys through CLI flags
- do not hardcode API keys in scripts
- rotate a key immediately if it appears in shell history, screenshots, logs, or chat

## Fastest Working Smoke Test

Use the documented Norwegian sample to confirm local setup:

```bash
source .venv/bin/activate
export VERIFYVAT_API_KEY="your_secure_api_key_here"

verifyvat --version
verifyvat check 914778271 --type no_orgnr --json
verifyvat check 914778271 --country NO --json
verifyvat discovery --country NO --json
verifyvat audit --limit 5
```

What these commands prove:

- the first `check` verifies a known identifier type directly
- the second `check` verifies the inference path
- `discovery` confirms the metadata endpoints and JSON mode
- `audit` confirms local SQLite reads

## How To Use Each Command

### 1. `check`

Use `check` when you want to verify one identifier.

Known-type flow:

```bash
verifyvat check 914778271 --type no_orgnr --json
```

Inference flow:

```bash
verifyvat check 914778271 --country NO --json
```

Use `--type` when:

- you already know the exact VerifyVAT type
- you want a more explicit and usually simpler verification path

Use `--country` when:

- you do not know the exact type
- you know the jurisdiction and want the CLI to infer the best type

### 2. `bulk`

Use `bulk` when you want to enrich a CSV of identifiers.

Example:

```bash
verifyvat bulk ./fixtures/sample_bulk_input.csv --output ./outputs/sample_bulk_output.csv
```

Input contract:

- required column: `identifier`
- optional columns: `country`, `type`

Output adds:

- `normalized_identifier`
- `inferred_type`
- `internal_status`
- `legal_name`
- `address`
- `consultation_receipt`
- `diagnostics`
- `execution_timestamp`

Sample fixture:

- `./fixtures/sample_bulk_input.csv` includes one explicit-type row and one inference row for the documented Norwegian sample identifier

### 3. `audit`

Use `audit` to inspect local verification history.

Examples:

```bash
verifyvat audit --limit 10
verifyvat audit --limit 10 --json
verifyvat audit --status VALID --search hydro
verifyvat audit --limit 10 --export-csv ./exports/audit-history.csv
```

Important behavior:

- `audit` reads only from the local SQLite database
- `audit` does not call the remote API
- `audit --json` returns a machine-readable payload with `query`, `audit_result`, and `records`
- `audit --status` filters by exact status and `audit --search` performs case-insensitive contains matching over raw identifier, normalized identifier, and legal name
- `audit` is useful for compliance evidence and support troubleshooting

### 4. `discovery`

Use `discovery` to inspect supported formats and source registries.

Examples:

```bash
verifyvat discovery
verifyvat discovery --formats --country NO
verifyvat discovery --sources --region EMEA
verifyvat discovery --country NO --json
```

Important behavior:

- if you provide neither `--formats` nor `--sources`, the CLI shows both sections
- `discovery` is read-only and does not create audit records
- `--json` writes one machine-readable object to stdout
- discovery now exposes richer per-format source coverage and per-source supported-type detail
- discovery does not currently include freshness timestamps because the current SDK discovery payloads do not expose them

## Real VAT ID Testing

When testing a real company identifier:

1. decide whether you have a VAT ID or a company-registration ID
2. if you know the exact VerifyVAT type, prefer `--type`
3. if you only know the country, use `--country`

Templates:

```bash
verifyvat check "<REAL_IDENTIFIER>" --type "<EXACT_VERIFYVAT_TYPE>" --json
verifyvat check "<REAL_IDENTIFIER>" --country "<ISO2_COUNTRY>" --json
```

Common mistake:

- using the wrong identifier family for the country, such as mixing a VAT ID with a business-registration ID

## How To Read Results

In JSON mode, the most important fields are:

- `verification_result.status`
- `verification_result.legal_name`
- `verification_result.address`
- `normalized_identifier`
- `inferred_type`
- `audit_record.execution_timestamp`

For discovery mode, inspect:

- `query`
- `discovery_result`
- `formats`
- `sources`
- `formats[*].source_details`
- `sources[*].supported_type_details`

## Where Data Is Stored

The local SQLite database lives at:

```text
~/.verifyvat/audit.db
```

This database stores audit evidence for verification attempts, including:

- raw identifier
- normalized identifier
- inferred type
- internal status
- legal name
- address
- provider payload

## Common Troubleshooting

### `verifyvat: command not found`

Usually means the local virtual environment is not active.

Fix:

```bash
source .venv/bin/activate
verifyvat --help
```

Or use:

```bash
./.venv/bin/verifyvat --help
```

### `uv: command not found`

Use the `venv` and `pip` fallback path instead.

### Missing API key error

Export the environment variable:

```bash
export VERIFYVAT_API_KEY="your_secure_api_key_here"
```

### A real company test fails but the sample works

Check these first:

- are you using the correct country?
- are you verifying a VAT ID or a company-registration ID?
- if using `--type`, is it the exact VerifyVAT type for that identifier family?

## Repeatable Helper Scripts

Use the repo-local helper scripts when you want a fast confidence pass:

```bash
./scripts/smoke_test.sh --offline
./scripts/check_docs_alignment.py
```

When you have a valid `VERIFYVAT_API_KEY` exported and want the full end-to-end pass:

```bash
./scripts/smoke_test.sh --live
```

What these do:

- `./scripts/smoke_test.sh --offline` checks `verifyvat --version`, CLI help, local audit JSON, and docs alignment without calling the remote API
- `./scripts/smoke_test.sh --offline` prefers repo-local `.venv` binaries but falls back to the active environment's `verifyvat` and `python` executables when needed, which keeps CI-compatible installs working
- `./scripts/smoke_test.sh --live` adds real `check`, `discovery`, and `bulk` smoke tests using `./fixtures/sample_bulk_input.csv`
- `./scripts/check_docs_alignment.py` verifies the core docs still match the shipped command surface

## Recommended Daily Workflow

For a new developer working locally:

1. activate `.venv`
2. export `VERIFYVAT_API_KEY`
3. run `verifyvat --help`
4. run `verifyvat --version`
5. run `./scripts/smoke_test.sh --offline`
6. run the sample `check` smoke test
7. run your real test case
8. inspect `audit` output if you need evidence or debugging context

## Where To Go Next

- Start with the root [README.md](../README.md) for the project overview.
- Read [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) for the shipped implementation scope.
- Read [REFINEMENT_ROADMAP.md](./REFINEMENT_ROADMAP.md) for the next refinement and extension phases.
- Review the product and design context in [PRD.md](./PRD.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [DESIGN.md](./DESIGN.md), and [SPECS.md](./SPECS.md).
