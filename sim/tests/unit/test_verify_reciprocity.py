"""Reciprocity compares data edges, not BIT_SELECT hierarchy edges."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from cli.core.semantic.verify import _check_reciprocity  # noqa: E402
from trace.core.graph.models import EdgeKind, NodeKind, SignalGraph, TraceEdge, TraceNode  # noqa: E402
from trace.core.query.signal import SignalTracer  # noqa: E402


class TestVerifyReciprocity(unittest.TestCase):
    def test_bit_select_only_pair_is_not_a_reciprocity_violation(self):
        g = SignalGraph()
        for nid, kind in [("top.a", NodeKind.SIGNAL), ("top.b", NodeKind.PORT_IN)]:
            g.add_trace_node(TraceNode(id=nid, name=nid.rsplit(".", 1)[-1],
                                       module="top", kind=kind, width=(0, 0)))
        g.add_trace_edge(TraceEdge(src="top.a", dst="top.b",
                                   kind=EdgeKind.BIT_SELECT,
                                   assign_type="internal"))
        result = _check_reciprocity(SignalTracer(g, mig=None), g, ["top.b"],
                                    max_nodes=10)
        self.assertEqual([], result["violations"])


if __name__ == '__main__':
    unittest.main()
