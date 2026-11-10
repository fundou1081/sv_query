"""Constraint solve-before and dist metadata."""
import json
import os
import subprocess
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures',
                        'constraint_neighborhood.sv')


def _constraints(prop):
    proc = subprocess.run(
        [sys.executable, os.path.join(_ROOT, 'run_cli.py'), 'trace',
         'constraints', prop, '-f', _FIXTURE, '--json'],
        capture_output=True, text=True, cwd=_ROOT)
    assert proc.returncode == 0, proc.stderr[-1000:]
    return json.loads(proc.stdout)['result']['constraints']


class TestConstraintSolveDist(unittest.TestCase):
    def test_solve_before_is_reported(self):
        blocks = {b['block']: b for b in _constraints('rnd_item.b')}
        solve = blocks['rnd_item.c_ab']['solve_before']
        self.assertEqual(['rnd_item.a'], solve[0]['before'])
        self.assertEqual('rnd_item.c_ab', blocks['rnd_item.c_ab']['id'])

    def test_dist_weights_are_reported(self):
        blocks = {b['block']: b for b in _constraints('rnd_item.e')}
        dist = blocks['rnd_item.c_de']['dist']
        items = dist[0]['items']
        self.assertEqual('0', items[0]['value'])
        self.assertEqual('1', items[0]['weight'])
        self.assertEqual('1', items[1]['value'])
        self.assertEqual('3', items[1]['weight'])


if __name__ == '__main__':
    unittest.main()
