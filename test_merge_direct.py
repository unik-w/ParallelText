#!/usr/bin/env python3

from paralleltext.cli.ptd import cli
import sys

print('Testing CLI merge command...')

try:
    # Test with merge command
    args = ['merge', '--src', 'fixtures/de.epub', '--tgt', 'fixtures/en.epub', '--out', 'fixtures/test_cli_direct.epub']
    print(f'Args: {args}')
    cli(args)
except SystemExit as e:
    print(f'SystemExit: {e}')
except Exception as e:
    print(f'Exception: {e}')
    import traceback
    traceback.print_exc()
