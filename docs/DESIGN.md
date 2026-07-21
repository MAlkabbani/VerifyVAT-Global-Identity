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

### Output Safety Rules

- Human-readable mode may use tables, colors, and progress indicators.
- `--json` mode must write only the verification result to stdout.
- Secrets, auth headers, and raw credential values must never appear in terminal output.
- Debug output must redact sensitive values before printing.
