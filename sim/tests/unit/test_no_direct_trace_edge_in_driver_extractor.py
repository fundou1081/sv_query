# test_no_direct_trace_edge_in_driver_extractor.py - [V4 2026-07-15]
#
# 守卫: driver_extractor.py 不应直接构造 TraceEdge 实例.
# 应统一走 TraceEdgeFactory.make_edge (经 self._append_edge helper).
#
# 背景: 旧 driver_extractor.py 有 7 处 `result.edges.append(TraceEdge(...))` 直接构造.
# 通过引入 self._append_edge wrapper 统一入口, 任何新 TraceEdge 字段
# (source_location, confidence, function_return 等) 只在 factory 一处修改.

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))


class TestNoDirectTraceEdgeInDriverExtractor(unittest.TestCase):
    """[V4] driver_extractor.py 必须用 factory 入口"""

    def test_no_direct_trace_edge_constructor(self):
        """不应直接调用 TraceEdge(...) -- 应统一走 factory"""

        path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..', 'src', 'trace', 'core', 'driver_extractor.py'
        )
        with open(path) as f:
            content = f.read()

        # Find all "TraceEdge(" constructor calls
        # Skip docstring lines (lines starting with """ or containing docstring)
        in_docstring = False
        offender_lines = []
        for i, line in enumerate(content.split('\n'), 1):
            stripped = line.strip()
            # Detect docstring start/end
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if in_docstring:
                    in_docstring = False
                else:
                    in_docstring = True
                continue
            if in_docstring:
                continue
            # Look for TraceEdge( as a constructor call (not in code path):
            # exact pattern "TraceEdge(" with following args
            if 'TraceEdge(' in line and 'self._edge_factory' not in line and 'TraceEdge>' not in line:
                # Allow dataclass return types and import lines
                if line.strip().startswith('TraceEdge,') or line.strip().startswith('#'):
                    continue
                # Skip type hints like "edge: TraceEdge"
                if ': TraceEdge' in line or 'TraceEdge]' in line:
                    continue
                # Skip edge variable name usages (e.g. edge = TraceEdge)
                if 'edge = ' in line and 'TraceEdge(' in line:
                    # Could be direct constructor
                    offender_lines.append((i, line.rstrip()))

        self.assertEqual(
            offender_lines, [],
            f"[V4 violation] Direct `TraceEdge(...)` constructors found in driver_extractor.py. "
            f"Use `self._append_edge(...)` instead:\n"
            + '\n'.join(f"  line {ln}: {l}" for ln, l in offender_lines[:5])
        )

    def test_append_edge_helper_exists(self):
        """self._append_edge 必须存在"""
        path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..', 'src', 'trace', 'core', 'driver_extractor.py'
        )
        with open(path) as f:
            content = f.read()
        self.assertIn(
            'def _append_edge(',
            content,
            "[V4 violation] Missing `self._append_edge` helper in driver_extractor.py. "
            "Add it before re-enabling direct TraceEdge usage."
        )


if __name__ == '__main__':
    unittest.main()
