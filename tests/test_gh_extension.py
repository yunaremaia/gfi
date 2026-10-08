"""Tests for gfi GitHub CLI extension mode."""
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from gfi.gh_extension import main

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_gh_extension_invokes_cli():
    """Test that gh extension mode invokes the CLI with correct args."""
    with patch.object(sys, "argv", ["gh-gfi", "search", "--limit", "5"]):
        with patch("gfi.gh_extension.cli") as mock_cli:
            main()
            mock_cli.assert_called_once_with(prog_name="gh gfi")


def test_gh_extension_passes_args_to_cli():
    """Arguments are forwarded to the gfi CLI unchanged."""
    with patch.object(sys, "argv", ["gh-gfi", "search", "--limit", "5"]):
        with patch("gfi.gh_extension.cli") as mock_cli:
            main()
            assert sys.argv == ["gfi", "search", "--limit", "5"]
            mock_cli.assert_called_once_with(prog_name="gh gfi")


def test_gh_extension_help():
    """Test that gh extension shows help when no args."""
    with patch.object(sys, "argv", ["gh-gfi"]):
        with patch("gfi.gh_extension.cli") as mock_cli:
            main()
            assert sys.argv == ["gfi", "--help"]
            mock_cli.assert_called_once_with(prog_name="gh gfi")


def test_gh_extension_version():
    """`--version` is forwarded so click prints the version, not help (#91)."""
    with patch.object(sys, "argv", ["gh-gfi", "--version"]):
        with patch("gfi.gh_extension.cli") as mock_cli:
            main()
            assert sys.argv == ["gfi", "--version"]
            mock_cli.assert_called_once_with(prog_name="gh gfi")


def test_gh_extension_root_script_prints_version():
    """The root script extension must print a version, not the help text.

    `gh gfi --version` used to take the help branch and exit 0 with usage text,
    which is indistinguishable from a successful help request (#91).
    """
    result = subprocess.run(
        [str(REPO_ROOT / "gh-gfi"), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHON": sys.executable},
    )
    assert result.returncode == 0, f"gh-gfi --version failed: {result.stderr}"
    assert "version 0.1.0" in result.stdout, result.stdout
    assert not result.stdout.lstrip().startswith("Usage:"), result.stdout


def test_gh_extension_script_declared_in_pyproject():
    """The `gh-gfi` console script must be declared as an entry point.

    This is a static check on pyproject.toml: it does not need the package to
    be installed, so it holds in a bare checkout as well as in CI.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'gh-gfi = "gfi.gh_extension:main"' in pyproject


def test_gh_extension_root_script_exists_and_is_executable():
    """`gh extension install` requires an executable `gh-gfi` in the repo root.

    Without this file gh creates the extension symlink but fails at run time
    with `fork/exec .../gh-gfi: no such file or directory`.
    """
    script = REPO_ROOT / "gh-gfi"
    assert script.is_file(), "root gh-gfi script extension is missing"
    assert script.stat().st_mode & 0o111, "root gh-gfi must be executable (chmod +x)"


def test_gh_extension_root_script_runs():
    """The root script extension must actually invoke the CLI.

    Runs it in a subprocess with an isolated PYTHONPATH so it exercises the
    checkout directly instead of whatever `gfi` happens to be on PATH. PYTHON is
    pinned to the running interpreter so the result does not depend on which
    python3 happens to be first on PATH.
    """
    result = subprocess.run(
        [str(REPO_ROOT / "gh-gfi"), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHON": sys.executable},
    )
    assert result.returncode == 0, f"gh-gfi --help failed: {result.stderr}"
    assert "gh gfi" in result.stdout, f"unexpected help output: {result.stdout}"
    assert "RuntimeWarning" not in result.stderr, (
        f"gh-gfi emitted a RuntimeWarning: {result.stderr}"
    )


def test_python_m_gfi_module_entrypoint():
    """`python -m gfi` must run the extension entry point.

    `gh-gfi` falls back to this when gfi is not installed as a console script,
    so it is a real code path rather than a convenience alias.
    """
    result = subprocess.run(
        [sys.executable, "-m", "gfi", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert result.returncode == 0, f"python -m gfi failed: {result.stderr}"
    assert "gh gfi" in result.stdout, f"unexpected help output: {result.stdout}"


def test_main_module_delegates_to_extension_main():
    """`gfi.__main__` wires straight to the extension entry point.

    Executed via runpy with run_name='__main__' so the module's own
    `if __name__ == '__main__'` guard is actually exercised.
    """
    with patch.object(sys, "argv", ["gh-gfi", "--help"]):
        with patch("gfi.gh_extension.cli") as mock_cli:
            runpy.run_module("gfi", run_name="__main__")
            mock_cli.assert_called_once_with(prog_name="gh gfi")


@pytest.mark.skipif(
    shutil.which("gh-gfi") is None,
    reason="gh-gfi console script is not on PATH (package not installed)",
)
def test_gh_extension_script_installed() -> None:
    """Test that gh-gfi script is installed by pip."""
    # The script should be on PATH after pip install
    gfi_path = shutil.which("gh-gfi")
    assert gfi_path is not None, (
        "gh-gfi not found on PATH \u2014 check pyproject.toml [project.scripts]"
    )
    result = subprocess.run(
        [gfi_path, "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    # Either prints version or invokes CLI (which has its own --version handling)
    assert result.returncode == 0, f"gh-gfi --version failed: {result.stderr}"
