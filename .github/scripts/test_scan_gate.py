"""Gate orchestration regression tests; Docker and Trivy are mocked."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('scan-image.sh')
FAKE_DOCKER = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['CALLS'], 'a') as log:
    log.write(json.dumps(args) + '\n')
mount = next(a for a in args if a.startswith('type=bind,src=') and a.endswith(',dst=/out'))
outdir = pathlib.Path(mount[len('type=bind,src='):-len(',dst=/out')])
mode = os.environ['SCENARIO']
is_gate = '--exit-code' in args
is_convert = 'convert' in args
if mode == 'scan-error' and not is_convert and not is_gate: sys.exit(1)
if mode == 'conversion-error' and is_convert: sys.exit(1)
if '--output' in args and mode != 'missing-report':
    output = outdir / pathlib.Path(args[args.index('--output') + 1]).name
    output.write_text('{"SchemaVersion":2,"Results":[]}' if output.suffix == '.json' else 'test report\n')
if is_gate and mode == 'findings': sys.exit(42)
if is_gate and mode == 'eol': sys.exit(43)
if is_gate and mode == 'gate-error': sys.exit(1)
sys.exit(0)
'''

class GateTests(unittest.TestCase):
    def run_case(self, scenario, layout=False):
        with tempfile.TemporaryDirectory(prefix='reporter gate ') as tmp:
            root = Path(tmp)
            docker = root / 'docker'
            docker.write_text(FAKE_DOCKER)
            docker.chmod(0o755)
            image = root / 'image'
            if layout:
                image.mkdir()
                (image / 'index.json').write_text('{}')
                (image / 'oci-layout').write_text('{"imageLayoutVersion":"1.0.0"}')
            else:
                image.write_bytes(b'test artifact; not a real image')
            calls = root / 'calls.jsonl'
            env = dict(os.environ, PATH=f'{root}:{os.environ["PATH"]}',
                       SCENARIO=scenario, CALLS=str(calls),
                       TRIVY_CACHE_DIR=str(root / 'cache'))
            proc = subprocess.run(['bash', str(SCRIPT), str(image), str(root / 'out')],
                                  env=env, capture_output=True, text=True, timeout=30)
            return proc, [json.loads(line) for line in calls.read_text().splitlines()]

    def test_clean(self):
        proc, calls = self.run_case('clean')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(calls), 4)
        self.assertNotIn('--ignore-unfixed', calls[0])
        self.assertIn('--ignore-unfixed', calls[-1])
        self.assertIn('--exit-code', calls[-1])
        self.assertIn('42', calls[-1])
        self.assertIn('--skip-db-update', calls[-1])
        for call in calls:
            self.assertNotIn('--ignore-status', call)
            self.assertFalse(any('/var/run/docker.sock' in arg for arg in call))

    def test_oci_layout(self):
        self.assertEqual(self.run_case('clean', layout=True)[0].returncode, 0)

    def test_findings_block(self):
        self.assertEqual(self.run_case('findings')[0].returncode, 42)

    def test_eol_blocks(self):
        self.assertEqual(self.run_case('eol')[0].returncode, 43)

    def test_scan_error_blocks(self):
        proc, calls = self.run_case('scan-error')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(len(calls), 1)

    def test_missing_report_blocks(self):
        proc, calls = self.run_case('missing-report')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(len(calls), 1)

    def test_conversion_error_blocks(self):
        proc, calls = self.run_case('conversion-error')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(len(calls), 2)

    def test_gate_error_blocks(self):
        self.assertNotEqual(self.run_case('gate-error')[0].returncode, 0)

if __name__ == '__main__':
    unittest.main()
