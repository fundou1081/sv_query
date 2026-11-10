"""P140 external boundary adapter: explicit map only, no auto inference."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_RUNNER = os.path.join(_ROOT, 'examples', 'project_adaptations',
                       'opentitan_fifo', 'trace_with_map.py')
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'arch_pair.sv')


def _run(map_data=None, src='top.x', dst='top.y'):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(map_data or {"adapter": "test", "boundaries": []}, f)
        path = f.name
    try:
        return subprocess.run(
            [sys.executable, _RUNNER, src, dst, '--file', _FIXTURE,
             '--map', path],
            capture_output=True, text=True, cwd=_ROOT)
    finally:
        os.unlink(path)


class TestProjectAdaptation(unittest.TestCase):
    def test_empty_map_stops_at_frontier(self):
        proc = _run()
        self.assertEqual(2, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertEqual('boundary', data['status'])
        self.assertEqual([], data['chain'])
        self.assertTrue(data['frontier']['frontier'])

    def test_missing_evidence_is_rejected(self):
        proc = _run({"adapter": "bad", "boundaries": [{
            "src": "top.x", "dst": "top.y", "kind": "fifo_state",
            "confidence": "medium"}]})
        self.assertEqual(1, proc.returncode)
        self.assertFalse(json.loads(proc.stdout)['ok'])


if __name__ == '__main__':
    unittest.main()
