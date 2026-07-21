# **VerifyVAT Global Identity CLI**

An enterprise-grade, terminal-based application designed to validate and enrich global business identifiers (VAT, GST, TRN) by cross-referencing over 41 official government registries in real-time. Built upon the official VerifyVAT Python SDK, this tool provides instant syntactical checks, registry status verification, and automatic local audit logging to ensure strict financial compliance for cross-border B2B transactions.

## **Strategic Capabilities**

* **Deterministic Validation:** Replaces guesswork with definitive registry proof, validating syntax and checking active status directly against authoritative sources like EU VIES, UK Companies House, and global tax databases.  
* **Intelligent Type Inference:** Automatically deduces the jurisdiction and format type of raw strings, handling messy user inputs gracefully.  
* **Immutable Audit Logging:** Solves tax compliance requirements by automatically preserving timestamps, unique consultation receipts, and raw provider payloads into an embedded SQLite database for historical proof during audits.  
* **Bulk Operations:** Seamlessly process CSV files containing thousands of legacy IDs, generating enriched datasets with legal names and addresses ready for ERP ingestion.  
* **Automation Ready:** Emits strictly structured JSON payloads via the \--json flag for integration into CI/CD pipelines, backend chron jobs, or shell scripts.

## **Installation and Environment Setup**

This application strictly requires Python 3.13 or higher. We highly recommend utilizing the uv package manager for rapid dependency resolution.

> 1. Clone the repository to your local machine:bash git clone [https://github.com/MAlkabbani/VerifyVAT-Global-Identity](https://github.com/MAlkabbani/VerifyVAT-Global-Identity.git) cd VerifyVAT-Global-Identity  
> 2. Initialize the virtual environment and install all required dependencies:  
>    Bash  
>    uv venv  
>    uv pip install \-r requirements.txt

## **Security and Authentication Configuration**

The VerifyVAT CLI employs a zero-trust model for credential management. You must never hardcode your API key into scripts or pass it as a raw command-line argument.  
Obtain your API Key from the VerifyVAT dashboard and export it to your operating system's environment:

Bash  
export VERIFYVAT\_API\_KEY="your\_secure\_api\_key\_here"

## **Operational Usage**

**Validating a Single Identifier (Automatic Inference):** If the exact jurisdiction is unknown, provide the ID and a geographic hint. The CLI will infer the optimal format and execute the query.

Bash  
verifyvat check 914778271 \--country NO

**Validating an Identifier with a Known Format:** Bypass the inference engine for faster execution if the format is strictly known.

Bash  
verifyvat check 914778271 \--type no\_orgnr

**Executing Bulk Validations:** Ingest a CSV containing a column of raw identifiers and output an enriched dataset.

Bash  
verifyvat bulk ./inputs/legacy\_suppliers.csv \--output ./enriched\_suppliers.csv

**Retrieving Audit Evidence:** Query the local SQLite database to review historical validation attempts.

Bash  
verifyvat audit \--limit 10

## **Licensing and Contributions**

This software is released under the MIT License. Contributions, bug reports, and feature requests are actively welcomed to expand the tool's utility.
