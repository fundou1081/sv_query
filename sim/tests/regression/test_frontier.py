"""trace frontier reports generic boundaries, never FIFO classification."""
import json
import os
import subprocess
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'arch_pair.sv')


def _run(*extra):
    return subprocess.run(
        [sys.executable, os.path.join(_ROOT, 'run_cli.py'), 'trace', 'frontier',
         'top.x', '-f', _FIXTURE, '--json', *extra],
        capture_output=True, text=True, cwd=_ROOT)


class TestFrontier(unittest.TestCase):
    def test_boundary_and_probes(self):
        proc = _run()
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        result = json.loads(proc.stdout)['result']
        self.assertGreaterEqual(result['summary']['frontier_count'], 1)
        row = result['frontier'][0]
        self.assertEqual('no_structural_edge', row['reason'])
        self.assertTrue(row['next_probes'])
        self.assertIn('not a FIFO classification', result['note'])

    def test_unknown_signal_is_explicit(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, 'run_cli.py'), 'trace', 'frontier',
             'top.nope', '-f', _FIXTURE, '--json'],
            capture_output=True, text=True, cwd=_ROOT)
        self.assertEqual(1, proc.returncode)
        self.assertFalse(json.loads(proc.stdout)['ok'])

    def test_invalid_direction_is_explicit(self):
        proc = _run('--direction', 'sideways')
        self.assertEqual(1, proc.returncode)
        self.assertFalse(json.loads(proc.stdout)['ok'])


if __name__ == '__main__':
    unittest.main()
