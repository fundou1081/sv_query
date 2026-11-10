"""Single-bit bit_range must not be treated as a 2-bit (1,0) sentinel."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from cli.core.semantic.verify import _check_bit_mapping  # noqa: E402
from trace.core.graph.models import NodeKind, SignalGraph, TraceNode  # noqa: E402


class TestVerifyBitWidth(unittest.TestCase):
    def test_single_bit_range_uses_explicit_span(self):
        g = SignalGraph()
        parent = TraceNode(id="top.bus", name="bus", module="top",
                           kind=NodeKind.SIGNAL, width=(7, 0))
        child = TraceNode(id="top.bus[3]", name="bus[3]", module="top",
                          kind=NodeKind.SIGNAL, width=(1, 0),
                          parent="top.bus", bit_range="[3]",
                          parent_bit_start=3, parent_bit_end=3)
        g.add_trace_node(parent)
        g.add_trace_node(child)
        result = _check_bit_mapping(g, ["top.bus[3]"])
        self.assertEqual([], result["violations"])

    def test_real_multi_bit_range_still_checks_width(self):
        g = SignalGraph()
        parent = TraceNode(id="top.bus", name="bus", module="top",
                           kind=NodeKind.SIGNAL, width=(7, 0))
        child = TraceNode(id="top.bus[4:3]", name="bus[4:3]", module="top",
                          kind=NodeKind.SIGNAL, width=(4, 3),
                          parent="top.bus", bit_range="[4:3]",
                          parent_bit_start=4, parent_bit_end=3)
        g.add_trace_node(parent)
        g.add_trace_node(child)
        result = _check_bit_mapping(g, ["top.bus[4:3]"])
        self.assertEqual([], result["violations"])


if __name__ == '__main__':
    unittest.main()
