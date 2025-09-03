from pathlib import Path
import subprocess
import sys


def test_merge_smoke(tmp_path):
    # Requires fixtures to exist in tests/data created by tools/make_fixtures.py
    root = Path(__file__).resolve().parents[1]
    src = root / "tests" / "data" / "DE_kafka_min.epub"
    tgt = root / "tests" / "data" / "EN_kafka_min.epub"
    out = tmp_path / "out.epub"
    assert (
        src.exists() and tgt.exists()
    ), "Test fixtures missing. Run tools/make_fixtures.py."

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
    ]
    subprocess.check_call(cmd)
    assert out.exists() and out.stat().st_size > 0
