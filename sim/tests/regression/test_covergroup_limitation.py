"""Coverage limitation must be explicit in the CLI schema, never silent.

Root cause is a pyslang covergroup-body builtin-name shadow (`start`/`stop`):
InvalidCoverageExpr / VoidAssignment / InvalidBinsTarget.  sv_query keeps the
strict semantic-AST rule and tells the agent to read the source instead of
trying to extract partial coverage.
"""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from sv_query.trace.core.compiler import CompilationError  # noqa: E402
from sv_query.trace.core.covergroup_extractor import CovergroupExtractor  # noqa: E402

_FIXTURES = os.path.join(os.path.dirname(__file__), '..', 'fixtures')
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def _src(name: str) -> str:
    with open(os.path.join(_FIXTURES, name), encoding='utf-8') as f:
        return f.read()


class TestCoverageLimitation(unittest.TestCase):
    def test_strict_extractor_raises_with_structured_errors(self):
        e = CovergroupExtractor({'shadow.sv': _src('covergroup_builtin_shadow.sv')})
        with self.assertRaises(CompilationError) as ctx:
            e.extract()
        codes = {x.get('code') for x in ctx.exception.errors}
        self.assertIn('InvalidCoverageExpr', codes)

    def test_inherited_member_is_not_a_limitation(self):
        e = CovergroupExtractor({'inherit.sv': _src('covergroup_inherited_member.sv')})
        cgs = e.extract()
        self.assertEqual({'base_cg', 'derived_cg'}, {cg.name for cg in cgs})

    def test_cli_json_carries_coverage_limitation(self):
        fixture = os.path.join(_FIXTURES, 'covergroup_builtin_shadow.sv')
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, 'run_cli.py'),
             'trace', 'covergroups', '-f', fixture, '--json'],
            capture_output=True, text=True, cwd=_ROOT)
        self.assertEqual(1, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertFalse(data['ok'])
        lim = data['coverage_limitation']
        self.assertEqual('unavailable', lim['status'])
        self.assertIn('pyslang', lim['reason'])
        self.assertIn('InvalidCoverageExpr', lim['codes'])
        self.assertTrue(lim['source_locations'])
        self.assertIn('read', lim['agent_action'].lower())
        self.assertIn('InvalidCoverageExpr', {e.get('code') for e in data['errors']})

    def _run_cli(self, *args):
        fixture = os.path.join(_FIXTURES, 'covergroup_builtin_shadow.sv')
        return subprocess.run(
            [sys.executable, os.path.join(_ROOT, 'run_cli.py'), *args,
             '-f', fixture, '--json'],
            capture_output=True, text=True, cwd=_ROOT)

    def test_trace_covergroup_parity(self):
        proc = self._run_cli('trace', 'covergroup', 'cg')
        self.assertEqual(1, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertEqual('trace_covergroup', data['command'])
        self.assertEqual('unavailable', data['coverage_limitation']['status'])

    def test_trace_coverpoints_parity(self):
        proc = self._run_cli('trace', 'coverpoints', 'top.fbyte')
        self.assertEqual(1, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        self.assertEqual('trace_coverpoints', data['command'])
        self.assertEqual('unavailable', data['coverage_limitation']['status'])


if __name__ == '__main__':
    unittest.main()
