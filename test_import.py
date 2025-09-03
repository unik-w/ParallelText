#!/usr/bin/env python3

try:
    import paralleltext.cli.ptd
    print('Import successful')
except Exception as e:
    print(f'Import failed: {e}')
    import traceback
    traceback.print_exc()
