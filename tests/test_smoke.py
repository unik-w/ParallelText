from pathlib import Path
import subprocess
import sys


def test_merge_smoke_naive(tmp_path):
    """Smoke test using naive alignment (backward compatibility)."""
    root = Path(__file__).resolve().parents[1]
    src = root / "tests" / "data" / "DE_kafka_min.epub"
    tgt = root / "tests" / "data" / "EN_kafka_min.epub"
    out = tmp_path / "out.epub"

    if not (src.exists() and tgt.exists()):
        # Fall back to fixtures if kafka test data not available
        src = root / "tests" / "fixtures" / "de.epub"
        tgt = root / "tests" / "fixtures" / "en.epub"
        if not (src.exists() and tgt.exists()):
            import pytest
            pytest.skip("Test fixtures missing.")

    cmd = [
        sys.executable,
        "-m",
        "paralleltext.cli.ptd",
        "merge",
        "--src",
        str(src),
        "--tgt",
        str(tgt),
        "--out",
        str(out),
        "--alignment-backend",
        "naive",
    ]
    subprocess.check_call(cmd)
    assert out.exists() and out.stat().st_size > 0


def test_merge_bertalign(tmp_path):
    """Test merge with Bertalign semantic alignment on full EPUBs."""
    root = Path(__file__).resolve().parents[1]
    src = root / "German.epub"
    tgt = root / "English.epub"
    out = tmp_path / "bertalign_out.epub"

    if not (src.exists() and tgt.exists()):
        import pytest
        pytest.skip("English.epub and German.epub not found at repo root.")

    cmd = [
        sys.executable,
        "-m",
        "paralleltext.cli.ptd",
        "merge",
        "--src",
        str(src),
        "--tgt",
        str(tgt),
        "--out",
        str(out),
        "--alignment-backend",
        "bertalign",
        "--chapters",
        "3",
    ]
    subprocess.check_call(cmd)
    assert out.exists() and out.stat().st_size > 0
