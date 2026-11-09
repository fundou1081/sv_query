"""Partial covergroup extraction when pyslang rejects builtin-shadowed names.

pyslang raises InvalidCoverageExpr/VoidAssignment for covergroup-body
identifiers named `start`/`stop` (CovergroupBody builtin names).  The semantic
root is still available.  `trace covergroups --partial` intentionally exposes
that partial root, with explicit errors, instead of silently returning zero
covergroups.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import CompilationError  # noqa: E402
from trace.core.covergroup_extractor import CovergroupExtractor  # noqa: E402

_FIXTURES = os.path.join(os.path.dirname(__file__), '..', 'fixtures')


def _src(name: str) -> str:
    with open(os.path.join(_FIXTURES, name), encoding='utf-8') as f:
        return f.read()


class TestCovergroupPartialExtraction(unittest.TestCase):
    def test_builtin_shadow_partial_returns_definitions(self):
        e = CovergroupExtractor({'shadow.sv': _src('covergroup_builtin_shadow.sv')})
        cgs = e.extract(allow_partial=True)
        self.assertTrue(e.partial)
        self.assertEqual(1, len(cgs))
        self.assertEqual('cg', cgs[0].name)
        names = {cp.name for cp in cgs[0].coverpoints}
        self.assertIn('cp_start', names)
        self.assertIn('cp_stop', names)
        # explicit error codes are attached; no silent success
        self.assertIn('InvalidCoverageExpr', cgs[0].errors)

    def test_strict_mode_still_raises(self):
        e = CovergroupExtractor({'shadow.sv': _src('covergroup_builtin_shadow.sv')})
        with self.assertRaises(CompilationError):
            e.extract(allow_partial=False)

    def test_inherited_member_is_not_partial(self):
        e = CovergroupExtractor({'inherit.sv': _src('covergroup_inherited_member.sv')})
        cgs = e.extract(allow_partial=True)
        self.assertFalse(e.partial)
        self.assertEqual({'base_cg', 'derived_cg'}, {cg.name for cg in cgs})
        for cg in cgs:
            self.assertEqual('cfg', cg.coverpoints[0].name)


if __name__ == '__main__':
    unittest.main()
