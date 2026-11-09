"""FIFO must be invisible to default structural/dataflow/verify consumers."""
import json
import os
import subprocess
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'fifo_bridge.sv')


def _run(*args):
    return subprocess.run(
        [sys.executable, os.path.join(_ROOT, 'run_cli.py'), *args,
         '-f', _FIXTURE, '--json'],
        capture_output=True, text=True, cwd=_ROOT)


class TestFifoVisibility(unittest.TestCase):
    def test_paths_default_undirected_hides_fifo(self):
        proc = _run('paths', 'top.din', 'top.dout')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        self.assertFalse(json.loads(proc.stdout).get('found'))

    def test_dataflow_default_hides_fifo(self):
        proc = _run('dataflow', 'analyze', 'top.din', 'top.dout')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        result = json.loads(proc.stdout).get('result', {})
        self.assertFalse(result.get('is_reachable'))

    def test_verify_path_default_contradicts_fifo(self):
        claim = json.dumps({"type": "path", "from": "top.din", "to": "top.dout"})
        proc = _run('verify', 'claim', '--claim', claim)
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        self.assertEqual('contradicted', json.loads(proc.stdout)['result']['status'])

    def test_fanin_does_not_cross_fifo(self):
        proc = _run('trace', 'fanin', 'top.u_fifo.rdata_o')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        sig = json.loads(proc.stdout)['result']['signals'][0]
        self.assertNotIn('top.w', {d['id'] for d in sig.get('drivers', [])})


if __name__ == '__main__':
    unittest.main()
