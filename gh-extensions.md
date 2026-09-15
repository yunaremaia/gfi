# GitHub CLI Extension: Install `gh gfi`

You can use `gfi` as a [GitHub CLI extension](https://cli.github.com/manual/gh) so it lives alongside your other `gh` commands — type `gh gfi` instead of `gfi` directly.

## Install

From the upstream repository:

```bash
gh extension install yunaremaia/gfi
```

Once installed, the same commands are available under the `gh` namespace:

```bash
gh gfi search --limit 3
gh gfi --help
```

## Uninstall

```bash
gh extension uninstall gfi
```

## Local development install

If you cloned the repo and want to test the extension locally before pushing:

```bash
cd /path/to/gfi
gh extension install .
```

This points `gh gfi` at your working tree, so changes to `src/gfi/cli.py` are picked up on the next invocation (no reinstall needed).

## How it works

The extension entry point is declared in `pyproject.toml`:

```toml
[project.scripts]
gfi = "gfi.cli:cli"
```

GitHub CLI discovers extensions by looking for an executable named `gh-<name>` in the installed package. The `gfi` package ships `gfi` as a script entry point; the `gh extension install` command wraps it so `gh gfi` and `gfi` behave identically.

## Pattern reference: `aipr`

This follows the same pattern as [`yunaremaia/aipr`](https://github.com/yunaremaia/aipr), which ships as `gh aipr`. See commit [df67b96](https://github.com/yunaremaia/aipr/commit/df67b96) ("feat: add GitHub CLI extension wrapper (gh aipr)") for the canonical implementation.

Both projects share the same author and the same extension-discovery convention, so once you've installed one, the other feels familiar.
