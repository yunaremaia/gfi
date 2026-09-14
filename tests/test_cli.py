"""Tests for gfi CLI commands and CSV export format."""
import csv
import io
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from gfi.cli import _render_csv, cli
from gfi.search import Issue


@pytest.fixture
def sample_issues():
    return [
        Issue(
            number=25,
            title="docs: update README stats",
            repo="yunaremaia/driftcheck",
            url="https://github.com/yunaremaia/driftcheck/issues/25",
            state="open",
            labels=["documentation", "good first issue"],
            assignees=[],
            stars=50,
            language="python",
        ),
        Issue(
            number=101,
            title="fix: handle empty config",
            repo="octocat/hello-world",
            url="https://github.com/octocat/hello-world/issues/101",
            state="closed",
            labels=[],
            assignees=["octocat"],
            stars=1200,
            language="go",
        ),
    ]


def test_render_csv_header_and_data(sample_issues):
    csv_text = _render_csv(sample_issues)
    reader = list(csv.DictReader(io.StringIO(csv_text)))

    assert len(reader) == 2

    assert reader[0]["number"] == "25"
    assert reader[0]["title"] == "docs: update README stats"
    assert reader[0]["repo"] == "yunaremaia/driftcheck"
    assert reader[0]["url"] == "https://github.com/yunaremaia/driftcheck/issues/25"
    assert reader[0]["state"] == "open"
    assert reader[0]["labels"] == "documentation good first issue"
    assert reader[0]["stars"] == "50"
    assert reader[0]["language"] == "python"

    assert reader[1]["number"] == "101"
    assert reader[1]["title"] == "fix: handle empty config"
    assert reader[1]["repo"] == "octocat/hello-world"
    assert reader[1]["url"] == "https://github.com/octocat/hello-world/issues/101"
    assert reader[1]["state"] == "closed"
    assert reader[1]["labels"] == ""
    assert reader[1]["stars"] == "1200"
    assert reader[1]["language"] == "go"


def test_render_csv_empty():
    csv_text = _render_csv([])
    reader = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(reader) == 0
    assert csv_text.strip() == "number,title,repo,url,state,labels,stars,language"


def test_search_csv_flag(sample_issues):
    runner = CliRunner()
    with patch("gfi.cli.GitHubSearcher") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.search.return_value = iter(sample_issues)
        mock_instance.is_seen.return_value = False
        mock_cls.return_value = mock_instance

        result = runner.invoke(cli, ["search", "--csv"])
        assert result.exit_code == 0

        rows = list(csv.DictReader(io.StringIO(result.output)))
        assert len(rows) == 2
        assert rows[0]["number"] == "25"
        assert rows[0]["repo"] == "yunaremaia/driftcheck"


def test_repo_csv_flag(sample_issues):
    runner = CliRunner()
    with patch("gfi.cli.GitHubSearcher") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.search.return_value = iter(sample_issues)
        mock_cls.return_value = mock_instance

        result = runner.invoke(cli, ["repo", "yunaremaia/driftcheck", "--csv"])
        assert result.exit_code == 0

        rows = list(csv.DictReader(io.StringIO(result.output)))
        assert len(rows) == 2
        assert rows[0]["title"] == "docs: update README stats"


def test_trending_csv_flag(sample_issues):
    runner = CliRunner()
    with patch("gfi.cli.GitHubSearcher") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.search.return_value = iter(sample_issues)
        mock_cls.return_value = mock_instance

        result = runner.invoke(cli, ["trending", "--csv", "--limit", "5"])
        assert result.exit_code == 0

        rows = list(csv.DictReader(io.StringIO(result.output)))
        assert len(rows) > 0
        assert "number" in rows[0]
        assert "title" in rows[0]
        assert "repo" in rows[0]


def test_feed_csv_flag(sample_issues):
    runner = CliRunner()
    with patch("gfi.cli.GitHubSearcher") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.search.return_value = iter(sample_issues)
        mock_instance.is_seen.return_value = False
        mock_cls.return_value = mock_instance

        result = runner.invoke(cli, ["feed", "--csv"])
        assert result.exit_code == 0

        rows = list(csv.DictReader(io.StringIO(result.output)))
        assert len(rows) == 2
        assert mock_instance.mark_seen.call_count == 2


def test_search_csv_empty_results():
    runner = CliRunner()
    with patch("gfi.cli.GitHubSearcher") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.search.return_value = iter([])
        mock_cls.return_value = mock_instance

        result = runner.invoke(cli, ["search", "--csv"])
        assert result.exit_code == 0
        assert result.output.strip() == "number,title,repo,url,state,labels,stars,language"
        rows = list(csv.DictReader(io.StringIO(result.output)))
        assert len(rows) == 0


def test_csv_escapes_commas_and_quotes():
    issues = [
        Issue(
            number=42,
            title='feat: support "quoted", comma-separated text',
            repo="org/repo",
            url="https://github.com/org/repo/issues/42",
            state="open",
            labels=["label,with,commas", "another"],
            stars=10,
            language="python",
        )
    ]
    csv_text = _render_csv(issues)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 1
    assert rows[0]["title"] == 'feat: support "quoted", comma-separated text'
    assert rows[0]["labels"] == "label,with,commas another"


def test_json_output_no_leading_whitespace(sample_issues):
    runner = CliRunner()
    with patch("gfi.cli.GitHubSearcher") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.search.return_value = iter(sample_issues)
        mock_instance.is_seen.return_value = False
        mock_cls.return_value = mock_instance

        result = runner.invoke(cli, ["search", "--json-output"])
        assert result.exit_code == 0
        assert not result.output.startswith("\n")
        assert result.output.strip().startswith("[")

