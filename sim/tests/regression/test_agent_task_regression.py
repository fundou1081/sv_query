"""P145 portable agent task corpus gate."""
import json
import os
import subprocess
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_TOOL = os.path.join(_ROOT, 'tools', 'agent', 'agent_task_regression.py')


class TestAgentTaskRegression(unittest.TestCase):
    def test_corpus_is_green_and_metrics_are_explicit(self):
        proc = subprocess.run([sys.executable, _TOOL, '--json'],
                              capture_output=True, text=True, cwd=_ROOT)
        self.assertEqual(0, proc.returncode, proc.stdout[-2000:] + proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertEqual(13, data['tasks'])
        self.assertEqual(data['tasks'], data['passed'])
        self.assertEqual(0, data['failed'])
        self.assertEqual(0, data['false_confident'])
        self.assertEqual(0, data['false_found'])
        self.assertEqual({'deep_path', 'deep_reverse', 'dataflow_deep',
                          'verify_deep', 'constraint_chain',
                          'constraint_not_random', 'constraint_unknown',
                          'frontier', 'boundary_trace', 'boundary_empty',
                          'schema_envelope', 'neighborhood_truncated',
                          'coverage_reason'},
                         {r['task'] for r in data['results']})


if __name__ == '__main__':
    unittest.main()
