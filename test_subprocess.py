#!/usr/bin/env python3

import sys
import subprocess

result = subprocess.run([
    sys.executable, '-m', 'paralleltext.cli.ptd', 'merge', 
    '--src', 'fixtures/de.epub', 
    '--tgt', 'fixtures/en.epub', 
    '--out', 'fixtures/test_subprocess.epub'
], capture_output=True, text=True)

print('Return code:', result.returncode)
print('STDOUT:', repr(result.stdout))
print('STDERR:', repr(result.stderr))
