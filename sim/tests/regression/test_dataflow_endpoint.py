"""Dataflow endpoint fidelity: paths must end at the requested dst."""
import json
import os
import subprocess
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FL = os.path.join(os.path.dirname(__file__), '..', 'fixtures',
                   'minimal_3module', 'filelist.f')


def _run(src, dst):
    return subprocess.run([sys.executable, os.path.join(_ROOT, 'run_cli.py'),
                           'dataflow', 'analyze', src, dst,
                           '--filelist', _FL, '--json'],
                          capture_output=True, text=True, cwd=_ROOT)


class TestDataflowEndpoint(unittest.TestCase):
    def test_parent_candidate_is_not_reported_as_reached_target(self):
        p = _run('top_minimal.clk', 'top_minimal.sa1.rst_n')
        self.assertEqual(0, p.returncode, p.stderr[-1000:])
        r = json.loads(p.stdout)['result']
        self.assertFalse(r['is_reachable'])
        self.assertEqual(0, r['paths_count'])

    def test_every_reported_path_ends_at_requested_dst(self):
        p = _run('top_minimal.sa1.valid_i', 'top_minimal.sa1.ready_o')
        self.assertEqual(0, p.returncode, p.stderr[-1000:])
        r = json.loads(p.stdout)['result']
        self.assertTrue(r['is_reachable'])
        for path in r['paths']:
            segs = path.get('segments', [])
            if segs:
                self.assertEqual('top_minimal.sa1.ready_o', segs[-1]['to_signal'])


if __name__ == '__main__':
    unittest.main()
