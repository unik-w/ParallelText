#!/usr/bin/env python3
"""Debug script to test merge functionality."""

from paralleltext.cli.ptd import _do_merge

try:
    _do_merge(
        "tests/data/DE_kafka_min.epub",
        "tests/data/EN_kafka_min.epub",
        "debug_output.epub",
        0,
        "diagonal",
    )
    print("✅ Merge completed successfully")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
