# Contributing to gfi

Thank you for your interest in contributing! gfi (Good First Issue finder) is a small Python CLI that helps developers discover contribution opportunities on GitHub — the same kind of opportunity this guide is trying to make easier to find.

## Getting started

### Prerequisites

- Python 3.10+
- `gh` CLI ([installed](https://cli.github.com/)) for extension-related features (optional for core search)

### Setup

```bash
git clone https://github.com/yunaremaia/gfi.git
cd gfi
pip install -e ".[dev]"
```

This installs gfi in editable mode plus `pytest` for running tests.

## Running tests

```bash
pytest
```

The test suite lives in `tests/` and currently covers the search and filtering logic. Run with coverage:

```bash
pytest --cov=gfi --cov-report=term-missing
```

## Project structure

```
src/gfi/
  cli.py        # Click command group, argument parsing, output formatting
  search.py     # GitHub Search API queries, label filtering, sorting
  __init__.py   # Package metadata
tests/
  test_search.py
pyproject.toml  # Build config, deps, script entry points
README.md       # User-facing documentation
gh-extensions.md # GitHub CLI extension install guide
```

## How gfi works

1. **Search**: gfi calls the GitHub Search API (`/search/issues`) with a query built from the user's filters (`--language`, `--label`, `--exclude-label`, `--limit`, etc.).
2. **Filter**: results are filtered client-side by label, and issues already assigned or closed are excluded.
3. **aipr scan** (optional): when `aipr` is installed, gfi can run an AI policy check on candidate issues. See [aipr](https://github.com/yunaremaia/aipr) for details.
4. **Output**: results are rendered as a table (default), JSON (`--json`), or CSV (`--csv`).

## Adding a new filter

Filters live in `src/gfi/cli.py` as Click options on the `search` command. To add one:

1. Add a `@click.option(...)` decorator with the new flag.
2. Pass the value into the search query builder in `src/gfi/search.py`.
3. Add a test case in `tests/test_search.py` covering the new filter.
4. Document the flag in `README.md` and/or `gh-extensions.md`.

## Adding a new output format

Output formatting is handled in `cli.py` after the search returns results. To add a format:

1. Add a `--format <name>` option (or a dedicated flag like `--xml`).
2. Write a renderer function that takes the issue list and prints it.
3. Wire the flag into the command flow.
4. Test with a small fixture.

## GitHub CLI extension

gfi can be installed as a `gh` extension so you can run `gh gfi ...` alongside your other `gh` commands. See [`gh-extensions.md`](gh-extensions.md) for install instructions and the `aipr` pattern reference.

The extension entry point is declared in `pyproject.toml` under `[project.scripts]`. GitHub CLI wraps that entry point; no separate wrapper is needed.

## Pull requests

1. Fork the repo and create a branch from `main`.
2. Make your change on the branch.
3. Run `pytest` (and `ruff`/`black` if you have them configured) locally.
4. Open a PR against `main`. Link any related issue with `Closes #N` or `Fixes #N` in the PR body.

PRs don't need to be perfect on first submission — the maintainer will review and iterate with you.

## License

By contributing you agree that your contribution is licensed under the MIT License, the same license as the rest of gfi.
