#!/usr/bin/env python3
"""Lightweight guardrail to keep key docs aligned with the shipped CLI surface."""

from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

REQUIRED_FILES = (
    Path("README.md"),
    Path("docs/GETTING_STARTED_GUIDE.md"),
    Path("docs/DESIGN.md"),
    Path("docs/SPECS.md"),
    Path("docs/ARCHITECTURE.md"),
    Path("docs/PRD.md"),
    Path("fixtures/sample_bulk_input.csv"),
    Path("scripts/smoke_test.sh"),
)

REQUIRED_SNIPPETS: dict[Path, tuple[str, ...]] = {
    Path("README.md"): (
        "`verifyvat --version`",
        "`./scripts/smoke_test.sh --offline`",
        "`./scripts/check_docs_alignment.py`",
        "`./fixtures/sample_bulk_input.csv`",
        "verifyvat audit --limit 10 --json",
        "verifyvat audit --status VALID --search hydro",
    ),
    Path("docs/GETTING_STARTED_GUIDE.md"): (
        "`verifyvat --version`",
        "`./scripts/smoke_test.sh --offline`",
        "`./fixtures/sample_bulk_input.csv`",
        "verifyvat audit --limit 10 --json",
        "verifyvat audit --status VALID --search hydro",
    ),
    Path("docs/DESIGN.md"): (
        "--limit [INT], --export-csv [FILE_PATH], --status [STATUS], --search [TEXT], --json",
        "The root parser should also expose a `--version` flag",
    ),
    Path("docs/SPECS.md"): (
        "`verifyvat audit`: Reads recent local audit records from SQLite, renders them in a human-readable table, may filter the selected rows by exact status or case-insensitive search, and may export the selected rows as CSV or JSON.",
        "--limit [INT], --export-csv [FILE_PATH], --status [STATUS], --search [TEXT], --json",
        "The root parser should expose `--version` so operators can confirm the installed release quickly.",
    ),
    Path("docs/ARCHITECTURE.md"): (
        "The currently shipped implementation now includes audit-query and export flows",
    ),
    Path("docs/PRD.md"): (
        "The currently shipped implementation scope delivers `check`, `bulk`, `audit`, and `discovery`.",
    ),
}


def main() -> int:
    """Check a small set of high-signal doc invariants."""

    missing_files = [path for path in REQUIRED_FILES if not (ROOT_DIR / path).is_file()]
    if missing_files:
        for path in missing_files:
            print(f"Missing required file: {path}")
        return 1

    missing_snippets: list[tuple[Path, str]] = []
    for relative_path, snippets in REQUIRED_SNIPPETS.items():
        content = (ROOT_DIR / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in content:
                missing_snippets.append((relative_path, snippet))

    if missing_snippets:
        for relative_path, snippet in missing_snippets:
            print(f"Missing snippet in {relative_path}: {snippet}")
        return 1

    print("Docs alignment checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
