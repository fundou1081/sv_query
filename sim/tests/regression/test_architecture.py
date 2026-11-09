"""Module/instance architecture graph from real CONNECTION edges."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'arch_pair.sv')


def _run(*extra):
    return subprocess.run(
        [sys.executable, os.path.join(_ROOT, 'run_cli.py'),
         'architecture', 'graph', '-f', _FIXTURE, '--json', *extra],
        capture_output=True, text=True, cwd=_ROOT)


class TestArchitectureGraph(unittest.TestCase):
    def test_real_net_between_instances(self):
        proc = _run()
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        r = json.loads(proc.stdout)['result']
        ids = {n['id'] for n in r['nodes']}
        self.assertEqual({'top.u0', 'top.u1'}, ids)
        edge = r['edges'][0]
        self.assertEqual(('top.u0', 'top.u1', 'top.w'), (edge['src'], edge['dst'], edge['net']))
        self.assertEqual(('b', 'a'), (edge['src_port'], edge['dst_port']))
        self.assertEqual(('output', 'input'), (edge['src_direction'], edge['dst_direction']))
        self.assertEqual(2, r['stats']['boundaries'])

    @unittest.skipUnless(shutil.which("dot"), "graphviz dot not installed")
    def test_json_plus_svg_writes_both(self):
        with tempfile.TemporaryDirectory() as td:
            svg = os.path.join(td, "arch.svg")
            proc = subprocess.run(
                [sys.executable, os.path.join(_ROOT, 'run_cli.py'),
                 'architecture', 'graph', '-f', _FIXTURE,
                 '--json', '--svg', svg],
                capture_output=True, text=True, cwd=_ROOT)
            self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
            data = json.loads(proc.stdout)
            self.assertEqual(1, data['result']['stats']['connections'])
            self.assertTrue(os.path.isfile(svg))
            self.assertGreater(os.path.getsize(svg), 0)

    def test_dot_is_generated(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, 'run_cli.py'),
             'architecture', 'graph', '-f', _FIXTURE],
            capture_output=True, text=True, cwd=_ROOT)
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        self.assertIn('digraph architecture', proc.stdout)
        self.assertIn('top.w', proc.stdout)


if __name__ == '__main__':
    unittest.main()
