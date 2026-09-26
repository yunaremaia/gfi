"""Tests for gfi search."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from gfi.search import GitHubSearcher, Issue


class TestIssue:
    @pytest.fixture
    def issue(self):
        return Issue(
            number=123,
            title="Test issue",
            repo="owner/repo",
            url="https://github.com/owner/repo/issues/123",
            state="open",
            labels=["good first issue", "enhancement"],
            assignees=[],
            created_at="2026-09-01T00:00:00Z",
            updated_at="2026-09-05T00:00:00Z",
            stars=500,
            language="python",
        )

    def test_is_assigned_false(self, issue):
        assert issue.is_assigned is False

    def test_is_assigned_true(self, issue):
        issue.assignees = ["someone"]
        assert issue.is_assigned is True

    def test_created_date(self, issue):
        assert issue.created_date is not None

    def test_age_days(self, issue):
        age = issue.age_days()
        assert age is not None
        assert age > 0

    def test_age_days_none(self, issue):
        issue.created_at = ""
        assert issue.age_days() is None


class TestGitHubSearcher:
    @pytest.fixture
    def searcher(self, tmp_path):
        return GitHubSearcher(cache_dir=tmp_path / "cache")

    def test_init_creates_dir(self, searcher):
        assert searcher.cache_dir.exists()

    def test_load_seen_empty(self, searcher):
        assert len(searcher._seen) == 0

    def test_mark_seen(self, searcher):
        issue = Issue(number=1, title="test", repo="a/b", url="", state="open")
        searcher.mark_seen(issue)
        assert searcher.is_seen(issue)

    def test_filter_unseen(self, searcher):
        issues = [
            Issue(number=i, title=f"issue-{i}", repo="a/b", url="", state="open")
            for i in range(5)
        ]
        searcher.mark_seen(issues[0])
        searcher.mark_seen(issues[2])
        unseen = list(searcher.filter_unseen(iter(issues)))
        assert len(unseen) == 3


class TestSeenPersistence:
    def test_save_and_load(self, tmp_path):
        searcher1 = GitHubSearcher(cache_dir=tmp_path / "cache")
        issue = Issue(number=42, title="test", repo="x/y", url="", state="open")
        searcher1.mark_seen(issue)
        searcher2 = GitHubSearcher(cache_dir=tmp_path / "cache")
        assert searcher2.is_seen(issue)


def _gh_result(returncode=0, stdout="[]"):
    result = type("Result", (), {})()
    result.returncode = returncode
    result.stdout = stdout
    return result


class TestGetStars:
    @pytest.fixture
    def searcher(self, tmp_path):
        return GitHubSearcher(cache_dir=tmp_path / "cache")

    @patch("gfi.search.subprocess.run")
    def test_returns_star_count(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="42\n")

        assert searcher._get_stars("owner/repo") == 42
        cmd = mock_run.call_args[0][0]
        assert "repos/owner%2Frepo" in cmd

    @patch("gfi.search.subprocess.run")
    def test_returns_zero_on_nonzero_exit(self, mock_run, searcher):
        mock_run.return_value = _gh_result(returncode=1, stdout="")

        assert searcher._get_stars("owner/repo") == 0

    def test_returns_zero_on_timeout(self, searcher):
        with patch("gfi.search.subprocess.run",
                    side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=10)):
            assert searcher._get_stars("owner/repo") == 0

    @patch("gfi.search.subprocess.run")
    def test_returns_zero_on_unparseable_output(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="null")

        assert searcher._get_stars("owner/repo") == 0


class TestGetLanguage:
    @pytest.fixture
    def searcher(self, tmp_path):
        return GitHubSearcher(cache_dir=tmp_path / "cache")

    @patch("gfi.search.subprocess.run")
    def test_returns_language(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout='"Python"\n')

        assert searcher._get_language("owner/repo") == "Python"
        cmd = mock_run.call_args[0][0]
        assert "repos/owner%2Frepo" in cmd

    @patch("gfi.search.subprocess.run")
    def test_returns_empty_on_nonzero_exit(self, mock_run, searcher):
        mock_run.return_value = _gh_result(returncode=1, stdout="")

        assert searcher._get_language("owner/repo") == ""

    def test_returns_empty_on_timeout(self, searcher):
        with patch("gfi.search.subprocess.run",
                    side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=10)):
            assert searcher._get_language("owner/repo") == ""


class TestSearchDispatch:
    @pytest.fixture
    def searcher(self, tmp_path):
        return GitHubSearcher(cache_dir=tmp_path / "cache")

    def test_search_with_repos_uses_search_repo(self, searcher, monkeypatch):
        calls = []

        def fake_search_repo(self, repo, *args, **kwargs):
            calls.append(repo)
            return iter([])

        monkeypatch.setattr(GitHubSearcher, "_search_repo", fake_search_repo)
        list(searcher.search(repos=["a/b", "c/d"]))

        assert calls == ["a/b", "c/d"]

    def test_search_without_repos_uses_search_global(self, searcher, monkeypatch):
        calls = []

        def fake_search_global(self, *args, **kwargs):
            calls.append(True)
            return iter([])

        monkeypatch.setattr(GitHubSearcher, "_search_global", fake_search_global)
        list(searcher.search())

        assert calls == [True]


class TestSearchRepo:
    @pytest.fixture
    def searcher(self, tmp_path):
        s = GitHubSearcher(cache_dir=tmp_path / "cache")
        s._get_stars = lambda repo: 100
        s._get_language = lambda repo: "Python"
        return s

    @patch("gfi.search.subprocess.run")
    def test_builds_command_with_hyphenated_label_and_repo(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="[]")

        list(searcher._search_repo(
            "owner/repo", "query", "good first issue", "open", None,
            None, True, None, limit=20,
        ))

        cmd = mock_run.call_args[0][0]
        assert "repo:owner/repo" in cmd
        assert "is:issue" in cmd
        assert "label:good-first-issue" in cmd
        assert "state:open" in cmd
        assert not any(part.startswith("created:") for part in cmd)

    @patch("gfi.search.subprocess.run")
    def test_adds_created_after_term(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="[]")

        list(searcher._search_repo(
            "owner/repo", "query", "good first issue", "open", None,
            None, True, "2026-08-01", limit=20,
        ))

        cmd = mock_run.call_args[0][0]
        assert "created:>=2026-08-01" in cmd

    @patch("gfi.search.subprocess.run")
    def test_skips_repo_below_stars_min_without_calling_gh(self, mock_run, searcher):
        results = list(searcher._search_repo(
            "owner/repo", "query", "good first issue", "open", None,
            stars_min=200, unassigned_only=True, created_after=None, limit=20,
        ))

        assert results == []
        mock_run.assert_not_called()

    @patch("gfi.search.subprocess.run")
    def test_skips_repo_with_mismatched_language(self, mock_run, searcher):
        results = list(searcher._search_repo(
            "owner/repo", "query", "good first issue", "open", "Rust",
            None, True, None, limit=20,
        ))

        assert results == []
        mock_run.assert_not_called()

    @patch("gfi.search.subprocess.run")
    def test_yields_issues_from_gh_json(self, mock_run, searcher):
        payload = json.dumps([{
            "number": 7,
            "title": "Fix bug",
            "url": "https://github.com/owner/repo/issues/7",
            "state": "open",
            "labels": [{"name": "good first issue"}, {"name": "bug"}],
            "assignees": [],
            "createdAt": "2026-08-01T00:00:00Z",
            "updatedAt": "2026-08-02T00:00:00Z",
            "body": "some body text",
            "commentsCount": 3,
        }])
        mock_run.return_value = _gh_result(stdout=payload)

        results = list(searcher._search_repo(
            "owner/repo", "query", "good first issue", "open", None,
            None, True, None, limit=20,
        ))

        assert len(results) == 1
        issue = results[0]
        assert issue.number == 7
        assert issue.repo == "owner/repo"
        assert issue.labels == ["good first issue", "bug"]
        assert issue.stars == 100
        assert issue.language == "Python"
        assert issue.comments == 3

    @patch("gfi.search.subprocess.run")
    def test_excludes_assigned_issues_when_unassigned_only(self, mock_run, searcher):
        payload = json.dumps([{
            "number": 8,
            "title": "Taken",
            "url": "https://github.com/owner/repo/issues/8",
            "state": "open",
            "labels": [],
            "assignees": [{"login": "someone"}],
            "createdAt": "",
            "updatedAt": "",
            "body": "",
            "commentsCount": 0,
        }])
        mock_run.return_value = _gh_result(stdout=payload)

        results = list(searcher._search_repo(
            "owner/repo", "query", "good first issue", "open", None,
            None, True, None, limit=20,
        ))

        assert results == []

    @patch("gfi.search.subprocess.run")
    def test_returns_nothing_on_nonzero_exit(self, mock_run, searcher):
        mock_run.return_value = _gh_result(returncode=1, stdout="")

        results = list(searcher._search_repo(
            "owner/repo", "query", "good first issue", "open", None,
            None, True, None, limit=20,
        ))

        assert results == []

    @patch("gfi.search.subprocess.run")
    def test_returns_nothing_on_malformed_json(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="not json")

        results = list(searcher._search_repo(
            "owner/repo", "query", "good first issue", "open", None,
            None, True, None, limit=20,
        ))

        assert results == []

    def test_returns_nothing_on_timeout(self, searcher):
        with patch("gfi.search.subprocess.run",
                    side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=30)):
            results = list(searcher._search_repo(
                "owner/repo", "query", "good first issue", "open", None,
                None, True, None, limit=20,
            ))

        assert results == []


class TestSearchGlobal:
    @pytest.fixture
    def searcher(self, tmp_path):
        s = GitHubSearcher(cache_dir=tmp_path / "cache")
        s._get_stars = lambda repo: 50
        s._get_language = lambda repo: "Python"
        return s

    @patch("gfi.search.subprocess.run")
    def test_builds_command_with_no_assignee_and_hyphenated_label(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="[]")

        list(searcher._search_global(
            "query", "good first issue", "open", None, None, True, None, limit=20,
        ))

        cmd = mock_run.call_args[0][0]
        assert "is:issue" in cmd
        assert "label:good-first-issue" in cmd
        assert "state:open" in cmd
        assert "no:assignee" in cmd

    @patch("gfi.search.subprocess.run")
    def test_adds_language_and_created_after_terms(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="[]")

        list(searcher._search_global(
            "query", "good first issue", "open", "Python", None, True,
            "2026-08-01", limit=20,
        ))

        cmd = mock_run.call_args[0][0]
        assert "language:Python" in cmd
        assert "created:>=2026-08-01" in cmd

    @patch("gfi.search.subprocess.run")
    def test_extracts_repo_from_repository_field(self, mock_run, searcher):
        payload = json.dumps([{
            "number": 9,
            "title": "Global issue",
            "repository": {"nameWithOwner": "owner/repo"},
            "url": "https://github.com/owner/repo/issues/9",
            "state": "open",
            "labels": [],
            "assignees": [],
            "createdAt": "",
            "updatedAt": "",
            "body": "",
            "commentsCount": 0,
        }])
        mock_run.return_value = _gh_result(stdout=payload)

        results = list(searcher._search_global(
            "query", "good first issue", "open", None, None, True, None, limit=20,
        ))

        assert len(results) == 1
        assert results[0].repo == "owner/repo"
        assert results[0].stars == 50
        assert results[0].language == "Python"

    @patch("gfi.search.subprocess.run")
    def test_filters_by_stars_min_after_fetch(self, mock_run, searcher):
        payload = json.dumps([{
            "number": 10,
            "title": "Too small",
            "repository": {"nameWithOwner": "owner/repo"},
            "url": "",
            "state": "open",
            "labels": [],
            "assignees": [],
            "createdAt": "",
            "updatedAt": "",
            "body": "",
            "commentsCount": 0,
        }])
        mock_run.return_value = _gh_result(stdout=payload)

        results = list(searcher._search_global(
            "query", "good first issue", "open", None, stars_min=100,
            unassigned_only=True, created_after=None, limit=20,
        ))

        assert results == []

    @patch("gfi.search.subprocess.run")
    def test_excludes_assigned_issues_when_unassigned_only(self, mock_run, searcher):
        payload = json.dumps([{
            "number": 11,
            "title": "Taken",
            "repository": {"nameWithOwner": "owner/repo"},
            "url": "",
            "state": "open",
            "labels": [],
            "assignees": [{"login": "someone"}],
            "createdAt": "",
            "updatedAt": "",
            "body": "",
            "commentsCount": 0,
        }])
        mock_run.return_value = _gh_result(stdout=payload)

        results = list(searcher._search_global(
            "query", "good first issue", "open", None, None, True, None, limit=20,
        ))

        assert results == []

    @patch("gfi.search.subprocess.run")
    def test_returns_nothing_on_nonzero_exit(self, mock_run, searcher):
        mock_run.return_value = _gh_result(returncode=1, stdout="")

        results = list(searcher._search_global(
            "query", "good first issue", "open", None, None, True, None, limit=20,
        ))

        assert results == []

    @patch("gfi.search.subprocess.run")
    def test_returns_nothing_on_malformed_json(self, mock_run, searcher):
        mock_run.return_value = _gh_result(stdout="not json")

        results = list(searcher._search_global(
            "query", "good first issue", "open", None, None, True, None, limit=20,
        ))

        assert results == []

    def test_returns_nothing_on_timeout(self, searcher):
        with patch("gfi.search.subprocess.run",
                    side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=30)):
            results = list(searcher._search_global(
                "query", "good first issue", "open", None, None, True, None, limit=20,
            ))

        assert results == []
