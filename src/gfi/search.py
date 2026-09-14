"""Core search functionality for gfi — GitHub issue finder."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator


@dataclass
class Issue:
    """A GitHub issue with relevant metadata."""
    number: int
    title: str
    repo: str
    url: str
    state: str
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    body: str = ""
    language: str = ""
    stars: int = 0
    comments: int = 0

    @property
    def is_assigned(self) -> bool:
        return len(self.assignees) > 0

    @property
    def created_date(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def age_days(self) -> int | None:
        created = self.created_date
        if created is None:
            return None
        delta = datetime.now(created.tzinfo) - created
        return delta.days


class GitHubSearcher:
    """Search GitHub issues using gh CLI."""

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path("/tmp/gfi-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.seen_file = self.cache_dir / "seen.json"
        self._seen = self._load_seen()

    def _load_seen(self) -> set[str]:
        if self.seen_file.exists():
            try:
                return set(json.loads(self.seen_file.read_text()))
            except json.JSONDecodeError:
                pass
        return set()

    def _save_seen(self) -> None:
        self.seen_file.write_text(json.dumps(list(self._seen), indent=2))

    def _run_gh(self, args: list[str]) -> dict | list:
        """Run gh CLI and return JSON output."""
        cmd = ["gh", "api"] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return {} if "--json" in args else []
            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return {} if "--json" in args else []

    def _get_stars(self, repo: str) -> int:
        """Get star count for a repo."""
        cmd = ["gh", "api", f"repos/{repo}", "--jq", ".stargazers_count"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return int(result.stdout.strip())
        except (ValueError, subprocess.TimeoutExpired):
            pass
        return 0

    def _get_language(self, repo: str) -> str:
        """Get primary language for a repo."""
        cmd = ["gh", "api", f"repos/{repo}", "--jq", ".language"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                lang = result.stdout.strip().strip('"')
                return lang
        except subprocess.TimeoutExpired:
            pass
        return ""

    def search(
        self,
        query: str = "good first issue",
        label: str = "good first issue",
        state: str = "open",
        language: str | None = None,
        stars_min: int | None = None,
        unassigned_only: bool = True,
        created_after: str | None = None,
        limit: int = 20,
        repos: list[str] | None = None,
    ) -> Iterator[Issue]:
        """Search for issues matching criteria.

        Args:
            query: Search query text
            label: Label to filter by (e.g., "good first issue")
            state: Issue state ("open", "closed", "all")
            language: Filter by programming language
            stars_min: Minimum repo stars
            unassigned_only: Only return unassigned issues
            created_after: ISO date (e.g., "2026-08-01")
            limit: Max results
            repos: Specific repos to search (e.g., ["owner/repo"])
        """
        if repos:
            for repo in repos:
                yield from self._search_repo(
                    repo, query, label, state, language,
                    stars_min, unassigned_only, created_after, limit
                )
        else:
            yield from self._search_global(
                query, label, state, language,
                stars_min, unassigned_only, created_after, limit
            )

    def _search_repo(
        self,
        repo: str,
        query: str,
        label: str,
        state: str,
        language: str | None,
        stars_min: int | None,
        unassigned_only: bool,
        created_after: str | None,
        limit: int,
    ) -> Iterator[Issue]:
        """Search within a specific repo."""
        # First check stars threshold
        stars = self._get_stars(repo)
        if stars_min and stars < stars_min:
            return
        if language and self._get_language(repo) != language:
            return

        # Build search query - use hyphenated label form (GitHub search compatible)
        label_alt = label.replace(" ", "-")

        search_query_parts = [
            f"repo:{repo}",
            "is:issue",
            f"label:{label_alt}",
            f"state:{state}",
        ]
        if created_after:
            search_query_parts.append(f"created:>={created_after}")

        # gh search needs each term as separate arg, not a single string
        cmd = [
            "gh", "search", "issues",
            *search_query_parts,
            "--json", "number,title,url,state,labels,assignees,createdAt,updatedAt,body,commentsCount",
            "--limit", str(limit),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return
            items = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return

        for item in items:
            issue = Issue(
                number=item.get("number", 0),
                title=item.get("title", ""),
                repo=repo,
                url=item.get("url", ""),
                state=item.get("state", ""),
                labels=[l.get("name", "") for l in item.get("labels", [])],
                assignees=[a.get("login", "") for a in item.get("assignees", [])],
                created_at=item.get("createdAt", ""),
                updated_at=item.get("updatedAt", ""),
                body=(item.get("body") or "")[:500],
                language=self._get_language(repo),
                stars=stars,
                comments=item.get("commentsCount", 0),
            )

            if unassigned_only and issue.is_assigned:
                continue
            yield issue



    def _search_global(
        self,
        query: str,
        label: str,
        state: str,
        language: str | None,
        stars_min: int | None,
        unassigned_only: bool,
        created_after: str | None,
        limit: int,
    ) -> Iterator[Issue]:
        """Search globally across GitHub."""
        # Build search query - use hyphenated label form (GitHub search compatible)
        label_alt = label.replace(" ", "-")
        search_terms = [
            "is:issue",
            f"label:{label_alt}",
            f"state:{state}",
            "no:assignee",
        ]
        if language:
            search_terms.append(f"language:{language}")
        if created_after:
            search_terms.append(f"created:>={created_after}")

        # gh search needs each term as separate arg, not a single string
        cmd = [
            "gh", "search", "issues",
            *search_terms,
            "--json", "number,title,repository,url,state,labels,assignees,createdAt,updatedAt,body,commentsCount",
            "--sort", "updated",
            "--limit", str(limit),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return
            items = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return

        for item in items:
            repo = item.get("repository", {}).get("nameWithOwner", "")
            stars = self._get_stars(repo) if repo else 0

            if stars_min and stars < stars_min:
                continue

            issue = Issue(
                number=item.get("number", 0),
                title=item.get("title", ""),
                repo=repo,
                url=item.get("url", ""),
                state=item.get("state", ""),
                labels=[l.get("name", "") for l in item.get("labels", [])],
                assignees=[a.get("login", "") for a in item.get("assignees", [])],
                created_at=item.get("createdAt", ""),
                updated_at=item.get("updatedAt", ""),
                body=(item.get("body") or "")[:500],
                language=self._get_language(repo) if repo else "",
                stars=stars,
                comments=item.get("commentsCount", 0),
            )

            if unassigned_only and issue.is_assigned:
                continue
            yield issue

    def mark_seen(self, issue: Issue) -> None:
        """Mark an issue as seen."""
        key = f"{issue.repo}#{issue.number}"
        self._seen.add(key)
        self._save_seen()

    def is_seen(self, issue: Issue) -> bool:
        """Check if issue was previously seen."""
        key = f"{issue.repo}#{issue.number}"
        return key in self._seen

    def filter_unseen(self, issues: Iterator[Issue]) -> Iterator[Issue]:
        """Yield only issues not previously seen."""
        for issue in issues:
            if not self.is_seen(issue):
                yield issue


class HotTopics:
    """Track trending topics for good-first-issues."""

    TRENDING_QUERIES = [
        "good first issue",
        "help wanted",
        "beginner friendly",
        "easy fix",
        "documentation",
    ]

    POPULAR_LANGUAGES = [
        "python", "typescript", "rust", "go", "javascript",
        "java", "c++", "c", "ruby", "swift",
    ]

    ORGANIZATIONS = [
        "kubernetes", "microsoft", "google", "vercel", "sigstore",
        "anchore", "cilium", "guacsec", "hiero-ledger",
    ]
