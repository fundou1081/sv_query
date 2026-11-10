"""Constraint chain between two random variables (P142)."""
import json
import os
import subprocess
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures',
                        'constraint_neighborhood.sv')


def _run(src, dst, *extra):
    return subprocess.run(
        [sys.executable, os.path.join(_ROOT, 'run_cli.py'), 'trace',
         'constraint-chain', src, dst, '-f', _FIXTURE, '--json', *extra],
        capture_output=True, text=True, cwd=_ROOT)


class TestConstraintChain(unittest.TestCase):
    def test_multi_hop_chain_and_blocks(self):
        proc = _run('rnd_item.a', 'rnd_item.d')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        result = json.loads(proc.stdout)['result']
        self.assertTrue(result['found'])
        self.assertEqual(3, result['hop_count'])
        self.assertEqual(['rnd_item.c_ab', 'rnd_item.c_bc', 'rnd_item.c_cd'],
                         result['blocks'])
        self.assertEqual(['rnd_item.a', 'rnd_item.b', 'rnd_item.c',
                          'rnd_item.d'],
                         [x['id'] for x in result['chain']
                          if x['kind'] == 'variable'])

    def test_condition_edge_is_marked(self):
        proc = _run('rnd_item.c', 'rnd_item.d')
        result = json.loads(proc.stdout)['result']
        self.assertTrue(result['found'])
        self.assertEqual('condition', result['segments'][0]['via'])

    def test_non_random_endpoint_is_explicit(self):
        proc = _run('rnd_item.a', 'rnd_item.k')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        result = json.loads(proc.stdout)['result']
        self.assertFalse(result['found'])
        self.assertEqual('endpoint_not_random', result['reason'])

    def test_no_path_is_not_found(self):
        proc = _run('rnd_item.a', 'rnd_item.e')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        result = json.loads(proc.stdout)['result']
        self.assertFalse(result['found'])
        self.assertEqual('no_constraint_path', result['reason'])

    def test_unknown_endpoint_is_explicit(self):
        proc = _run('rnd_item.a', 'rnd_item.nope')
        self.assertEqual(1, proc.returncode)
        self.assertFalse(json.loads(proc.stdout)['ok'])


if __name__ == '__main__':
    unittest.main()
