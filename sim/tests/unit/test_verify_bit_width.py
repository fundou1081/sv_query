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

    def test_real_width_mismatch_is_reported(self):
        g = SignalGraph()
        parent = TraceNode(id="top.bus", name="bus", module="top",
                           kind=NodeKind.SIGNAL, width=(7, 0))
        child = TraceNode(id="top.bus[4:3]", name="bus[4:3]", module="top",
                          kind=NodeKind.SIGNAL, width=(4, 3),
                          parent="top.bus", bit_range="[4:3]",
                          parent_bit_start=4, parent_bit_end=4)
        g.add_trace_node(parent)
        g.add_trace_node(child)
        result = _check_bit_mapping(g, ["top.bus[4:3]"])
        # A malformed range span is caught by the range check; either kind is a
        # true positive (the point is that a real inconsistency is reported).
        self.assertTrue({"width_mismatch", "bit_range_mismatch"}
                        & {v["kind"] for v in result["violations"]})

    def test_generate_bracket_in_ancestor_is_not_parent_mismatch(self):
        g = SignalGraph()
        parent = TraceNode(id="top.gen[0].u", name="u", module="top",
                           kind=NodeKind.INSTANTIATED_MODULE, width=(0, 0))
        child = TraceNode(id="top.gen[0].u.cfg", name="cfg", module="top",
                          kind=NodeKind.SIGNAL, width=(0, 0),
                          parent="top.gen[0].u")
        g.add_trace_node(parent)
        g.add_trace_node(child)
        result = _check_bit_mapping(g, ["top.gen[0].u.cfg"])
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
