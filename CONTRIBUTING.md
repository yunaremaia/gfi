# Contributing to gfi

Thank you for your interest in contributing to `gfi` (Good First Issue Finder)! We welcome bug reports, feature suggestions, documentation updates, and pull requests.

---

## 1. Development Setup

`gfi` requires **Python 3.10** or higher.

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/gfi.git
   cd gfi
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv

   # Linux / macOS:
   source .venv/bin/activate

   # Windows:
   .venv\Scripts\activate
   ```

3. **Install in editable mode with development dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

---

## 2. Running Tests

Tests are located in the `tests/` directory and use `pytest`:

```bash
# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_cli.py
pytest tests/test_search.py
```

Ensure all existing and new tests pass before submitting your changes.

---

## 3. Code Style & Quality

- **Formatting & Linting:** Code follows standard Python conventions (PEP 8). We recommend using `ruff` or `black` for formatting.
- **Type Annotations:** Use Python type hints where applicable.
- **Dependencies:** Keep dependencies minimal; `gfi` relies on `click` and `rich` for fast CLI interactions.

---

## 4. Project Structure

The core package lives under `src/gfi/`:

- `src/gfi/cli.py`: Defines the Click command-line interface, subcommands (`search`, `repo`, `trending`, `feed`, `stats`, `reset`, `open`), and formatting helpers for Rich tables, JSON, and CSV exports.
- `src/gfi/search.py`: Core GitHub API integration and `Issue` dataclass. Handles query construction, rate-limit headers, and persistent seen-issue tracking via local JSON cache (`~/.cache/gfi/seen.json`).

---

## 5. GitHub API & Authentication

`gfi` uses GitHub's public REST Search API:
- **Unauthenticated:** A personal access token is **optional** for querying public issues (subject to standard GitHub IP rate limits: 10 requests/minute for Search).
- **Authenticated:** Set the `GITHUB_TOKEN` environment variable to authenticate requests for higher rate limits (30 requests/minute for Search) or private repositories:
  ```bash
  export GITHUB_TOKEN="ghp_your_token_here"
  ```

---

## 6. Pull Request Process

1. **Branch Naming:** Create a focused feature branch from `main`:
   - `feat/feature-name`
   - `fix/bug-description`
   - `docs/guide-name`
2. **Commit Conventions:** Write clear, descriptive commit messages outlining what changed and why.
3. **Testing:** Include unit tests in `tests/` covering any new functionality or bug fixes.
4. **Open a PR:** Submit your pull request against the `main` branch with a concise summary and link any relevant issue (e.g. `Closes #7`).

---

## 7. Code of Conduct

We are committed to providing a friendly, inclusive, and welcoming environment for all contributors. Please treat fellow maintainers and contributors with respect and kindness.
