"""TB field -> RTL candidate join (explicit candidate, not a hard claim)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_TB = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'tb_join_tb.sv')
_RTL = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'tb_join_rtl.sv')


class TestTbJoin(unittest.TestCase):
    def test_unique_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ, SVQ_SNAPSHOT_DIR=td)
            save = subprocess.run(
                [sys.executable, os.path.join(_ROOT, 'run_cli.py'), 'snapshot',
                 'save', _RTL, '--tag', 'tb_join_snap', '--json'],
                capture_output=True, text=True, cwd=_ROOT, env=env)
            self.assertEqual(0, save.returncode, save.stderr[-1000:])
            proc = subprocess.run(
                [sys.executable, os.path.join(_ROOT, 'run_cli.py'), 'trace', 'tb-join',
                 'tb_item.rcont', '-f', _TB, '--from-snapshot', 'tb_join_snap', '--json'],
                capture_output=True, text=True, cwd=_ROOT, env=env)
            self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
            r = json.loads(proc.stdout)['result']
            self.assertEqual('single_candidate', r['join_status'])
            self.assertEqual('top.rcont', r['rtl_candidates'][0]['signal'])
            self.assertEqual('tb_item.rcont_c', r['constraints'][0]['block'])


if __name__ == '__main__':
    unittest.main()
