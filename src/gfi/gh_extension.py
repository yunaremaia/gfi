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

    # If first arg is a gfi subcommand, pass through
    # Otherwise, show gfi help
    if not args or args[0] in ("--help", "-h", "--version"):
        # Show gfi help
        sys.argv = ["gfi", "--help"]
    else:
        sys.argv = ["gfi"] + args

    cli()


if __name__ == "__main__":
    main()
