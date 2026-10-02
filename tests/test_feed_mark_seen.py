"""Tests that `gfi feed` marks issues as seen in every output mode.

`gfi feed` is a consumable queue: whatever it hands you it also records, so the
next run does not resurface the same issues. The README promises this
unconditionally -- "Show a feed of unseen good first issues. Marks issues as
seen automatically." -- and lists `--json-output` and `--csv` as supported
invocations, so the promise covers the machine formats too. Scripted callers
(`gfi feed --csv > feed.csv` in a cron job) were the ones silently starved:
they got the payload, but the seen cache never grew, so every run re-emitted an
identical file forever.

Two invariants are asserted together, because either one alone is easy to
"fix" by cheating:

- mark_seen IS called for every surfaced issue, in every mode; and
- stdout stays exactly the machine payload -- the fix must not route the
  marking, or its side effects, into the parsed stream.

The ordering test pins a third, quieter property: an issue is only consumed
after it has actually been delivered. If marking ran first and printing then
crashed, the issue would be gone from the feed forever with nothing delivered.
"""
import contextlib
import csv
import io
import json

import pytest
from click.testing import CliRunner

from gfi.cli import CSV_COLUMNS, cli
from gfi.search import GitHubSearcher, Issue

# Short titles: the human-facing table truncates and wraps them, which would
# make the ordering assertion below depend on column widths.
ISSUES = [
    Issue(
        number=1,
        title="First issue",
        repo="owner/project",
        url="https://github.com/owner/project/issues/1",
        state="open",
        labels=["good first issue"],
        created_at="2026-09-01T12:30:00Z",
        stars=42,
        comments=3,
    ),
    Issue(
        number=2,
        title="Second issue",
        repo="owner/project",
        url="https://github.com/owner/project/issues/2",
        state="open",
        stars=7,
    ),
]

URLS = [issue.url for issue in ISSUES]


@pytest.fixture
def searcher_stub(monkeypatch):
    """Install a searcher stub and hand the test a handle on it.

    The handle is a plain dict created before the command runs, so a test can
    adjust the stub's behaviour (empty results, an alternate result set) before
    invoking the CLI -- the stub reads it lazily, at call time.
    """
    handle = {"issues": list(ISSUES), "instance": None, "cls": None}

    class StubSearcher:
        def __init__(self):
            self.marked = []
            self.seen_keys = set()
            handle["instance"] = self

        def search(self, **kwargs):
            return iter(list(handle["issues"]))

        def is_seen(self, issue):
            return self._seen_key(issue) in self.seen_keys

        def _seen_key(self, issue):
            return issue.url or f"{issue.repo}#{issue.number}"

        def sort_deterministicly(self, results):
            return sorted(
                results, key=lambda i: (i.stars, i.created_at or ""), reverse=True
            )

        def mark_seen(self, issue):
            self.marked.append(issue)

        _seen = {}

    handle["cls"] = StubSearcher
    monkeypatch.setattr("gfi.cli.GitHubSearcher", StubSearcher)
    return handle


def invoke(args):
    """Invoke the CLI with stdout and stderr separated (Click 8.1 and 8.2+)."""
    try:
        runner = CliRunner(mix_stderr=False)
    except TypeError:  # Click >= 8.2: streams are always separate.
        runner = CliRunner()
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    return result.stdout, result.stderr


# Every documented `gfi feed` invocation shape.
MODES = [
    pytest.param([], id="text"),
    pytest.param(["--json-output"], id="json"),
    pytest.param(["--csv"], id="csv"),
]


def marked_urls(searcher_stub):
    return [issue.url for issue in searcher_stub["instance"].marked]


class TestMarkSeenRunsInEveryMode:
    @pytest.mark.parametrize("flags", MODES)
    def test_every_surfaced_issue_is_marked(self, searcher_stub, flags):
        invoke(["feed", *flags])

        assert marked_urls(searcher_stub) == URLS

    @pytest.mark.parametrize("flags", MODES)
    def test_marking_is_not_duplicated(self, searcher_stub, flags):
        invoke(["feed", *flags])

        marked = marked_urls(searcher_stub)
        assert len(marked) == len(set(marked)), "an issue was marked twice"

    @pytest.mark.parametrize("flags", MODES)
    def test_limit_truncates_both_output_and_marking(self, searcher_stub, flags):
        """Only delivered issues are consumed; the over-fetch is not."""
        invoke(["feed", "--limit", "1", *flags])

        assert marked_urls(searcher_stub) == URLS[:1]

    @pytest.mark.parametrize("flags", MODES)
    def test_no_results_nothing_is_marked(self, searcher_stub, flags):
        searcher_stub["issues"] = []

        invoke(["feed", *flags])

        assert searcher_stub["instance"].marked == []


class TestMarkingDoesNotCorruptStdout:
    """The fix must not pay for marking with a byte of stdout."""

    def test_json_stdout_is_still_exactly_the_payload(self, searcher_stub):
        stdout, _ = invoke(["feed", "--json-output"])

        assert [row["url"] for row in json.loads(stdout)] == URLS

    def test_csv_stdout_is_still_exactly_the_table(self, searcher_stub):
        stdout, _ = invoke(["feed", "--csv"])

        rows = list(csv.reader(io.StringIO(stdout)))
        assert rows[0] == list(CSV_COLUMNS)
        assert len(rows) == 1 + len(ISSUES)

    @pytest.mark.parametrize("flags", MODES)
    def test_marking_writes_nothing_to_stderr(self, searcher_stub, flags):
        _, stderr = invoke(["feed", *flags])

        assert "Marked" not in stderr
        assert "seen" not in stderr.lower()


class TestPayloadIsDeliveredBeforeMarking:
    """An issue is consumed only once it has actually been shown.

    Marking first would mean a crash between the two drops the issue from the
    feed with nothing delivered to compensate.
    """

    @pytest.mark.parametrize("flags", MODES)
    def test_nothing_is_marked_before_stdout_is_written(
        self, monkeypatch, searcher_stub, flags
    ):
        buffer = io.StringIO()
        stdout_at_mark = []

        def mark_seen(self, issue):
            stdout_at_mark.append(buffer.getvalue())
            self.marked.append(issue)

        monkeypatch.setattr(searcher_stub["cls"], "mark_seen", mark_seen)

        with contextlib.redirect_stdout(buffer):
            cli.main(["feed", *flags], standalone_mode=False)

        assert stdout_at_mark, "mark_seen was never called"
        assert stdout_at_mark[0], "stdout was still empty at the first mark_seen"
        assert ISSUES[0].title in stdout_at_mark[0], (
            "the first issue was consumed before it reached stdout"
        )
        assert ISSUES[-1].title in buffer.getvalue()


class TestSeenCacheIsPersisted:
    """End-to-end through the real searcher: the cache file must grow.

    The stub above only proves the method was called; this proves the file a
    later `gfi feed` / `gfi stats` reads actually contains the issues.
    """

    @pytest.mark.parametrize("flags", MODES)
    def test_seen_json_written(self, monkeypatch, tmp_path, flags):
        # Real GitHubSearcher, fake GitHub. Redirecting HOME keeps the
        # developer's own ~/.gfi out of the test.
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setattr(
            GitHubSearcher, "search", lambda self, **kwargs: iter(list(ISSUES))
        )

        invoke(["feed", *flags])

        seen_file = tmp_path / ".gfi" / "seen.json"
        assert seen_file.exists(), "feed did not persist the seen cache"
        assert set(json.loads(seen_file.read_text())) == set(URLS)