# Contributing

Thanks for contributing to `verifyvat-cli`.

## Before You Start

- Read [README.md](README.md) for the current command surface and local setup.
- Read [docs/GETTING_STARTED_GUIDE.md](docs/GETTING_STARTED_GUIDE.md) if you are new to the repository.
- Review [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) and [docs/REFINEMENT_ROADMAP.md](docs/REFINEMENT_ROADMAP.md) before proposing larger changes.

## Development Workflow

1. Create and activate a local environment.
2. Install project dependencies.
3. Export `VERIFYVAT_API_KEY` only when you need live API checks.
4. Keep changes scoped to the task you are solving.

Preferred setup:

```bash
uv sync
source .venv/bin/activate
```

Fallback setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Contribution Expectations

- Preserve the current CLI behavior unless the change explicitly updates the documented contract.
- Keep `--json` output machine-readable and free of extra stdout noise.
- Treat API keys, auth headers, and provider payload secrets as sensitive.
- Update documentation when command behavior, setup, or outputs change.
- Prefer focused tests and targeted validation over broad speculative rewrites.

## Validation

Run the highest-signal checks for your change set:

```bash
pytest
ruff check .
mypy src
./scripts/smoke_test.sh --offline
```

Use `./scripts/smoke_test.sh --live` only when `VERIFYVAT_API_KEY` is exported and you intentionally want live provider coverage.

## Pull Requests

- Describe the user-visible change clearly.
- Mention any documentation updates included in the same change.
- Note whether validation was offline only or included live API checks.
