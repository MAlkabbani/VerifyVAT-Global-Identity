## Product Requirements Document

The Product Requirements Document defines the operational scope, target personas, and functional requirements for the CLI.

The VerifyVAT Command Line Interface is intended to be a practical utility for financial operations, compliance auditing, and developer workflows. It bridges the gap between web dashboards and lower-level API integrations by providing an immediate terminal-based interface for global identity verification.

The primary user personas are compliance officers who need to spot-check a supplier before authorizing payment, systems administrators who automate bulk validation tasks in nightly cron jobs, and backend developers who test API assumptions before integrating with a service.

For consistency across product, architecture, and implementation documents, use the terms raw identifier, normalized identifier, inferred type, verification result, audit record, and provider payload with their exact meanings.

To satisfy these personas, the application must produce deterministic output. When a user inputs a raw string, the CLI must infer the identifier type when the jurisdiction is unknown, perform the verification query, and render the results in a readable terminal table. For programmatic use cases, the CLI must support a strict JSON output flag so the verified payload can be piped into tools like jq or external logging systems.

The PRD also requires a durable audit trail. Taxation authorities require proof that validation occurred on a specific date. The CLI must persist every transaction, including the normalized input, returned entity details, timestamp, and raw API response payload, into an embedded SQLite database. This ensures that even ephemeral terminal checks still produce a permanent, queryable compliance history.

Bulk processing is another non-negotiable requirement. The application must ingest a CSV file containing hundreds or thousands of legacy customer IDs, apply the required rate limiting and retry logic, and generate an enriched CSV file containing validation status, legal names, and failure diagnostics for ingestion into ERP systems.

The CLI must also enforce a secure authentication posture. It must read `VERIFYVAT_API_KEY` from the runtime environment, use the SDK's recommended header-based authentication path, reject command-line secret injection, and avoid exposing secrets in logs, debug output, or persisted audit data.

The scope of the application is limited to validation and local auditing. It will not manage user billing, account creation, or API key provisioning; those responsibilities remain in the VerifyVAT web platform.
