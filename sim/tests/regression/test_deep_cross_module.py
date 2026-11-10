"""Deep from/to path scenarios across multiple module levels (P141)."""
import json
import os
import subprocess
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures',
                        'deep_cross_module.sv')


def _run(*args):
    return subprocess.run(
        [sys.executable, os.path.join(_ROOT, 'run_cli.py'), *args,
         '-f', _FIXTURE, '--json'],
        capture_output=True, text=True, cwd=_ROOT)


class TestDeepCrossModule(unittest.TestCase):
    def test_six_hop_path_crosses_three_modules(self):
        proc = _run('paths', 'top.x', 'top.y', '--directed')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertTrue(data['found'])
        self.assertGreaterEqual(len(data['path']), 6)
        self.assertIn('top.u_mid.u_leaf.a', data['path'])
        self.assertEqual('top.u_mid.u_leaf.b',
                         data['path'][data['path'].index('top.u_mid.u_leaf.a') + 1])

    def test_path_from_deep_position_to_top_output(self):
        proc = _run('paths', 'top.u_mid.u_leaf.a', 'top.y', '--directed')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertTrue(data['found'])
        self.assertEqual('top.u_mid.u_leaf.a', data['path'][0])

    def test_reverse_directed_path_is_not_found(self):
        proc = _run('paths', 'top.y', 'top.x', '--directed')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        self.assertFalse(json.loads(proc.stdout)['found'])

    def test_dataflow_agrees_on_reachability(self):
        proc = _run('dataflow', 'analyze', 'top.x', 'top.y')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        result = json.loads(proc.stdout).get('result', {})
        self.assertTrue(result.get('is_reachable'))

    def test_verify_claim_path_supports_deep_path(self):
        claim = json.dumps({"type": "path", "from": "top.x", "to": "top.y"})
        proc = _run('verify', 'claim', '--claim', claim)
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        self.assertEqual('verified', json.loads(proc.stdout)['result']['status'])


if __name__ == '__main__':
    unittest.main()
