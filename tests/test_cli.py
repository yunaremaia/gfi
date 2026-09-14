"""Tests for gfi CLI output formats."""
import csv
import io

import pytest
from click.testing import CliRunner

from gfi.cli import CSV_COLUMNS, cli
from gfi.search import Issue


@pytest.fixture
def issues():
    return [
        Issue(
            number=1,
            title='Parser handles commas, "quotes", and\nnewlines',
            repo="owner/project",
            url="https://github.com/owner/project/issues/1",
            state="open",
            labels=["good first issue", "désign"],
            created_at="2026-09-01T12:30:00Z",
            stars=42,
            comments=3,
        ),
        Issue(
            number=2,
            title="UTF-8: café ☕",
            repo="owner/project",
            url="https://github.com/owner/project/issues/2",
            state="open",
        ),
    ]


@pytest.fixture
def fake_searcher(monkeypatch, issues):
    class FakeSearcher:
        def search(self, **kwargs):
            return iter(issues)

        def is_seen(self, issue):
            return False

    monkeypatch.setattr("gfi.cli.GitHubSearcher", FakeSearcher)


def parse_csv(output):
    return list(csv.reader(io.StringIO(output)))


def test_search_csv_has_exact_header_and_escaped_rows(fake_searcher):
    result = CliRunner().invoke(cli, ["search", "--csv"])

    assert result.exit_code == 0
    rows = parse_csv(result.output)
    assert rows[0] == list(CSV_COLUMNS)
    assert rows[1] == [
        "1",
        'Parser handles commas, "quotes", and\nnewlines',
        "owner/project",
        "https://github.com/owner/project/issues/1",
        "good first issue, désign",
        "2026-09-01T12:30:00Z",
        "3",
        "42",
    ]
    assert rows[2] == [
        "2",
        "UTF-8: café ☕",
        "owner/project",
        "https://github.com/owner/project/issues/2",
        "",
        "",
        "0",
        "0",
    ]


@pytest.mark.parametrize(
    ("args", "expected_rows"),
    [
        (["repo", "owner/project", "--csv"], 3),
        (["trending", "--limit", "2", "--csv"], 3),
    ],
)
def test_other_commands_support_csv(fake_searcher, args, expected_rows):
    result = CliRunner().invoke(cli, args)

    assert result.exit_code == 0
    rows = parse_csv(result.output)
    assert rows[0] == list(CSV_COLUMNS)
    assert len(rows) == expected_rows
