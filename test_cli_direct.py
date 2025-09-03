#!/usr/bin/env python3

from paralleltext.cli.ptd import cli
import sys

print('Testing CLI...')
print('sys.argv:', sys.argv)

try:
    # Test with help
    print('Testing help...')
    cli(['--help'])
except SystemExit as e:
    print(f'SystemExit: {e}')
except Exception as e:
    print(f'Exception: {e}')
    import traceback
    traceback.print_exc()
