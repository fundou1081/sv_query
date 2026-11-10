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
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures',
                        'explicit_boundary.sv')
_EVIDENCE = "sim/tests/fixtures/explicit_boundary.sv:1"


def _entry(src, dst, **extra):
    item = {"src": src, "dst": dst, "kind": "fifo_state",
            "evidence": _EVIDENCE, "confidence": "medium"}
    item.update(extra)
    return item


def _run(boundaries, src='top.x', dst='top.y'):
    map_data = {"adapter": "test", "boundaries": boundaries}
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(map_data, f)
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
        proc = _run([])
        self.assertEqual(2, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertEqual('boundary', data['status'])
        self.assertEqual([], data['chain'])
        self.assertTrue(data['frontier']['frontier'])

    def test_explicit_boundary_composes_marked_chain(self):
        proc = _run([_entry('top.p', 'top.q')])
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertEqual('traced', data['status'])
        self.assertFalse(data['proven'])
        self.assertEqual(1, len(data['boundary_hops']))
        self.assertIn('explicit_boundary',
                      [s['kind'] for s in data['segments']])
        self.assertIn('top.p', data['chain'])
        self.assertIn('top.q', data['chain'])

    def test_fake_but_syntactically_valid_map_is_asserted_not_proven(self):
        # This pair is not a FIFO; the runner must not claim semantic proof.
        proc = _run([_entry('top.p', 'top.y')])
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertEqual('traced', data['status'])
        self.assertFalse(data['proven'])
        self.assertTrue(data['asserted_relation'])

    def test_multiple_viable_boundaries_are_ambiguous(self):
        proc = _run([_entry('top.p', 'top.q'), _entry('top.x', 'top.q')])
        self.assertEqual(2, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertEqual('ambiguous', data['status'])
        self.assertEqual([], data['chain'])
        self.assertGreater(len(data['candidates']), 1)

    def test_missing_evidence_is_rejected(self):
        proc = _run([{"src": "top.p", "dst": "top.q", "kind": "fifo_state",
                      "confidence": "medium"}])
        self.assertEqual(1, proc.returncode)
        self.assertFalse(json.loads(proc.stdout)['ok'])

    def test_malformed_boundary_is_explicit(self):
        proc = _run(["top.p"])
        self.assertEqual(1, proc.returncode)
        self.assertFalse(json.loads(proc.stdout)['ok'])


if __name__ == '__main__':
    unittest.main()
