# gfi — Good First Issue Finder

Search and filter GitHub issues for contributors. Built for autonomous workflows and humans alike.

## Install

```bash
pip install gfi
```

Or from source:

```bash
git clone https://github.com/yunaremaia/gfi.git
cd gfi
pip install -e .
```

## Features

- **Smart search**: Auto-filters by `good first issue` label
- **Seen tracking**: Tracks seen issues to avoid repetition
- **Trending mode**: Scans popular repos for new opportunities
- **JSON & CSV export**: For automation, CI integration, and spreadsheet analysis
- **Rich terminal output**: Tables and panels

## Quick Start

```bash
# Search for good first issues
gfi search --language python --stars-min 100

# Search a specific repo
gfi repo anchore/grype --limit 5

# Trending issues across popular repos
gfi trending --limit 10

# Fresh feed (unseen issues only)
gfi feed --limit 20

# Open issue in browser
gfi open owner/repo 123

# Reset seen cache
gfi reset
```

## CLI Reference

### `gfi search`

Search globally for good first issues.

```bash
gfi search --language python --stars-min 100 --limit 10
gfi search --repos kubernetes/kubernetes --repos microsoft/vscode
gfi search --no-assigned  # Include assigned issues
gfi search --created-after 2026-08-01  # Recent issues only
```

### `gfi repo REPO`

List good first issues in a specific repository.

```bash
gfi repo anchore/grype --limit 10
gfi repo yunaremaia/driftcheck --json-output
```

### `gfi trending`

Show trending good first issues across popular repositories.

```bash
gfi trending --limit 20
gfi trending --json-output > trending.json
```

### `gfi feed`

Show a feed of unseen good first issues. Marks issues as seen automatically.

```bash
gfi feed --limit 20
gfi feed --limit 50 --json-output
```

### `gfi stats`

Show statistics about seen issues.

```bash
gfi stats
```

### `gfi reset`

Reset the seen issues cache. All issues become "fresh" again.

```bash
gfi reset
```

### `gfi open REPO NUMBER`

Open a GitHub issue in the browser.

```bash
gfi open yunaremaia/driftcheck 21
```

## JSON & CSV Output

All commands support `--json-output` for automation and `--csv` for spreadsheet analysis:

```bash
# JSON output
gfi search --limit 5 --json-output | jq '.[].title'

# CSV export
gfi search --limit 20 --csv > issues.csv
gfi repo yunaremaia/driftcheck --csv > driftcheck_issues.csv
gfi trending --limit 10 --csv > trending.csv
gfi feed --limit 20 --csv > feed.csv
```

CSV format includes: `number,title,repo,url,state,labels,stars,language`. Labels are space-separated within the `labels` column.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
