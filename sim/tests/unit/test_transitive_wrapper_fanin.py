"""Transitive fanin must retain a wrapper-passthrough PORT_OUT ancestor."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from sv_query.trace.core.graph.models import EdgeKind, NodeKind, SignalGraph, TraceEdge, TraceNode  # noqa: E402
from sv_query.trace.core.query.signal import SignalTracer  # noqa: E402


def _node(nid, kind):
    return TraceNode(id=nid, name=nid.rsplit(".", 1)[-1], module="top",
                     kind=kind, width=(0, 0))


class TestTransitiveWrapperFanin(unittest.TestCase):
    def test_wrapper_passthrough_source_is_in_transitive_fanin(self):
        g = SignalGraph()
        for nid, kind in [
            ("top.cio", NodeKind.PORT_OUT),
            ("top.sck", NodeKind.SIGNAL),
            ("top.core.sck_o", NodeKind.PORT_OUT),
            ("top.core.u_fsm.sck_o", NodeKind.PORT_OUT),
            ("top.core.u_fsm.sck_q", NodeKind.REG),
        ]:
            g.add_trace_node(_node(nid, kind))

        # core.sck_o is an internal placeholder; fsm.sck_o is its wrapper source.
        g.add_trace_edge(TraceEdge(src="top.core.sck_o", dst="top.core.sck_o",
                                   kind=EdgeKind.DRIVER, assign_type="internal"))
        g.add_trace_edge(TraceEdge(src="top.core.u_fsm.sck_o",
                                   dst="top.core.sck_o", kind=EdgeKind.DRIVER,
                                   assign_type="wrapper_passthrough"))
        g.add_trace_edge(TraceEdge(src="top.core.u_fsm.sck_o",
                                   dst="top.core.sck_o", kind=EdgeKind.CONNECTION,
                                   assign_type="connection"))
        g.add_trace_edge(TraceEdge(src="top.core.u_fsm.sck_q",
                                   dst="top.core.u_fsm.sck_o",
                                   kind=EdgeKind.DRIVER, assign_type="continuous"))
        g.add_trace_edge(TraceEdge(src="top.core.sck_o", dst="top.sck",
                                   kind=EdgeKind.CONNECTION, assign_type="connection"))
        g.add_trace_edge(TraceEdge(src="top.sck", dst="top.cio",
                                   kind=EdgeKind.DRIVER, assign_type="continuous"))

        ids = {n.id for n in SignalTracer(g, mig=None).trace_fanin("top.cio", depth=None)}
        self.assertIn("top.core.u_fsm.sck_o", ids)
        self.assertIn("top.core.sck_o", ids)


if __name__ == '__main__':
    unittest.main()
