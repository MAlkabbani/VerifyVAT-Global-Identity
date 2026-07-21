## **Technical Specifications Document (SPECS.md)**

The Technical Specifications translate the architectural vision into precise schemas, class contracts, and data structures. This document serves as the absolute source of truth for developers actively writing the Python codebase.

### **Audit Database Schema Definition**

The SQLite database must be initialized upon the first execution of the CLI if the .db file does not exist. The schema must prioritize the immutable preservation of both the internal application state and the raw external API state4.

| Column Designation | SQL Data Type | Functional Description and Compliance Purpose |
| :---- | :---- | :---- |
| transaction\_id | INTEGER PRIMARY KEY | Autoincrementing index for local querying and sorting. |
| execution\_timestamp | TEXT | ISO 8601 formatted UTC timestamp marking the exact moment the HTTP request was resolved. Vital for audit defense1. |
| consultation\_receipt | TEXT | The unique cryptographic receipt or internal tracking number provided by the registry or VerifyVAT, serving as definitive proof of inquiry1. |
| raw\_user\_input | TEXT | The exact string provided via the CLI, preserving the original context of user typos or formatting errors4. |
| normalized\_identifier | TEXT | The mathematically sanitized string actually transmitted to the API. |
| inferred\_format\_type | TEXT | The specific jurisdictional registry format utilized (e.g., gb\_vat, de\_ust\_id)5. |
| internal\_resolution\_state | TEXT | ENUM strictly limited to: VALID, INVALID, NETWORK\_ERROR. Maps disparate external errors into a predictable internal ontology4. |
| verified\_legal\_entity | TEXT | The official corporate name returned by the registry, allowing finance teams to manually cross-reference ERP records4. |
| registered\_address | TEXT | The official geographic commercial location of the entity4. |
| raw\_provider\_payload | JSON | The complete, unedited HTTP response body. This allows for retroactive debugging and provides the ultimate source of truth during rigorous compliance audits4. |

*Table 2: SQLite Schema for the Immutable Audit Trail*

### **SDK Implementation Mechanics**

The application must strictly adhere to the object-oriented patterns mandated by the official Python SDK to ensure future compatibility with upstream changes6.  
When processing an identifier of unknown provenance, the system must execute the TypeInferrer.infer\_id\_type method, passing the normalized string and any optional geographic constraints6. The resulting inference object is complex and contains multiple weighted probabilities. The developer must strictly utilize the pick\_best\_inferred\_id\_type helper method to programmatically extract the optimal string representation of the format type6.  
During the verification phase, the Verifier.verify\_id method requires explicit parameter passing of both the resolved type and the normalized identifier6. The returned verification object encapsulates a rich, deeply nested state. The application must leverage the Verifier.describe\_verification helper to extract human-readable diagnostic summaries6. The code must anticipate scenarios where the registry confirms the active status of the ID but, due to local jurisdictional privacy regulations, redacts or obfuscates the entity's legal name and address. The application must handle None types gracefully during terminal rendering and database insertion to prevent cascading application failures.

## **Terminal User Experience and Interface Design (DESIGN.md)**

The design of a CLI is defined by its argument syntax, feedback mechanisms, and output formatting. A successful tool must be intuitive for human operators while remaining structurally predictable for automated shell scripts.

### **Command Hierarchy and Argument Parsing**

The CLI will expose a primary entry point, verifyvat, followed by discrete subcommands. This hierarchical structure allows for future expansion of the tool's capabilities without polluting the global argument space.

| Command Syntax | Operational Purpose | Key Arguments and Flags |
| :---- | :---- | :---- |
| verifyvat check \[ID\] | Executes a real-time validation against a single business identifier1. | \--country \[ISO\_CODE\], \--type \[EXACT\_FORMAT\], \--json |
| verifyvat bulk \[FILE\] | Ingests a CSV file, iteratively processes identifiers, and emits an enriched output file1. | \--output \[FILE\_PATH\], \--delay \[SECONDS\] |
| verifyvat discovery | Queries the auxiliary endpoints to list supported jurisdictions and registry freshness6. | \--sources, \--formats |
| verifyvat audit | Queries the local SQLite database to retrieve historical validation evidence2. | \--limit \[INT\], \--export-csv |

*Table 3: CLI Command Hierarchy and Subcommand Architecture*

### **Visual Feedback and Progressive Disclosure**

Because interactions with governmental registries can introduce unpredictable latency, the CLI must provide continuous visual feedback to the operator. When the check or bulk commands are initiated, the application must immediately render an indeterminate loading indicator (such as an animated terminal spinner) accompanied by status text (e.g., "Negotiating with European VIES Registry..."). This assures the user that the thread has not stalled.  
Upon resolution, the output must be highly structured. A successful verification should utilize green ANSI coloring to highlight the active status, followed by a neatly aligned table displaying the legal name, address, and consultation receipt. In the event of a validation failure, red text should emphasize the invalid status, and the specific diagnostic issues returned by the SDK must be prominently displayed to explain *why* the identifier was rejected (e.g., "The modulus checksum is mathematically invalid for this jurisdiction")6.  
Crucially, if the operator appends the \--json flag to any command, all visual formatting, spinners, and color codes must be strictly suppressed. The application must silently stream the raw JSON string directly to standard output, ensuring seamless interoperability with tools like jq or deployment within CI/CD pipelines where visual artifacts would corrupt parsing logic.
