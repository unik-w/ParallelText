"""Tests for CLI functionality."""

import pytest
import tempfile
import subprocess
import sys
from pathlib import Path


class TestCLI:
    """Test command-line interface functionality."""

    @pytest.fixture
    def test_fixtures(self):
        """Get paths to test fixture files."""
        base_path = Path(__file__).parent / "fixtures"
        src_path = base_path / "de.epub"
        tgt_path = base_path / "en.epub"

        if src_path.exists() and tgt_path.exists():
            return {"src": str(src_path), "tgt": str(tgt_path)}
        return None

    def test_cli_merge_command_success(self, test_fixtures):
        """Test that CLI merge command completes successfully."""
        if test_fixtures is None:
            pytest.skip("Test fixtures not available")

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            output_path = f.name

        try:
            cmd = [
                sys.executable,
                "-m",
                "paralleltext",
                "merge",
                "--src",
                test_fixtures["src"],
                "--tgt",
                test_fixtures["tgt"],
                "--out",
                output_path,
                "--chapters",
                "1",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            assert result.returncode == 0, f"Command failed: {result.stderr}"
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_cli_merge_with_diagonal_strategy(self, test_fixtures):
        """Test CLI merge with diagonal cover strategy."""
        if test_fixtures is None:
            pytest.skip("Test fixtures not available")

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            output_path = f.name

        try:
            cmd = [
                sys.executable,
                "-m",
                "paralleltext",
                "merge",
                "--src",
                test_fixtures["src"],
                "--tgt",
                test_fixtures["tgt"],
                "--out",
                output_path,
                "--cover-strategy",
                "diagonal",
                "--chapters",
                "1",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            assert result.returncode == 0
            assert Path(output_path).exists()

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_cli_merge_with_side_by_side_strategy(self, test_fixtures):
        """Test CLI merge with side-by-side cover strategy."""
        if test_fixtures is None:
            pytest.skip("Test fixtures not available")

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            output_path = f.name

        try:
            cmd = [
                sys.executable,
                "-m",
                "paralleltext",
                "merge",
                "--src",
                test_fixtures["src"],
                "--tgt",
                test_fixtures["tgt"],
                "--out",
                output_path,
                "--cover-strategy",
                "side_by_side",
                "--chapters",
                "1",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            assert result.returncode == 0
            assert Path(output_path).exists()

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_cli_merge_all_chapters(self, test_fixtures):
        """Test CLI merge with all chapters (chapters=0)."""
        if test_fixtures is None:
            pytest.skip("Test fixtures not available")

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            output_path = f.name

        try:
            cmd = [
                sys.executable,
                "-m",
                "paralleltext",
                "merge",
                "--src",
                test_fixtures["src"],
                "--tgt",
                test_fixtures["tgt"],
                "--out",
                output_path,
                "--chapters",
                "0",  # All chapters
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            assert result.returncode == 0
            assert Path(output_path).exists()

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_cli_missing_required_args(self):
        """Test CLI behavior with missing required arguments."""
        cmd = [
            sys.executable,
            "-m",
            "paralleltext",
            "merge",
            # Missing --src and --tgt
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode != 0  # Should fail

    def test_cli_nonexistent_input_files(self):
        """Test CLI behavior with non-existent input files."""
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            output_path = f.name

        try:
            cmd = [
                sys.executable,
                "-m",
                "paralleltext",
                "merge",
                "--src",
                "nonexistent_source.epub",
                "--tgt",
                "nonexistent_target.epub",
                "--out",
                output_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            assert result.returncode != 0  # Should fail

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_cli_help_message(self):
        """Test that CLI shows help message."""
        cmd = [sys.executable, "-m", "paralleltext", "--help"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0
        assert "merge" in result.stdout.lower()

    def test_cli_merge_help_message(self):
        """Test that CLI merge subcommand shows help."""
        cmd = [sys.executable, "-m", "paralleltext", "merge", "--help"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0
        assert "--src" in result.stdout
        assert "--tgt" in result.stdout
        assert "--out" in result.stdout
