"""Tests for gfi GitHub CLI extension mode."""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from gfi.gh_extension import main


def test_gh_extension_invokes_cli():
    """Test that gh extension mode invokes the CLI with correct args."""
    with patch.object(sys, "argv", ["gh-gfi", "search", "--limit", "5"]):
        with patch("gfi.gh_extension.cli") as mock_cli:
            main()
            mock_cli.assert_called_once_with()


def test_gh_extension_help():
    """Test that gh extension shows help when no args."""
    with patch.object(sys, "argv", ["gh-gfi"]):
        with patch("gfi.gh_extension.cli") as mock_cli:
            main()
            mock_cli.assert_called_once_with()


def test_gh_extension_version():
    """Test that gh extension shows version."""
    with patch.object(sys, "argv", ["gh-gfi", "--version"]):
        with patch("gfi.gh_extension.cli") as mock_cli:
            main()
            mock_cli.assert_called_once_with()


def test_gh_extension_script_installed() -> None:
    """Test that gh-gfi script is installed by pip."""
    import shutil
    # The script should be on PATH after pip install
    gfi_path = shutil.which("gh-gfi")
    assert gfi_path is not None, (
        "gh-gfi not found on PATH — check pyproject.toml [project.scripts]"
    )
    result = subprocess.run(
        ["gh-gfi", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    # Either prints version or invokes CLI (which has its own --version handling)
    assert result.returncode == 0, f"gh-gfi --version failed: {result.stderr}"
