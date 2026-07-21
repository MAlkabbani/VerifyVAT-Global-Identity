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

1. Clone the repository:

   ```bash
   git clone https://github.com/MAlkabbani/VerifyVAT-Global-Identity.git
   cd VerifyVAT-Global-Identity
   ```

2. Create the virtual environment and install dependencies:

   ```bash
   uv venv
   uv pip install -r requirements.txt
   ```

## Security and Authentication Configuration

The VerifyVAT CLI uses environment-based credential management. Do not hardcode your API key into scripts or pass it as a raw command-line argument.

Obtain your API key from the VerifyVAT dashboard and export it to your operating system environment:

```bash
export VERIFYVAT_API_KEY="your_secure_api_key_here"
```

The official VerifyVAT authentication docs note that the API can accept credentials by header, JSON field, or query parameter. For this CLI, use the SDK with `VERIFYVAT_API_KEY` from the environment so requests authenticate through the recommended header-based flow.

## API Security Baseline

- Read the API key only from environment variables or a secret manager.
- Do not support `--api-key` style CLI flags because they leak into shell history and process listings.
- Do not print the API key, auth headers, or secret-bearing payload fragments to stdout, stderr, logs, or SQLite.
- Use HTTPS for all remote calls and fail fast with a clear error if the API key is missing.
- Prefer header-based authentication and do not place secrets in URLs, query strings, or copied example commands.
- Redact secrets from debug output, error reports, and exported diagnostics.

## Operational Usage

### Validating a Single Identifier

If the exact jurisdiction is unknown, provide the ID and a geographic hint. The CLI will infer the optimal format and execute the query.

```bash
verifyvat check 914778271 --country NO
```

### Validating an Identifier with a Known Format

Bypass the inference engine for faster execution when the format is already known.

```bash
verifyvat check 914778271 --type no_orgnr
```

### Executing Bulk Validations

Ingest a CSV containing raw identifiers and output an enriched dataset.

```bash
verifyvat bulk ./inputs/legacy_suppliers.csv --output ./enriched_suppliers.csv
```

### Retrieving Audit Evidence

Query the local SQLite database to review historical validation attempts.

```bash
verifyvat audit --limit 10
```

## Licensing and Contributions

This software is released under the MIT License. Contributions, bug reports, and feature requests are welcome.
