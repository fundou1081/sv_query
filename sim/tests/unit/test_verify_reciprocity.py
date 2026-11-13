"""Reciprocity compares data edges, not BIT_SELECT hierarchy edges."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from cli.core.semantic.verify import _check_reciprocity  # noqa: E402
from sv_query.trace.core.graph.models import EdgeKind, NodeKind, SignalGraph, TraceEdge, TraceNode  # noqa: E402
from sv_query.trace.core.query.signal import SignalTracer  # noqa: E402


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


class _FakeTracer:
    def trace_fanin(self, node, depth=1):
        return [g.get_node("top.a")] if node == "top.b" else []
    def trace_fanout(self, node, depth=1, **kw):
        return []


def test_real_asymmetry_is_reported():
    global g
    g = SignalGraph()
    for nid in ("top.a", "top.b"):
        g.add_trace_node(TraceNode(id=nid, name=nid.rsplit(".", 1)[-1],
                                   module="top", kind=NodeKind.SIGNAL,
                                   width=(0, 0)))
    g.add_trace_edge(TraceEdge(src="top.a", dst="top.b", kind=EdgeKind.DRIVER))
    result = _check_reciprocity(_FakeTracer(), g, ["top.b"], max_nodes=10)
    assert "fanin_not_reciprocal" in {v["kind"] for v in result["violations"]}
