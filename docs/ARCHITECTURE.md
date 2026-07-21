## Architectural Design Document

The Architecture document outlines the technical framework, module boundaries, and data flow required to fulfill the mandates established in the PRD. The system is designed to be lightweight, stateless across network requests, and durable for local evidence retention.

The foundation of the application rests on Python 3.13 or higher. This version is required to use advanced typing syntax, structural pattern matching, and performance characteristics that align with the official VerifyVAT Python SDK. Dependency management and virtual environment orchestration use uv to ensure deterministic build environments for contributors.

The software architecture is segmented into four loosely coupled layers:

> 1. **The Presentation and Routing Layer:** This subsystem uses argparse to interpret command-line arguments, parse operational flags, and construct the initial execution context. It is responsible for standard output rendering and uses Rich for readable terminal tables, or standard string serialization when strict JSON output is requested.
> 2. **The Core Controller Logic:** This layer receives the parsed arguments and executes the primary business logic. It handles normalization of user inputs, stripping whitespace and obvious syntactical errors. It determines whether to invoke the inference API before verification or proceed directly to the verification API based on the supplied flags.
> 3. **The API Integration Wrapper:** This module encapsulates all interactions with the external VerifyVAT network. It is the only component permitted to read the VERIFYVAT_API_KEY from the system environment. It instantiates the VerifyVatClient, TypeInferrer, and Verifier SDK classes. This layer acts as an anti-corruption layer by catching raw HTTP exceptions, network timeouts, and JSON parsing errors, then translating them into safe domain exceptions.
> 4. **The Embedded Storage Engine:** To satisfy the audit requirements, this layer manages connections to a local SQLite database stored in the user's home directory at `~/.verifyvat/audit.db`. SQLite is chosen because it requires zero configuration, works well inside a standalone CLI package, and supports durable local evidence retention.

### Security Boundaries

- The Presentation Layer must never read or display API credentials.
- The API Integration Wrapper is the only layer allowed to access `VERIFYVAT_API_KEY`.
- The Storage Engine must persist verification data but must never persist API keys, auth headers, or other secrets.
- The network boundary must use HTTPS, explicit timeouts, and bounded retry rules.
- Although the VerifyVAT API supports multiple authentication mechanisms, the CLI standard is environment-backed, header-based authentication through the SDK.

### Ownership Boundaries

These ownership boundaries are part of the build contract:

- Argument parsing, flag validation, and command dispatch belong to the Presentation Layer.
- Input normalization, inference selection, verification orchestration, and domain-level error mapping belong to the Core Controller Logic.
- SDK client creation and external network communication belong to the API Integration Wrapper.
- SQLite schema creation, writes, and historical reads belong to the Embedded Storage Engine.

No layer should absorb another layer's responsibilities for convenience. This keeps the CLI testable and preserves security boundaries around credentials and persistence.

### Build Order

The implementation should be built and verified in the following order:

1. SQLite schema initialization and audit-write path.
2. SDK client bootstrap and authentication validation.
3. Single-ID verification flow with explicit type support.
4. Type inference flow for unknown identifiers.
5. Human-readable rendering.
6. `--json` rendering contract.
7. Bulk CSV processing.
8. Audit query and export flows.

The current phase-1 implementation stops after bulk CSV processing and durable audit writes. Audit-query and discovery-command behavior remain planned follow-on slices.

The flow of data through the system is strictly linear. Input enters through the Presentation Layer, is sanitized by the Controller, and is transmitted outward by the API Wrapper. After a response is received, the API Wrapper returns a structured object to the Controller. The Controller serializes this state, whether it represents a successful validation or an upstream error, and dispatches it to the Storage Engine. Only after the audit log is committed to disk does the Presentation Layer render the final output to the operator. This ordering guarantees that no visual confirmation is provided unless the compliance evidence is preserved.
