"""Regression tests for the --language filter being case-sensitive (issue #84).

`_get_language()` returns GitHub's canonical casing ("Python", "TypeScript",
...), but `_search_repo()` compared it against the user-supplied value with a
case-sensitive `!=`. The README's own example (`--language python`) is
lowercase, so the documented invocation matched nothing while the
undocumented capitalised form worked.

`FakeGh` below reproduces a real `gh api` round trip for a repo whose
language is "Python", so these tests exercise the real comparison in
`_search_repo` rather than asserting a string in isolation.
"""
import json
from unittest.mock import patch

import pytest

from gfi.search import GitHubSearcher

REPO = "psf/requests"
LANGUAGE = "Python"

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
    """Stand-in for `gh` reporting a repo whose GitHub language is "Python"."""

    def __call__(self, cmd, *args, **kwargs):
        if cmd[:3] == ["gh", "search", "issues"]:
            return _result(0, json.dumps([_ISSUE]))
        if cmd[:2] == ["gh", "api"]:
            field = cmd[cmd.index("--jq") + 1]
            if field == ".stargazers_count":
                return _result(0, "100\n")
            if field == ".language":
                return _result(0, f'"{LANGUAGE}"\n')
        return _result(0, "")


@pytest.fixture
def searcher(tmp_path):
    return GitHubSearcher(cache_dir=tmp_path / "cache")


def _run(searcher, language):
    return list(searcher._search_repo(
        REPO,
        query="good first issue",
        label="good first issue",
        state="open",
        language=language,
        stars_min=None,
        unassigned_only=True,
        created_after=None,
    ))


class TestLanguageFilterIsCaseInsensitive:
    @pytest.mark.parametrize("requested", ["python", "Python", "PYTHON", "pYthOn"])
    def test_matches_regardless_of_requested_casing(self, searcher, requested):
        with patch("gfi.search.subprocess.run", FakeGh()):
            assert len(_run(searcher, requested)) == 1

    def test_still_rejects_a_genuinely_different_language(self, searcher):
        """Positive control: the filter must still bite, not accept everything."""
        with patch("gfi.search.subprocess.run", FakeGh()):
            assert _run(searcher, "Rust") == []

    def test_no_language_filter_returns_the_issue(self, searcher):
        with patch("gfi.search.subprocess.run", FakeGh()):
            assert len(_run(searcher, None)) == 1
