#!/usr/bin/env python3

import sys
from paralleltext.cli.ptd import cli

if __name__ == "__main__":
    print(f"DEBUG: __main__.py called with args: {sys.argv}", file=sys.stderr)
    cli()
