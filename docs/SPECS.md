## Technical Specifications Document

The Technical Specifications translate the architectural vision into schemas, class contracts, and data structures. This document serves as the source of truth for developers writing the Python codebase.

### Audit Database Schema Definition

The SQLite database must be initialized on the first execution of the CLI if the database file does not exist. The schema must prioritize the immutable preservation of both the internal application state and the raw external API state.

| Column Designation | SQL Data Type | Functional Description and Compliance Purpose |
| :---- | :---- | :---- |
| transaction_id | INTEGER PRIMARY KEY | Autoincrementing index for local querying and sorting. |
| execution_timestamp | TEXT | ISO 8601 formatted UTC timestamp marking the exact moment the HTTP request was resolved. |
| consultation_receipt | TEXT | The unique internal tracking number provided by the registry or VerifyVAT, serving as proof of inquiry. |
| raw_user_input | TEXT | The exact string provided via the CLI, preserving the original context of user typos or formatting errors. |
| normalized_identifier | TEXT | The sanitized string transmitted to the API. |
| inferred_format_type | TEXT | The specific jurisdictional registry format utilized, such as gb_vat or de_ust_id. |
| internal_resolution_state | TEXT | Enum limited to VALID, INVALID, or NETWORK_ERROR. |
| verified_legal_entity | TEXT | The official corporate name returned by the registry. |
| registered_address | TEXT | The official geographic commercial location of the entity. |
| raw_provider_payload | JSON | The complete, unedited HTTP response body for debugging and audit review. |

*Table 2: SQLite Schema for the Immutable Audit Trail*

### Canonical Terminology

Use these terms consistently in code, docs, and CLI help text:

- Raw identifier: The exact user-provided identifier before normalization.
- Normalized identifier: The sanitized identifier passed into inference or verification.
- Inferred type: The final format string selected by `pick_best_inferred_id_type`.
- Verification result: The structured verification object returned by the SDK.
- Audit record: The SQLite record created for one verification attempt.
- Provider payload: The raw upstream response body stored for audit and debugging.

### SDK Implementation Mechanics

The application must adhere to the object-oriented patterns defined by the official Python SDK to preserve compatibility with upstream changes.

When processing an identifier of unknown provenance, the system must call TypeInferrer.infer_id_type with the normalized string and any optional geographic constraints. The resulting inference object contains multiple weighted probabilities. The developer must use the pick_best_inferred_id_type helper to extract the optimal format type.

During verification, Verifier.verify_id requires both the resolved type and the normalized identifier. The returned verification object contains nested state, and the application must use Verifier.describe_verification to extract human-readable diagnostics. The code must also handle cases where the registry confirms active status but redacts the entity's legal name and address. The application must handle None values gracefully during terminal rendering and database insertion.

### Module Contract

The initial implementation should keep module boundaries narrow and predictable:

- `main.py`: CLI entry point, argument parsing, command dispatch, exit code selection, and output-mode routing.
- `core.py`: Input normalization, type inference flow, verification flow, error mapping, and response shaping.
- `db.py`: SQLite initialization, schema management, audit-record inserts, and audit-query helpers.

The contract between these modules should be explicit:

- `main.py` must not call the SDK directly.
- `db.py` must not perform network requests.
- `core.py` must return structured results that can be rendered in either human-readable or JSON mode.
- Cross-module data exchange should use typed Python structures rather than ad hoc dictionaries where practical.

### API Security Requirements

The API supports multiple authentication mechanisms, but this CLI should standardize on the safest path for production use.

- Read `VERIFYVAT_API_KEY` from the environment at runtime and pass it through the SDK client configuration.
- Use HTTPS only. Do not disable certificate verification or route requests through insecure transport.
- Prefer header-based authentication and do not send secrets in query parameters or example URLs.
- Do not implement an `--api-key` CLI option or any equivalent input path that exposes secrets in shell history or process tables.
- Do not persist API keys, auth headers, or secret-bearing request metadata in the audit database.
- Redact secrets from debug output, tracebacks, support bundles, and exported diagnostics.
- Apply explicit timeouts and bounded retries to remote calls, and classify timeouts separately from invalid identifiers.

### Command Contract

Each CLI command must have a clear execution contract:

- `verifyvat check [ID]`: Accepts one raw identifier, optionally accepts `--country` and `--type`, performs normalization, optional inference, verification, audit logging, and final rendering.
- `verifyvat bulk [FILE]`: Accepts a CSV input file, processes identifiers row by row, writes an enriched CSV output, and records each attempted verification in SQLite.
- `verifyvat discovery`: Returns supported formats and/or sources without mutating the audit database unless the team later documents a reason to log discovery operations.
- `verifyvat audit`: Reads from SQLite only and must not perform remote verification requests.

### Output Contract

The output contract must stay stable across implementations:

- Human-readable mode may render tables, colors, short summaries, and progress indicators.
- `--json` mode must write exactly one machine-readable result object per command invocation to stdout.
- Non-data output, such as progress messages or warnings, must go to stderr or be suppressed when `--json` is enabled.
- Output structures must preserve the distinction between raw identifier, normalized identifier, inferred type, verification result, and audit metadata.
- Secret values, auth headers, and unredacted credential material must never appear in any output mode.

### Error-State Contract

Handled failures must map to consistent internal categories:

- `VALID`: The identifier was verified successfully.
- `INVALID`: The identifier completed verification but was not valid according to the provider or registry.
- `NETWORK_ERROR`: The request could not be completed reliably because of transport, timeout, upstream availability, or similar runtime failures.
- `CONFIG_ERROR`: The command could not start correctly because required local configuration was missing or invalid.

If implementation constraints require storing only three states in SQLite, `CONFIG_ERROR` must still remain distinguishable in the in-memory result and user-facing output, even if it is folded into a broader persisted status later.

### Processing Order Contract

The runtime flow for verification commands must follow this order:

1. Parse command arguments and validate local configuration.
2. Capture the raw identifier.
3. Normalize input into a normalized identifier.
4. Infer the type when an explicit type is not supplied.
5. Execute verification through the SDK.
6. Map the provider response into the internal verification result.
7. Persist the audit record.
8. Render user-facing output.

This order is intentional. It preserves a durable audit trail and keeps rendering concerns separate from verification logic.

## Terminal User Experience and Interface Design

The design of a CLI is defined by its argument syntax, feedback mechanisms, and output formatting. A successful tool must be intuitive for human operators while remaining predictable for automated shell scripts.

### Command Hierarchy and Argument Parsing

The CLI will expose a primary entry point, verifyvat, followed by discrete subcommands. This structure allows for future expansion without polluting the global argument space.

| Command Syntax | Operational Purpose | Key Arguments and Flags |
| :---- | :---- | :---- |
| verifyvat check [ID] | Executes a real-time validation against a single business identifier. | --country [ISO_CODE], --type [EXACT_FORMAT], --json |
| verifyvat bulk [FILE] | Ingests a CSV file, processes identifiers, and emits an enriched output file. | --output [FILE_PATH], --delay [SECONDS] |
| verifyvat discovery | Queries auxiliary endpoints to list supported jurisdictions and registry freshness. | --sources, --formats |
| verifyvat audit | Queries the local SQLite database to retrieve historical validation evidence. | --limit [INT], --export-csv |

*Table 3: CLI Command Hierarchy and Subcommand Architecture*

### Visual Feedback and Progressive Disclosure

Because interactions with governmental registries can introduce unpredictable latency, the CLI must provide continuous visual feedback to the operator. When the check or bulk commands are initiated, the application must immediately render an indeterminate loading indicator, such as an animated terminal spinner, accompanied by status text. This assures the user that the process has not stalled.

Upon resolution, the output must be highly structured. A successful verification should use green ANSI coloring to highlight the active status, followed by an aligned table displaying the legal name, address, and consultation receipt. If validation fails, red text should emphasize the invalid status, and the specific diagnostic issues returned by the SDK must explain why the identifier was rejected.

If the operator appends the --json flag to any command, all visual formatting, spinners, and color codes must be suppressed. The application must stream the raw JSON string directly to standard output so tools like jq and CI/CD pipelines can consume it safely.

When `--json` is enabled, stdout should contain only the machine-readable result payload. Any progress messages, warnings, or diagnostics must be redirected to stderr or suppressed so downstream parsers receive a clean output contract.
