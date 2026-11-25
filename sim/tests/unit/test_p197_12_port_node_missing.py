"""P197.12 — port_node_missing is shared by CLI/session consistency."""
from __future__ import annotations

from sv_query.cli.core.semantic import verify as cli_verify
from sv_query.trace.core.graph.models import NodeKind, SignalGraph, TraceNode
from sv_query.trace.core.query import session_ops, verification


class _Port:
    internal_signal = "top.data"


class _Inst:
    ports = {"p": _Port()}


class _Mig:
    instances = {"top.u": _Inst()}


class _Tracer:
    def __init__(self, graph):
        self._graph = graph
        self._mig = _Mig()

    def get_graph(self):
        return self._graph

    def get_module_graph(self):
        return self._mig


def _graph():
    graph = SignalGraph()
    graph.add_trace_node(TraceNode(
        id="top.data", name="data", module="top",
        kind=NodeKind.SIGNAL, width=(0, 0)))
    return graph


def test_port_node_missing_is_reported_on_shared_paths():
    tracer = _Tracer(_graph())
    graph = tracer.get_graph()
    shared = verification.connection_check(tracer, graph)
    cli = cli_verify._check_connections(tracer, graph)
    session = session_ops._connection_check(tracer, graph)
    for result in (shared, cli, session):
        assert result["checked"] == 1
        assert result["status"] == "fail"
        assert result["violations"][0]["kind"] == "port_node_missing"
