"""Tests that the declared package metadata matches what the CLI can do.

`gfi open` shells out to `xdg-open`, which only exists on Linux. The package
metadata used to claim no platform restriction at all, so a macOS or Windows
user could install gfi from the declared metadata and only discover the problem
when `gfi open` failed. These tests pin the metadata to the real capability.

The checks read pyproject.toml as text rather than parsing it: `tomllib` only
exists on Python 3.11+, and this project's CI matrix includes 3.10. That
matches how tests/test_gh_extension.py asserts on the same file.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PYPROJECT = REPO_ROOT / "pyproject.toml"

CONTRADICTORY_CLASSIFIERS = (
    "Operating System :: MacOS",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: OS Independent",
)


def test_open_command_uses_xdg_open() -> None:
    """The reason a Linux marker is needed: `open` requires xdg-open."""
    cli_source = (REPO_ROOT / "src" / "gfi" / "cli.py").read_text(encoding="utf-8")
    assert "xdg-open" in cli_source, (
        "the platform marker is justified only while `gfi open` shells out to "
        "xdg-open; update the metadata if the opener changed"
    )


def test_metadata_declares_a_linux_platform_marker() -> None:
    """The declared metadata must state the Linux requirement it actually has."""
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    assert '"Operating System :: POSIX :: Linux"' in pyproject, (
        "classifiers declare no Operating System entry, so `gfi open` (which "
        "needs xdg-open) is advertised as portable"
    )


def test_metadata_does_not_claim_cross_platform_support() -> None:
    """No classifier may contradict the Linux marker."""
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    for contradictory in CONTRADICTORY_CLASSIFIERS:
        assert f'"{contradictory}"' not in pyproject, (
            f"{contradictory!r} contradicts the Linux-only `gfi open` command"
        )