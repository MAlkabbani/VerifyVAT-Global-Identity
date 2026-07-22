#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI_BIN="${ROOT_DIR}/.venv/bin/verifyvat"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
FIXTURE_PATH="${ROOT_DIR}/fixtures/sample_bulk_input.csv"
MODE="${1:-auto}"
TEMP_OUTPUT="${ROOT_DIR}/.tmp-smoke-output.csv"

cleanup() {
  rm -f "${TEMP_OUTPUT}"
}

trap cleanup EXIT

if [[ ! -x "${CLI_BIN}" ]]; then
  echo "Missing repo-local CLI entrypoint: ${CLI_BIN}" >&2
  echo "Set up the local environment first, for example: uv sync" >&2
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing repo-local Python interpreter: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -f "${FIXTURE_PATH}" ]]; then
  echo "Missing sample bulk fixture: ${FIXTURE_PATH}" >&2
  exit 1
fi

if [[ "${MODE}" != "auto" && "${MODE}" != "--offline" && "${MODE}" != "--live" ]]; then
  echo "Usage: ./scripts/smoke_test.sh [--offline|--live]" >&2
  exit 1
fi

echo "Running repo-local smoke checks..."
"${CLI_BIN}" --version
"${CLI_BIN}" --help >/dev/null
"${CLI_BIN}" audit --limit 1 --json >/dev/null
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/check_docs_alignment.py"

if [[ "${MODE}" == "--offline" ]]; then
  echo "Offline smoke checks passed."
  exit 0
fi

if [[ -z "${VERIFYVAT_API_KEY:-}" ]]; then
  if [[ "${MODE}" == "--live" ]]; then
    echo "VERIFYVAT_API_KEY is required for --live smoke checks." >&2
    exit 1
  fi

  echo "Skipping live API smoke checks because VERIFYVAT_API_KEY is not set."
  echo "Offline smoke checks passed."
  exit 0
fi

echo "Running live VerifyVAT smoke checks..."
"${CLI_BIN}" check 914778271 --type no_orgnr --json >/dev/null
"${CLI_BIN}" check 914778271 --country NO --json >/dev/null
"${CLI_BIN}" discovery --country NO --json >/dev/null
"${CLI_BIN}" bulk "${FIXTURE_PATH}" --output "${TEMP_OUTPUT}" --json >/dev/null

if [[ ! -s "${TEMP_OUTPUT}" ]]; then
  echo "Expected smoke-test bulk output file was not created: ${TEMP_OUTPUT}" >&2
  exit 1
fi

echo "Live smoke checks passed."
