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
Upon resolution, the output must be highly structured. A successful verification should utilize green ANSI coloring to highlight the active status, followed by a neatly aligned table displaying the legal name, address, and consultation receipt. In the event of a validation failure, red text should emphasize the invalid status, and the specific diagnostic issues returned by the SDK must be prominently displayed to explain *why* the identifier was rejected (e.g., "The modulus checksum is mathematically invalid for this jurisdiction").  
Crucially, if the operator appends the \--json flag to any command, all visual formatting, spinners, and color codes must be strictly suppressed. The application must silently stream the raw JSON string directly to standard output, ensuring seamless interoperability with tools like jq or deployment within CI/CD pipelines where visual artifacts would corrupt parsing logic.

