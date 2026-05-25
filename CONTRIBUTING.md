# Contributing to GitHub Code Analyzer

Thank you for your interest in contributing!

## Development setup

```bash
git clone https://github.com/arun250492/archhelp-Claude-plugin
cd archhelp-Claude-plugin
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running tests

```bash
# All tests with coverage (must stay ≥ 80%)
pytest

# Fast run (skip coverage)
pytest --no-cov -x

# Single file
pytest tests/test_diagrams.py -v
```

## Linting and formatting

```bash
ruff check server/ tests/    # lint
ruff format server/ tests/   # auto-format
mypy server/                 # type-check
```

All three must pass before opening a PR.  The CI pipeline enforces this.

## Adding a new diagram type

1. Add the generator function to `server/diagrams.py`.
2. Register the tool in `server/main.py` (`_tools()` list and the
   `diagram_fn` dispatch dict in `call_tool`).
3. Add at least 5 unit tests to `tests/test_diagrams.py`.
4. Update the tool table in `README.md`.

## Adding a new ORM / framework

- **ORM models** → add a regex to `analyzer.py: _MODEL_PATTERNS`
  and FK patterns to `_FK_PATTERNS`.
- **Frameworks** → add root file markers to
  `analyzer.py: _ROOT_FRAMEWORK_MARKERS`.
- **Services / middleware** → add a pattern to
  `analyzer.py: _SERVICE_PATTERNS`.
- Add tests in `tests/test_analysis.py` with a sample content fixture.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: detect NestJS framework from nest-cli.json
fix: handle repos with no default branch set
test: add coverage for Prisma FK extraction
docs: add Nuxt.js to supported frameworks table
```

## Pull request checklist

- [ ] Tests pass (`pytest`)
- [ ] Linting passes (`ruff check`, `ruff format --check`)
- [ ] Type-check passes (`mypy server/`)
- [ ] Coverage remains ≥ 80%
- [ ] `CHANGELOG.md` updated (under `[Unreleased]`)
- [ ] `README.md` updated if new tools or frameworks were added
