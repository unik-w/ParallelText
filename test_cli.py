#!/usr/bin/env python3

import sys
try:
    from paralleltext.cli.ptd import _do_merge
    print('Starting merge...')
    _do_merge('fixtures/de.epub', 'fixtures/en.epub', 'fixtures/test_cli_output.epub', 0)
    print('Merge completed')
except Exception as e:
    print(f'Error in _do_merge: {e}')
    import traceback
    traceback.print_exc()
