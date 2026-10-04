"""Regression tests for repo metadata lookups hitting a 404 (issue #75).

`quote(repo, safe="")` percent-encoded the `/` in `owner/repo`, so every
`gh api repos/owner%2Frepo` call returned 404 and the three helpers swallowed
the failure into falsy defaults (0, "", None).  `--stars-min` and
`--language` therefore rejected *every* repo.

Reported by @Jah-yee in #80.

`FakeGh` below reproduces GitHub's actual behaviour: an endpoint whose owner
and repo are joined by `%2F` 404s, a literal `/` returns data.  That lets the
filter code in `_search_repo` be exercised end to end without network access,
so these tests fail on the unfixed tree instead of only asserting a string.
"""
import json
from unittest.mock import patch

import pytest

from gfi.search import GitHubSearcher

# Ground truth for maziyarpanahi/openmed, measured against the live API.
REPO = "maziyarpanahi/openmed"
STARS = 5446
LANGUAGE = "Python"
PUSHED_AT = "2026-10-03T20:57:17Z"

_ISSUE = {
    "number": 1,
    "title": "probe issue",
    "url": f"https://github.com/{REPO}/issues/1",
    "state": "open",
    "labels": [{"name": "good first issue"}],
    "assignees": [],
    "createdAt": "2026-09-01T00:00:00Z",
    "updatedAt": "2026-09-05T00:00:00Z",
    "body": "",
    "commentsCount": 0,
}


def _result(returncode, stdout=""):
    r = type("Result", (), {})()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = ""
    return r


class FakeGh:
    """Stand-in for `gh` that 404s percent-encoded repo paths, like GitHub."""

    def __init__(self):
        self.api_calls = []

    def __call__(self, cmd, *args, **kwargs):
        if cmd[:3] == ["gh", "search", "issues"]:
            return _result(0, json.dumps([_ISSUE]))
        if cmd[:2] == ["gh", "api"]:
            endpoint = cmd[2]
            self.api_calls.append(endpoint)
            field = cmd[cmd.index("--jq") + 1]
            # The bug: `repos/owner%2Frepo` is not a valid repo path.
            if "%2F" in endpoint:
                return _result(1, "")
            if field == ".stargazers_count":
                return _result(0, f"{STARS}\n")
            if field == ".language":
                return _result(0, f'"{LANGUAGE}"\n')
            if field == ".pushed_at":
                return _result(0, f'"{PUSHED_AT}"\n')
        return _result(0, "")


@pytest.fixture
def searcher(tmp_path):
    return GitHubSearcher(cache_dir=tmp_path / "cache")


class TestSafeRepoPath:
    """The helper itself.

    Imported lazily so that on an unfixed tree these are the only tests that
    error -- every other test in this file still fails with a real assertion
    instead of the whole module failing to collect.
    """

    @staticmethod
    def _safe(repo):
        from gfi.search import _safe_repo_path

        return _safe_repo_path(repo)

    def test_preserves_separator(self):
        assert self._safe("owner/repo") == "owner/repo"

    def test_does_not_encode_separator_as_2f(self):
        assert "%2F" not in self._safe(REPO)

    def test_encodes_each_segment_individually(self):
        assert self._safe("owner name/repo name") == "owner%20name/repo%20name"

    def test_single_segment_is_still_encoded(self):
        assert self._safe("weird#name") == "weird%23name"


class TestCallSitesBuildAValidEndpoint:
    """All three call sites, not just one."""

    @patch("gfi.search.subprocess.run")
    def test_get_stars_uses_literal_separator(self, mock_run, searcher):
        mock_run.return_value = _result(0, "42\n")
        searcher._get_stars("owner/repo")
        assert "repos/owner/repo" in mock_run.call_args[0][0]

    @patch("gfi.search.subprocess.run")
    def test_get_language_uses_literal_separator(self, mock_run, searcher):
        mock_run.return_value = _result(0, '"Python"\n')
        searcher._get_language("owner/repo")
        assert "repos/owner/repo" in mock_run.call_args[0][0]

    @patch("gfi.search.subprocess.run")
    def test_get_repo_push_date_uses_literal_separator(self, mock_run, searcher):
        mock_run.return_value = _result(0, '"2026-10-03T20:57:17Z"\n')
        searcher._get_repo_push_date("owner/repo")
        assert "repos/owner/repo" in mock_run.call_args[0][0]


class TestNoPercentEncodedSeparator:
    """Source-level guard against the exact regression form (#46)."""

    def test_no_bare_quote_repo_safe_empty(self):
        import inspect

        import gfi.search as mod

        source = inspect.getsource(mod)
        offending = [
            line.strip()
            for line in source.splitlines()
            if "quote(repo" in line and 'safe=""' in line
        ]
        assert not offending, (
            "search.py builds a repo endpoint with quote(repo, safe=\"\"): "
            f"{offending}"
        )


class TestFiltersAcceptAQualifyingRepo:
    """The total-failure case: --stars-min and --language rejected everything."""

    def _run(self, searcher, **kwargs):
        args = {
            "query": "good first issue",
            "label": "good first issue",
            "state": "open",
            "language": None,
            "stars_min": None,
            "unassigned_only": True,
            "created_after": None,
        }
        args.update(kwargs)
        return list(searcher._search_repo(REPO, **args))

    def test_unfiltered_returns_the_issue(self, searcher):
        with patch("gfi.search.subprocess.run", FakeGh()):
            assert len(self._run(searcher)) == 1

    def test_stars_min_accepts_high_star_repo(self, searcher):
        """5446 stars must satisfy --stars-min 100."""
        with patch("gfi.search.subprocess.run", FakeGh()):
            assert len(self._run(searcher, stars_min=100)) == 1

    def test_language_accepts_matching_repo(self, searcher):
        with patch("gfi.search.subprocess.run", FakeGh()):
            assert len(self._run(searcher, language="Python")) == 1

    def test_stars_min_still_rejects_low_star_repo(self, searcher):
        """Positive control: the filter must still bite, not accept everything."""
        gh = FakeGh()
        gh_low = _result(0, "3\n")

        def run_low_stars(cmd, *a, **kw):
            if cmd[:2] == ["gh", "api"] and "%2F" not in cmd[2]:
                if ".stargazers_count" in cmd:
                    return gh_low
            return gh(cmd, *a, **kw)

        with patch("gfi.search.subprocess.run", run_low_stars):
            assert self._run(searcher, stars_min=100) == []

    def test_language_still_rejects_non_matching_repo(self, searcher):
        with patch("gfi.search.subprocess.run", FakeGh()):
            assert self._run(searcher, language="Rust") == []

    def test_metadata_is_not_defaulted_to_falsy(self, searcher):
        with patch("gfi.search.subprocess.run", FakeGh()):
            assert searcher._get_stars(REPO) == STARS
            assert searcher._get_language(REPO) == LANGUAGE
            assert searcher._get_repo_push_date(REPO) is not None

    def test_star_count_reaches_the_issue(self, searcher):
        with patch("gfi.search.subprocess.run", FakeGh()):
            issues = self._run(searcher)
            assert issues[0].stars == STARS
            assert issues[0].language == LANGUAGE