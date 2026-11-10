"""Snapshot frontier probes must be executable in the same snapshot context."""
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIX = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'arch_pair.sv')


def _run(args, env):
    return subprocess.run([sys.executable, os.path.join(_ROOT, 'run_cli.py'),
                           *args, '--json'], capture_output=True, text=True,
                          cwd=_ROOT, env=env)


class TestFrontierSnapshotProbes(unittest.TestCase):
    def test_probes_include_snapshot_and_execute(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env['SVQ_SNAPSHOT_DIR'] = td
            save = _run(['snapshot', 'save', _FIX, '--tag', 'p154'], env)
            self.assertEqual(0, save.returncode, save.stderr[-1000:])
            proc = _run(['trace', 'frontier', 'top.w', '--direction', 'fanout',
                         '--from-snapshot', 'p154'], env)
            self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
            rows = json.loads(proc.stdout)['result']['frontier']
            probes = [p for row in rows for p in row['next_probes']]
            self.assertTrue(probes)
            for probe in probes:
                self.assertIn('--from-snapshot p154', probe)
                args = shlex.split(probe)
                out = _run(args, env)
                self.assertEqual(0, out.returncode, f"{probe}: {out.stderr[-500:]}")
                self.assertTrue(json.loads(out.stdout).get('ok'), probe)


if __name__ == '__main__':
    unittest.main()
