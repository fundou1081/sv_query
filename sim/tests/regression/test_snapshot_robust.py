"""P158.7: malformed snapshots are visible, never crash the list; tags are filename-authoritative."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIX = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'arch_pair.sv')


def _run(args, env):
    return subprocess.run([sys.executable, os.path.join(_ROOT, 'run_cli.py'),
                           *args, '--json'], capture_output=True, text=True,
                          cwd=_ROOT, env=env)


class TestSnapshotRobust(unittest.TestCase):
    def test_bad_snapshot_is_visible_not_fatal(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env['SVQ_SNAPSHOT_DIR'] = td
            save = _run(['snapshot', 'save', _FIX, '--tag', 'good'], env)
            self.assertEqual(0, save.returncode, save.stderr[-1000:])
            with open(os.path.join(td, 'bad.json'), 'w') as f:
                f.write('{not-json')
            with open(os.path.join(td, 'shape.json'), 'w') as f:
                json.dump([], f)

            p = _run(['snapshot', 'list'], env)
            self.assertEqual(0, p.returncode, p.stderr[-1000:])
            entries = {e['tag']: e for e in json.loads(p.stdout)}
            self.assertTrue(entries['good']['module_graph_present'])
            self.assertIn('error', entries['bad'])
            self.assertIn('error', entries['shape'])

            p = _run(['snapshot', 'list', 'bad'], env)
            self.assertEqual(1, p.returncode)
            self.assertIn('invalid snapshot', p.stdout)
            self.assertNotIn('Traceback', p.stderr)

    def test_filename_is_authoritative_tag(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env['SVQ_SNAPSHOT_DIR'] = td
            save = _run(['snapshot', 'save', _FIX, '--tag', 'filename'], env)
            self.assertEqual(0, save.returncode, save.stderr[-1000:])
            path = os.path.join(td, 'filename.json')
            data = json.load(open(path))
            data['tag'] = 'body_tag'
            with open(path, 'w') as f:
                json.dump(data, f)
            p = _run(['snapshot', 'list', 'filename'], env)
            self.assertEqual(0, p.returncode, p.stderr[-1000:])
            info = json.loads(p.stdout)
            self.assertEqual('filename', info['tag'])
            self.assertEqual('body_tag', info['tag_mismatch'])

    def test_dataflow_uses_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env['SVQ_SNAPSHOT_DIR'] = td
            save = _run(['snapshot', 'save', _FIX, '--tag', 'df'], env)
            self.assertEqual(0, save.returncode, save.stderr[-1000:])
            p = _run(['dataflow', 'analyze', 'top.x', 'top.y',
                      '--from-snapshot', 'df'], env)
            self.assertEqual(0, p.returncode, p.stderr[-1000:])
            r = json.loads(p.stdout)['result']
            self.assertTrue(r['is_reachable'])
            self.assertEqual(1, r['paths_count'])
            self.assertEqual('df', json.loads(p.stdout)['params']['from_snapshot'])
            # mutually exclusive with source input
            p = _run(['dataflow', 'analyze', 'top.x', 'top.y',
                      '--from-snapshot', 'df', '-f', _FIX], env)
            self.assertEqual(1, p.returncode)
            self.assertIn('mutually exclusive', p.stdout)

    def test_snapshot_mig_roundtrip_and_tracer(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env['SVQ_SNAPSHOT_DIR'] = td
            save = _run(['snapshot', 'save', _FIX, '--tag', 'mig'], env)
            self.assertEqual(0, save.returncode, save.stderr[-1000:])
            data = json.load(open(os.path.join(td, 'mig.json')))
            self.assertIn('module_ports', data['module_graph'])
            sys.path.insert(0, os.path.join(_ROOT, 'src'))
            from cli.core.semantic.trace_common import _load_tracer_from_snapshot
            from unittest import mock
            with mock.patch.dict(os.environ, {'SVQ_SNAPSHOT_DIR': td}):
                tracer = _load_tracer_from_snapshot('mig')
            self.assertIsNotNone(tracer.get_module_graph())
            self.assertIsNotNone(tracer.get_path_resolver())
            self.assertIsNone(tracer.get_class_hierarchy())


if __name__ == '__main__':
    unittest.main()
