"""P149: snapshot consistency is explicit; connection is unknown without MIG."""
import json
import os
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


class TestConsistencySnapshot(unittest.TestCase):
    def test_bit_and_connection_statuses_are_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env['SVQ_SNAPSHOT_DIR'] = td
            save = _run(['snapshot', 'save', _FIX, '--tag', 'p149',
                         '--json'], env)
            self.assertEqual(0, save.returncode, save.stderr[-1000:])
            p = _run(['verify', 'consistency', '--from-snapshot', 'p149',
                      '--checks', 'bit,connection'], env)
            self.assertEqual(0, p.returncode, p.stderr[-1000:])
            r = json.loads(p.stdout)['result']
            self.assertEqual([], r['unknown_checks'])
            connection = next(c for c in r['checks'] if c['check'] == 'connection')
            self.assertEqual('pass', connection['status'])
            self.assertGreater(connection['checked'], 0)


if __name__ == '__main__':
    unittest.main()
