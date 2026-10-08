"""Encoding tests: user-supplied search terms must reach GitHub unaltered.

The search backend is invoked as a `gh search issues` subprocess whose argv list
*is* the wire representation of the query. If a user-supplied `query` or `label`
is interpolated raw into that argv, spaces, quotes, slashes, `&` and `#` are
re-interpreted by GitHub's search parser instead of being passed through as data,
which silently yields wrong or empty result sets.

These tests assert on the argv the fake subprocess client receives. They never
touch the network.
"""
import json
import subprocess
from unittest.mock import patch

import pytest

from gfi.search import GitHubSearcher


def _gh_result(returncode=0, stdout="[]"):
    result = type("Result", (), {})()
    result.returncode = returncode
    result.stdout = stdout
    return result


@pytest.fixture
def searcher(tmp_path):
    s = GitHubSearcher(cache_dir=tmp_path / "cache")
    s._get_stars = lambda repo: 100
    s._get_language = lambda repo: "Python"
    return s


def _search_argv(mock_run):
    """Return the argv list handed to the (fake) gh client."""
    return mock_run.call_args[0][0]


def _search_query_args(mock_run):
    """Positional search terms: everything between 'issues' and '--json'."""
    cmd = _search_argv(mock_run)
    start = cmd.index("issues") + 1
    return cmd[start:cmd.index("--json")]


class TestLabelQualifierEncoding:
    """A label with a space must stay one quoted qualifier, not be mangled."""

    @patch("gfi.search.subprocess.run")
    def test_label_with_space_is_quoted_not_hyphenated(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="[]")

        list(searcher._search_global(
            "query", "good first issue", "open", None, None, True, None,
            max_age_days=None, repo_max_age_days=None, limit=20,
        ))

        terms = _search_query_args(mock_run)
        # gh adds the quotes when it builds q=, so the value goes in bare.
        assert "label:good first issue" in terms
        # The hyphen-mangling workaround silently searches a different label.
        assert "label:good-first-issue" not in terms

    @patch("gfi.search.subprocess.run")
    def test_label_with_quote_is_escaped_and_cannot_break_out(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="[]")

        list(searcher._search_global(
            "query", 'needs "urgent" triage', "open", None, None, True, None,
            max_age_days=None, repo_max_age_days=None, limit=20,
        ))

        terms = _search_query_args(mock_run)
        assert len([t for t in terms if t.startswith("label:")]) == 1
        label_term = next(t for t in terms if t.startswith("label:"))
        # The embedded quotes are data, kept as one argv element: gh escapes
        # them when it composes q=, so adding our own backslashes would
        # double-escape and match nothing (#82).
        assert label_term == 'label:needs "urgent" triage'
        assert "\\" not in label_term
        assert "state:open" in terms

    @patch("gfi.search.subprocess.run")
    def test_label_with_colon_and_paren_survives_as_one_term(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="[]")

        list(searcher._search_global(
            "query", "type: bug (fix|chore)", "open", None, None, True, None,
            max_age_days=None, repo_max_age_days=None, limit=20,
        ))

        terms = _search_query_args(mock_run)
        assert "label:type: bug (fix|chore)" in terms

    @patch("gfi.search.subprocess.run")
    def test_repo_search_labels_label_the_same_way(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="[]")

        list(searcher._search_repo(
            "owner/repo", "query", "good first issue", "open", None,
            None, True, None,
            max_age_days=None, repo_max_age_days=None, limit=20,
        ))

        terms = _search_query_args(mock_run)
        assert "label:good first issue" in terms
        assert "label:good-first-issue" not in terms


class TestNoDoubleEscaping:
    """gh quotes argv terms itself; adding our own quotes breaks the query.

    Regression for #82, where every search silently returned zero results with
    exit code 0. Both search paths route through ``search_qualifier``, so one
    test covers the shared choke point and its two callers.
    """

    @patch("gfi.search.subprocess.run")
    def test_search_terms_carry_no_added_quotes_or_backslashes(
        self, mock_run, searcher
    ):
        mock_run.return_value = _gh_result(stdout="[]")

        list(searcher._search_global(
            "query", 'needs "urgent" triage', "open", "Python", None, True, None,
            max_age_days=None, repo_max_age_days=None, limit=20,
        ))
        global_terms = _search_query_args(mock_run)

        list(searcher._search_repo(
            "owner/repo", "query", "good first issue", "open", None,
            None, True, None,
            max_age_days=None, repo_max_age_days=None, limit=20,
        ))
        repo_terms = _search_query_args(mock_run)

        # gh quotes and escapes each argv term when it builds q=, so our value
        # must go in bare. Pre-quoting made GitHub receive the literal
        # \"good first issue\", which matches no label.
        assert "label:needs \"urgent\" triage" in global_terms
        assert "language:Python" in global_terms
        assert "label:good first issue" in repo_terms
        for terms in (global_terms, repo_terms):
            assert not any("\\" in t for t in terms), (
                f"gh already escapes argv terms; a backslash here means we are "
                f"double-escaping: {terms}"
            )

    def test_quote_search_value_does_not_exist(self):
        """Guard against re-introducing the double-escaping bug.

        The ``quote_search_value`` function was removed in the fix for #82.
        If someone re-adds it, this test fails immediately.
        """
        import gfi.search as search_module
        assert not hasattr(search_module, "quote_search_value"), (
            "quote_search_value was re-introduced; it double-escapes values "
            "and causes every search to return zero results (#82)"
        )

    def test_search_qualifier_returns_bare_value(self):
        """search_qualifier must not add quotes around the value."""
        from gfi.search import search_qualifier
        assert search_qualifier("label", "good first issue") == "label:good first issue"
        assert search_qualifier("label", "simple") == "label:simple"
        assert search_qualifier("language", "Python") == "language:Python"


class TestFreeTextQueryIntegrity:
    """The free-text query is data: it must arrive as exactly one argv element."""

    @patch("gfi.search.subprocess.run")
    def test_query_with_spaces_quotes_and_slash_is_one_argv_element(
        self, mock_run, searcher
    ):
        mock_run.return_value = _gh_result(stdout="[]")
        query = 'repo:owner/repo title:"fix: parser bug"'

        list(searcher._search_global(
            query, "good first issue", "open", None, None, True, None,
            max_age_days=None, repo_max_age_days=None, limit=20,
        ))

        terms = _search_query_args(mock_run)
        assert query in terms
        assert terms.count(query) == 1

    @patch("gfi.search.subprocess.run")
    def test_ampersand_in_query_cannot_inject_a_new_qualifier(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="[]")
        query = "parser & state:closed"

        list(searcher._search_global(
            query, "good first issue", "open", None, None, True, None,
            max_age_days=None, repo_max_age_days=None, limit=20,
        ))

        terms = _search_query_args(mock_run)
        # The whole string stays one element, so the & is data, not a separator.
        assert query in terms
        assert "state:closed" not in terms
        # Only the intended state qualifier is present.
        assert [t for t in terms if t.startswith("state:")] == ["state:open"]

    @patch("gfi.search.subprocess.run")
    def test_hash_in_query_is_not_truncated(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="[]")
        query = "fix #42 regression"

        list(searcher._search_global(
            query, "good first issue", "open", None, None, True, None,
            max_age_days=None, repo_max_age_days=None, limit=20,
        ))

        terms = _search_query_args(mock_run)
        assert "fix #42 regression" in terms
        assert not any("#" not in t and "42" in t for t in terms)

    @patch("gfi.search.subprocess.run")
    def test_empty_query_does_not_produce_an_empty_argv_element(
        self, mock_run, searcher
    ):
        mock_run.return_value = _gh_result(stdout="[]")

        list(searcher._search_global(
            "", "good first issue", "open", None, None, True, None,
            max_age_days=None, repo_max_age_days=None, limit=20,
        ))

        terms = _search_query_args(mock_run)
        assert "" not in terms


class TestEncodedTermsStillYieldIssues:
    """End-to-end: an exotic query must not break result parsing."""

    @patch("gfi.search.subprocess.run")
    def test_results_are_parsed_for_encoded_query(self, mock_run, searcher):
        payload = json.dumps([{
            "number": 41,
            "title": 'Fix: parser "bug" & more',
            "repository": {"nameWithOwner": "owner/repo"},
            "url": "https://github.com/owner/repo/issues/41",
            "state": "open",
            "labels": [{"name": "needs urgent triage"}],
            "assignees": [],
            "createdAt": "",
            "updatedAt": "",
            "body": "",
            "commentsCount": 0,
        }])
        mock_run.return_value = _gh_result(stdout=payload)

        results = list(searcher._search_global(
            'repo:owner/repo title:"bug"', "needs urgent triage", "open",
            None, None, True, None,
            max_age_days=None, repo_max_age_days=None, limit=20,
        ))

        assert [i.number for i in results] == [41]
        assert results[0].labels == ["needs urgent triage"]

    def test_searcher_handles_timeout_with_encoded_query(self, searcher):
        with patch(
            "gfi.search.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=30),
        ):
            results = list(searcher._search_global(
                'repo:owner/repo title:"bug"', "needs urgent triage", "open",
                None, None, True, None,
                max_age_days=None, repo_max_age_days=None, limit=20,
            ))

        assert results == []