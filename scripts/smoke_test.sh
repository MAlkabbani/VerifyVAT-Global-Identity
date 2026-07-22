#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE_PATH="${ROOT_DIR}/fixtures/sample_bulk_input.csv"
MODE="${1:-auto}"
TEMP_OUTPUT="${ROOT_DIR}/.tmp-smoke-output.csv"
CLI_BIN="${VERIFYVAT_CLI_BIN:-}"
PYTHON_BIN="${VERIFYVAT_PYTHON_BIN:-}"
CLI_DESC=""
CLI_CMD=()

cleanup() {
  rm -f "${TEMP_OUTPUT}"
}

trap cleanup EXIT

resolve_cli_bin() {
  local configured_cli=""

  if [[ -n "${CLI_BIN}" ]]; then
    if [[ -x "${CLI_BIN}" ]]; then
      CLI_BIN="$(cd "$(dirname "${CLI_BIN}")" && pwd)/$(basename "${CLI_BIN}")"
      CLI_DESC="${CLI_BIN}"
      CLI_CMD=("${CLI_BIN}")
      return
    fi

    if command -v "${CLI_BIN}" >/dev/null 2>&1; then
      configured_cli="$(command -v "${CLI_BIN}")"
      CLI_BIN="${configured_cli}"
      CLI_DESC="${CLI_BIN}"
      CLI_CMD=("${CLI_BIN}")
      return
    fi
  fi

  if [[ -x "${ROOT_DIR}/.venv/bin/verifyvat" ]]; then
    CLI_BIN="${ROOT_DIR}/.venv/bin/verifyvat"
    CLI_DESC="${CLI_BIN}"
    CLI_CMD=("${CLI_BIN}")
    return
  fi

  if command -v verifyvat >/dev/null 2>&1; then
    CLI_BIN="$(command -v verifyvat)"
    CLI_DESC="${CLI_BIN}"
    CLI_CMD=("${CLI_BIN}")
    return
  fi

  if "${PYTHON_BIN}" -c "import verifyvat_cli" >/dev/null 2>&1; then
    CLI_BIN="${PYTHON_BIN}"
    CLI_DESC="${PYTHON_BIN} -m verifyvat_cli.main"
    CLI_CMD=("${PYTHON_BIN}" "-m" "verifyvat_cli.main")
    return
  fi

  echo "Could not locate a VerifyVAT CLI executable." >&2
  echo "Preferred local path: ${ROOT_DIR}/.venv/bin/verifyvat" >&2
  echo "Fallback paths: an active-environment \`verifyvat\` on PATH, or \`${PYTHON_BIN} -m verifyvat_cli.main\`" >&2
  echo "Set up the local environment first, for example: uv sync, or install with: python -m pip install -e \".[dev]\"" >&2
  exit 1
}

resolve_python_bin() {
  if [[ -n "${PYTHON_BIN}" ]]; then
    if [[ -x "${PYTHON_BIN}" ]]; then
      return
    fi

    if command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v "${PYTHON_BIN}")"
      return
    fi
  fi

  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
    return
  fi

  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
    return
  fi

  echo "Could not locate a Python interpreter for smoke checks." >&2
  exit 1
}

resolve_python_bin
resolve_cli_bin

if [[ "${#CLI_CMD[@]}" -eq 0 ]]; then
  echo "Failed to configure a VerifyVAT CLI command." >&2
  exit 1
fi

if [[ -n "${CLI_BIN}" && ! -x "${CLI_BIN}" ]]; then
  echo "Configured VerifyVAT CLI is not executable: ${CLI_BIN}" >&2
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Configured Python interpreter is not executable: ${PYTHON_BIN}" >&2
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

echo "Running smoke checks..."
echo "Using CLI: ${CLI_DESC}"
echo "Using Python: ${PYTHON_BIN}"
"${CLI_CMD[@]}" --version
"${CLI_CMD[@]}" --help >/dev/null
"${CLI_CMD[@]}" audit --limit 1 --json >/dev/null
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
"${CLI_CMD[@]}" check 914778271 --type no_orgnr --json >/dev/null
"${CLI_CMD[@]}" check 914778271 --country NO --json >/dev/null
"${CLI_CMD[@]}" discovery --country NO --json >/dev/null
"${CLI_CMD[@]}" bulk "${FIXTURE_PATH}" --output "${TEMP_OUTPUT}" --json >/dev/null

if [[ ! -s "${TEMP_OUTPUT}" ]]; then
  echo "Expected smoke-test bulk output file was not created: ${TEMP_OUTPUT}" >&2
  exit 1
fi

echo "Live smoke checks passed."
