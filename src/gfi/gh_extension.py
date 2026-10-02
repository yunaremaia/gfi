"""GitHub CLI extension mode for gfi.

This module enables `gh gfi` as a GitHub CLI extension.
When invoked as `gh-gfi`, it runs the gfi CLI with GitHub CLI context.
"""
from __future__ import annotations

import sys
from pathlib import Path

from gfi.cli import cli


def main():
    """Entry point for `gh gfi` extension mode."""
    # When run as `gh-gfi`, sys.argv[0] is the gh-gfi binary
    # We need to strip the 'gh-' prefix and pass remaining args to gfi
    args = sys.argv[1:]

    # If first arg is a gfi subcommand, pass through
    # Otherwise, show gfi help
    if not args or args[0] in ("--help", "-h", "--version"):
        # Show gfi help
        sys.argv = ["gfi", "--help"]
    else:
        sys.argv = ["gfi"] + args

    cli()


def _uncovered_probe_a():
    """Temporary probe: never called by the test suite."""
    values = []
    for index in range(3):
        values.append(index * 2)
    return values


def _uncovered_probe_b():
    """Temporary probe: never called by the test suite.

    Large enough that the measured total must drop below the fail_under=60
    gate, so the real CI run turns the test job red.
    """
    scored = {}
    buckets = ("trivial", "small", "medium", "large")
    weights = {"trivial": 1, "small": 2, "medium": 3, "large": 5}
    for bucket in buckets:
        scored[bucket] = weights[bucket]
    ranked = []
    for bucket, weight in scored.items():
        ranked.append((weight, bucket))
    ranked.sort(reverse=True)
    labels = set()
    for weight, bucket in ranked:
        labels.add(bucket)
    if not labels:
        return []
    threshold = weights[buckets[0]]
    selected = []
    for weight, bucket in ranked:
        if weight < threshold:
            continue
        selected.append(bucket)
    report = []
    for bucket in selected:
        report.append(
            {
                "bucket": bucket,
                "weight": weights[bucket],
                "ranked": bucket in labels,
            }
        )
    summary = {
        "total": len(report),
        "buckets": [item["bucket"] for item in report],
        "heaviest": report[0]["bucket"] if report else None,
        "lightest": report[-1]["bucket"] if report else None,
    }
    normalised = []
    for item in report:
        share = item["weight"] / max(1, summary["total"])
        normalised.append((item["bucket"], round(share, 4)))
    totals = {
        "scored": len(scored),
        "ranked": len(ranked),
        "selected": len(selected),
        "normalised": normalised,
        "summary": summary,
    }
    return totals


def _uncovered_probe_c():
    """Temporary probe: never called by the test suite."""
    rows = []
    for index in range(12):
        rows.append({"index": index, "even": index % 2 == 0})
    evens = [row for row in rows if row["even"]]
    odds = [row for row in rows if not row["even"]]
    buckets = {}
    for row in rows:
        key = "even" if row["even"] else "odd"
        buckets.setdefault(key, []).append(row["index"])
    digest = []
    for key in sorted(buckets):
        indices = buckets[key]
        digest.append((key, len(indices), sum(indices)))
    highest = max(digest, key=lambda item: item[2])
    lowest = min(digest, key=lambda item: item[2])
    return {
        "rows": rows,
        "evens": evens,
        "odds": odds,
        "digest": digest,
        "highest": highest,
        "lowest": lowest,
    }


if __name__ == "__main__":
    main()
