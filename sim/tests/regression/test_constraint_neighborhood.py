"""Cross-block constraint neighborhood query (one-shot)."""
import json
import os
import subprocess
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures',
                        'constraint_neighborhood.sv')


def _run(prop: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, os.path.join(_ROOT, 'run_cli.py'),
         'trace', 'constraint-neighborhood', prop,
         '-f', _FIXTURE, '--json', *extra],
        capture_output=True, text=True, cwd=_ROOT)


class TestConstraintNeighborhood(unittest.TestCase):
    def test_cross_block_chain(self):
        proc = _run('rnd_item.b')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        r = json.loads(proc.stdout)['result']
        self.assertEqual('rnd_item.b', r['root'])
        self.assertEqual(4, r['summary']['node_count'])
        self.assertEqual(2, r['summary']['direct_degree'])
        self.assertEqual(2, r['summary']['importance_metrics']['block_count'])
        self.assertEqual(['rnd_item.b', 'rnd_item.c', 'rnd_item.d'],
                         r['paths']['rnd_item.d'])
        self.assertIn('rnd_item.b', r['paths']['rnd_item.a'])
        self.assertFalse(r['summary']['truncated'])

    def test_budget_hit_sets_truncated(self):
        proc = _run('rnd_item.b', '--max-nodes', '1')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        r = json.loads(proc.stdout)['result']
        self.assertTrue(r['summary']['truncated'])

    def test_isolated_variable_has_no_relations(self):
        proc = _run('rnd_item.e')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        r = json.loads(proc.stdout)['result']
        self.assertEqual(1, r['summary']['node_count'])
        self.assertEqual(0, r['summary']['relation_count'])

    def test_unknown_property_is_not_found(self):
        proc = _run('rnd_item.nope')
        self.assertEqual(1, proc.returncode)
        data = json.loads(proc.stdout)
        self.assertFalse(data['ok'])
        self.assertIn('not_found', data['error'])


if __name__ == '__main__':
    unittest.main()
