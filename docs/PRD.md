## Product Requirements Document

### Related Docs

- Repository overview: [README.md](../README.md)
- Beginner onboarding: [GETTING_STARTED_GUIDE.md](./GETTING_STARTED_GUIDE.md)
- Shipped implementation scope: [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)
- Follow-on refinement phases: [REFINEMENT_ROADMAP.md](./REFINEMENT_ROADMAP.md)
- Supporting technical docs: [ARCHITECTURE.md](./ARCHITECTURE.md), [DESIGN.md](./DESIGN.md), [SPECS.md](./SPECS.md)

The Product Requirements Document defines the operational scope, target personas, and functional requirements for the CLI.

The VerifyVAT Command Line Interface is intended to be a practical utility for financial operations, compliance auditing, and developer workflows. It bridges the gap between web dashboards and lower-level API integrations by providing an immediate terminal-based interface for global identity verification.

The primary user personas are compliance officers who need to spot-check a supplier before authorizing payment, systems administrators who automate bulk validation tasks in nightly cron jobs, and backend developers who test API assumptions before integrating with a service.

For consistency across product, architecture, and implementation documents, use the terms raw identifier, normalized identifier, inferred type, verification result, audit record, and provider payload with their exact meanings.

To satisfy these personas, the application must produce deterministic output. When a user inputs a raw string, the CLI must infer the identifier type when the jurisdiction is unknown, perform the verification query, and render the results in a readable terminal table. For programmatic use cases, the CLI must support a strict JSON output flag so the verified payload can be piped into tools like jq or external logging systems.

The PRD also requires a durable audit trail. Taxation authorities require proof that validation occurred on a specific date. The CLI must persist every transaction, including the normalized input, returned entity details, timestamp, and raw API response payload, into an embedded SQLite database. This ensures that even ephemeral terminal checks still produce a permanent, queryable compliance history.

Bulk processing is another non-negotiable requirement. The application must ingest a CSV file containing hundreds or thousands of legacy customer IDs, apply the required rate limiting and retry logic, and generate an enriched CSV file containing validation status, legal names, and failure diagnostics for ingestion into ERP systems.

The CLI must also enforce a secure authentication posture. It must read `VERIFYVAT_API_KEY` from the runtime environment, use the SDK's recommended header-based authentication path, reject command-line secret injection, and avoid exposing secrets in logs, debug output, or persisted audit data.

The scope of the application is limited to validation and local auditing. It will not manage user billing, account creation, or API key provisioning; those responsibilities remain in the VerifyVAT web platform.

The currently shipped implementation scope delivers `check`, `bulk`, `audit`, and `discovery`. We prioritized `audit` before `discovery`, then shipped `discovery` with a narrow first-pass contract focused on supported formats and registry sources rather than deeper metadata exports.

### Product Invariants

These rules are part of the build contract and must remain true unless the docs are explicitly changed:

- Every verification attempt produces an audit record before user-facing success output is rendered.
- The CLI never accepts API credentials through command-line flags.
- Human-readable mode and `--json` mode are both first-class interfaces and must stay deterministic.
- Raw identifiers may be transformed into normalized identifiers, but the original raw input must still be retained in the audit record.
- Invalid identifiers, network failures, and configuration failures must remain distinguishable states.
- The product remains a local CLI for verification and audit logging; it does not evolve into a billing, account-management, or hosted orchestration tool.

### Release Acceptance Criteria

A build is not complete unless it satisfies the following criteria:

- A developer can install dependencies, set `VERIFYVAT_API_KEY`, and execute a single verification from the terminal.
- A developer can confirm the installed release with `verifyvat --version` and run the documented repo-local smoke-test workflow.
- A single verification can run with either explicit type input or inference-driven type selection.
- Bulk processing can read identifiers from a CSV input and write a corresponding enriched CSV output.
- Each verification attempt writes a durable audit record to SQLite, including success and handled failure cases.
- `--json` mode emits machine-readable output to stdout without spinner noise, table formatting, or leaked secrets.
- Missing configuration, remote failures, and invalid identifiers produce clean user-facing diagnostics without raw tracebacks by default.
