"""FIFO boundary is an explicit, opt-in dataflow edge."""
import json
import os
import subprocess
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'fifo_bridge.sv')


def _paths(*extra):
    return subprocess.run(
        [sys.executable, os.path.join(_ROOT, 'run_cli.py'), 'paths',
         'top.din', 'top.dout', '--directed', '-f', _FIXTURE, '--json', *extra],
        capture_output=True, text=True, cwd=_ROOT)


class TestFifoBridge(unittest.TestCase):
    def test_default_does_not_cross_fifo(self):
        proc = _paths()
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        self.assertFalse(json.loads(proc.stdout).get('found'))

    def test_through_fifo_crosses_boundary(self):
        proc = _paths('--through-fifo')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertTrue(data.get('found'))
        path = data.get('path') or []
        self.assertIn('top.u_fifo.wdata_i', path)
        self.assertIn('top.u_fifo.rdata_o', path)


if __name__ == '__main__':
    unittest.main()
