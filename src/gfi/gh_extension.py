"""GitHub CLI extension mode for gfi.

This module enables `gh gfi` as a GitHub CLI extension.
When invoked as `gh-gfi`, it runs the gfi CLI with GitHub CLI context.
"""
from __future__ import annotations

import sys

from gfi.cli import cli


def main():
    """Entry point for `gh gfi` extension mode."""
    # When run as `gh-gfi`, sys.argv[0] is the gh-gfi binary
    # We need to strip the 'gh-' prefix and pass remaining args to gfi
    args = sys.argv[1:]

    # Empty invocation and explicit help flags show help. `--version` is not
    # help: click's version_option handles it, and folding it into this branch
    # rewrote `gh gfi --version` to `gfi --help` (#91).
    if not args or args[0] in ("--help", "-h"):
        sys.argv = ["gfi", "--help"]
    else:
        sys.argv = ["gfi"] + args

    # Pin the program name so help/usage reads "gh gfi" instead of whatever
    # sys.argv[0] happens to be (e.g. "python -m gfi.gfi").
    cli(prog_name="gh gfi")


if __name__ == "__main__":
    main()
