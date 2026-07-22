# VerifyVAT CLI Refinement Roadmap

## Related Docs

- Repository overview: [README.md](../README.md)
- Beginner onboarding: [GETTING_STARTED_GUIDE.md](./GETTING_STARTED_GUIDE.md)
- Shipped implementation scope: [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)
- Product and architecture context: [PRD.md](./PRD.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [DESIGN.md](./DESIGN.md), [SPECS.md](./SPECS.md)

## Purpose

This roadmap captures the post-implementation refinement and extension work that follows the completed CLI skeleton. It prioritizes usability, onboarding clarity, operational confidence, and targeted feature deepening without changing the core architecture.

## Current Baseline

The current shipped CLI already includes:

- `verifyvat check`
- `verifyvat bulk`
- `verifyvat audit`
- `verifyvat discovery`

The next phase is not about adding a missing command. It is about making the existing product easier to install, easier to understand, safer to operate, and easier to maintain.

## Delivery Principles

- Preserve the existing module boundaries between `main.py`, `core.py`, and `db.py`.
- Prefer high-signal refinements over broad redesign.
- Keep machine-readable `--json` output stable and quiet on stdout.
- Improve human-readable UX without weakening automation contracts.
- Keep docs aligned with what works locally in the repository.

## Phased Roadmap

### R1. Onboarding and Docs Clarity

Goal: make setup and first use obvious for a new or junior developer.

Planned outcomes:

- tighten the root `README.md` around real working setup paths
- add a comprehensive beginner-friendly guide document in `docs/`
- link the guide prominently from the root README
- clarify the difference between known-type verification and country-based inference
- document the recommended local `.venv` execution path first, with `uv` and `pip` fallback paths

### R2. CLI Help and UX Polish

Goal: improve the first-run terminal experience without changing command semantics.

Planned outcomes:

- add stronger parser descriptions and help text
- improve command discoverability with examples in help output
- make command intent clearer for `check`, `bulk`, `audit`, and `discovery`
- review human-readable output wording for consistency with repository terminology

### R3. CI and Maintenance Guardrails

Goal: make the current quality bar automatic and repeatable.

Planned outcomes:

- add a GitHub Actions workflow for `ruff`, `mypy`, and `pytest`
- ensure the workflow uses the repository’s supported Python version
- keep the CI setup lightweight and aligned with the current local toolchain

### R4. Discovery and Audit Extensions

Goal: deepen the existing product surface only where real use suggests value.

Candidate follow-on work:

- expand discovery metadata where the provider surface exposes richer per-format and per-source coverage detail
- note explicitly when hoped-for freshness timestamps are not available in the current SDK discovery payloads
- consider `audit --json` only if automation needs a machine-readable audit-read path
- consider audit filtering or search only after real operator usage justifies it

### R5. Productization Polish

Goal: make the repository easier to adopt and safer to evolve.

Candidate follow-on work:

- release/versioning polish
- smoke-test scripts for repeatable manual checks
- example input fixtures for bulk mode
- docs alignment checks across README, guide, and product docs

## Immediate Execution Order

The first execution tranche follows this order:

1. Create the roadmap and onboarding guide artifacts.
2. Refine the root `README.md` and link the new guide.
3. Polish CLI help text and usability wording.
4. Add CI automation.
5. Re-run tests, type checks, lint, and focused CLI checks.

## Definition of Done for This Tranche

This first refinement tranche is complete when:

- a new developer can set up and run the CLI by following the README and guide only
- the CLI help is materially clearer than the current baseline
- CI enforces the existing local quality checks
- the updated docs reflect the actual shipped command surface and setup paths
