"""CLI for gfi — Good First Issue finder."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from gfi.search import GitHubSearcher, Issue

console = Console()

CSV_COLUMNS = (
    "number",
    "title",
    "repo",
    "url",
    "labels",
    "created_at",
    "comments",
    "stars",
)


def _write_csv(issues: list[Issue]) -> None:
    """Write issues as CSV to standard output."""
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for issue in issues:
        writer.writerow((
            issue.number,
            issue.title,
            issue.repo,
            issue.url,
            ", ".join(issue.labels),
            issue.created_at,
            issue.comments,
            issue.stars,
        ))


def _format_date(date_str: str) -> str:
    """Format ISO date to readable string."""
    if not date_str:
        return "—"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10]


def _truncate(text: str, length: int = 60) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= length:
        return text
    return text[:length-3] + "..."


@click.group()
@click.version_option(package_name="gfi")
def cli():
    """gfi — Good First Issue finder for GitHub contributors."""
    pass


@cli.command()
@click.option("--query", "-q", default="good first issue", help="Search query")
@click.option("--label", "-l", default="good first issue", help="Label to filter")
@click.option("--language", "-L", default=None, help="Programming language filter")
@click.option("--stars-min", "-s", default=None, type=int, help="Minimum repo stars")
@click.option("--limit", "-n", default=20, help="Max results")
@click.option("--json-output", "json_out", is_flag=True, help="Output as JSON")
@click.option("--csv", "csv_out", is_flag=True, help="Output as CSV")
@click.option("--no-assigned/--assigned", default=True, help="Exclude assigned issues")
@click.option("--created-after", default=None, help="Created after date (YYYY-MM-DD)")
@click.option("--repos", "-r", multiple=True, help="Specific repos to search")
@click.option("--seen/--no-seen", default=True, help="Show only unseen issues")
def search(
    query, label, language, stars_min, limit, json_out, csv_out,
    no_assigned, created_after, repos, seen
):
    """Search for good first issues on GitHub."""
    searcher = GitHubSearcher()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        disable=csv_out,
    ) as progress:
        task = progress.add_task("Searching GitHub...", total=None)

        results = list(searcher.search(
            query=query,
            label=label,
            language=language,
            stars_min=stars_min,
            unassigned_only=no_assigned,
            created_after=created_after,
            limit=limit,
            repos=list(repos) if repos else None,
        ))

        if seen:
            results = [r for r in results if not searcher.is_seen(r)]

        progress.update(task, completed=True)

    if not results:
        console.print("[yellow]No issues found matching criteria.[/yellow]")
        return

    if json_out:
        output = []
        for issue in results:
            output.append({
                "number": issue.number,
                "title": issue.title,
                "repo": issue.repo,
                "url": issue.url,
                "labels": issue.labels,
                "stars": issue.stars,
                "language": issue.language,
                "created": issue.created_at,
                "age_days": issue.age_days(),
            })
        click.echo(json.dumps(output, indent=2))
        return

    if csv_out:
        _write_csv(results)
        return

    console.print(Panel(
        f"[bold]Found {len(results)} issues[/bold]",
        title="gfi — Search Results"
    ))

    table = Table(title="Good First Issues")
    table.add_column("#", style="cyan", width=6)
    table.add_column("Title", width=50)
    table.add_column("Repo", width=25)
    table.add_column("Stars", justify="right", width=8)
    table.add_column("Lang", width=10)
    table.add_column("Age", justify="right", width=6)

    for issue in results:
        table.add_row(
            str(issue.number),
            _truncate(issue.title, 48),
            _truncate(issue.repo, 23),
            f"⭐ {issue.stars}" if issue.stars else "—",
            issue.language or "—",
            f"{issue.age_days()}d" if issue.age_days() is not None else "—",
        )

    console.print(table)


@cli.command()
@click.argument("repo")
@click.option("--limit", "-n", default=10, help="Max results")
@click.option("--json-output", "json_out", is_flag=True, help="Output as JSON")
@click.option("--csv", "csv_out", is_flag=True, help="Output as CSV")
def repo(repo, limit, json_out, csv_out):
    """List good first issues in a specific repo."""
    searcher = GitHubSearcher()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        disable=csv_out,
    ) as progress:
        task = progress.add_task(f"Searching {repo}...", total=None)

        results = list(searcher.search(
            repos=[repo],
            limit=limit,
        ))

        progress.update(task, completed=True)

    if not results:
        console.print(f"[yellow]No good first issues found in {repo}.[/yellow]")
        return

    if json_out:
        output = []
        for issue in results:
            output.append({
                "number": issue.number,
                "title": issue.title,
                "url": issue.url,
                "labels": issue.labels,
                "assignees": issue.assignees,
                "body": issue.body,
            })
        click.echo(json.dumps(output, indent=2))
        return

    if csv_out:
        _write_csv(results)
        return

    console.print(Panel(
        f"[bold]{repo}[/bold] — {len(results)} issues",
        title="gfi — Repo Issues"
    ))

    table = Table()
    table.add_column("#", style="cyan", width=6)
    table.add_column("Title", width=60)
    table.add_column("Labels", width=30)

    for issue in results:
        labels = ", ".join(issue.labels[:3])
        table.add_row(
            str(issue.number),
            _truncate(issue.title, 58),
            _truncate(labels, 28),
        )

    console.print(table)


@cli.command()
@click.option("--limit", "-n", default=10, help="Max results per topic")
@click.option("--json-output", "json_out", is_flag=True, help="Output as JSON")
@click.option("--csv", "csv_out", is_flag=True, help="Output as CSV")
def trending(limit, json_out, csv_out):
    """Show trending good first issues across popular repos."""
    searcher = GitHubSearcher()

    # Popular repos with good first issues
    repos = [
        "kubernetes/kubernetes",
        "microsoft/vscode",
        "vercel/next.js",
        "sigstore/cosign",
        "anchore/grype",
        "cilium/cilium",
        "guacsec/guac",
    ]

    all_issues = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        disable=csv_out,
    ) as progress:
        task = progress.add_task("Scanning trending repos...", total=len(repos))

        for repo in repos:
            progress.update(task, description=f"Scanning {repo}...")
            issues = list(searcher.search(repos=[repo], limit=limit))
            all_issues.extend(issues)
            progress.advance(task)

    if not all_issues:
        console.print("[yellow]No trending issues found.[/yellow]")
        return

    # Sort by stars descending
    all_issues.sort(key=lambda x: x.stars, reverse=True)

    if json_out:
        output = []
        for issue in all_issues[:limit]:
            output.append({
                "number": issue.number,
                "title": issue.title,
                "repo": issue.repo,
                "url": issue.url,
                "stars": issue.stars,
            })
        click.echo(json.dumps(output, indent=2))
        return

    if csv_out:
        _write_csv(all_issues[:limit])
        return

    console.print(Panel(
        f"[bold]Trending Good First Issues[/bold]\n{len(all_issues)} issues across {len(repos)} repos",
        title="gfi — Trending"
    ))

    table = Table()
    table.add_column("#", style="cyan", width=6)
    table.add_column("Title", width=50)
    table.add_column("Repo", width=25)
    table.add_column("Stars", justify="right", width=8)

    for issue in all_issues[:limit]:
        table.add_row(
            str(issue.number),
            _truncate(issue.title, 48),
            _truncate(issue.repo, 23),
            f"⭐ {issue.stars}",
        )

    console.print(table)


@cli.command()
@click.option("--limit", "-n", default=20, help="Max results")
@click.option("--json-output", "json_out", is_flag=True, help="Output as JSON")
def feed(limit, json_out):
    """Show a feed of new good first issues (unseen)."""
    searcher = GitHubSearcher()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching feed...", total=None)

        results = list(searcher.search(
            limit=limit * 2,  # Fetch more to filter unseen
        ))
        results = [r for r in results if not searcher.is_seen(r)][:limit]

        progress.update(task, completed=True)

    if not results:
        console.print("[yellow]No new issues. Try again later![/yellow]")
        return

    if json_out:
        output = []
        for issue in results:
            output.append({
                "number": issue.number,
                "title": issue.title,
                "repo": issue.repo,
                "url": issue.url,
                "stars": issue.stars,
                "language": issue.language,
            })
        click.echo(json.dumps(output, indent=2))
        return

    console.print(Panel(
        f"[bold]Fresh Feed[/bold] — {len(results)} new issues",
        title="gfi — Feed"
    ))

    table = Table(show_lines=True)
    table.add_column("#", style="cyan", width=6)
    table.add_column("Title", width=50)
    table.add_column("Repo", width=25)
    table.add_column("Stars", justify="right", width=8)
    table.add_column("Lang", width=10)

    for issue in results:
        table.add_row(
            str(issue.number),
            _truncate(issue.title, 48),
            _truncate(issue.repo, 23),
            f"⭐ {issue.stars}" if issue.stars else "—",
            issue.language or "—",
        )

    console.print(table)

    # Mark as seen
    for issue in results:
        searcher.mark_seen(issue)


@cli.command()
def stats():
    """Show statistics about seen issues."""
    searcher = GitHubSearcher()
    seen_count = len(searcher._seen)

    console.print(Panel(
        f"Total issues seen: [bold]{seen_count}[/bold]",
        title="gfi — Stats"
    ))


@cli.command()
def reset():
    """Reset seen issues cache."""
    searcher = GitHubSearcher()
    searcher._seen.clear()
    searcher._save_seen()
    console.print("[green]Cache reset. All issues are fresh again.[/green]")


@cli.command()
@click.argument("repo")
@click.argument("number", type=int)
def open(repo, number):
    """Open a GitHub issue in the browser."""
    import subprocess
    url = f"https://github.com/{repo}/issues/{number}"
    subprocess.run(["xdg-open", url], capture_output=True)
    console.print(f"[dim]Opened: {url}[/dim]")
