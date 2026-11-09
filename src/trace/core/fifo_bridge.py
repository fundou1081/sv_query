"""Explicit FIFO boundary edges.

A FIFO is sequential storage: its write data is not combinationally connected
to read data.  We add a distinct ``EdgeKind.FIFO`` edge (write -> read) so
dataflow/path queries can opt in to crossing the boundary, while default
structural queries remain unchanged.
"""
from __future__ import annotations

from .graph.models import EdgeKind, TraceEdge

_WRITE = ("fifo_wdata_i", "wdata_i", "wdata", "wr_data", "din")
_READ = ("fifo_rdata_o", "rdata_o", "rdata", "rd_data", "dout")


class FifoBridgeBuilder:
    def __init__(self, graph, module_graph):
        self.graph = graph
        self.mig = module_graph

    def build(self) -> None:
        if self.mig is None:
            return
        for inst_id in self.mig.get_all_instances():
            inst = self.mig.get_instance(inst_id)
            if inst is None or not self._is_fifo(inst_id, inst):
                continue
            pair = self._wr_ports(getattr(inst, "ports", {}))
            if pair is None:
                continue
            w, r = pair
            self._add(f"{inst_id}.{w}", f"{inst_id}.{r}")
            self._add_bits(inst_id, w, r)

    @staticmethod
    def _wr_ports(ports) -> tuple[str, str] | None:
        w = next((p for p in ports if p in _WRITE or p.endswith("_wdata_i")), None)
        r = next((p for p in ports if p in _READ or p.endswith("_rdata_o")), None)
        return (w, r) if w and r else None

    @staticmethod
    def _is_fifo(inst_id: str, inst) -> bool:
        return ("fifo" in str(inst.module_type).lower()
                or "fifo" in inst_id.lower())

    def _add_bits(self, inst_id: str, write: str, read: str) -> None:
        prefix = f"{inst_id}.{write}["
        for bit_w in list(self.graph.nodes()):
            if not bit_w.startswith(prefix):
                continue
            suffix = bit_w[len(f"{inst_id}.{write}"):]
            bit_r = f"{inst_id}.{read}{suffix}"
            if bit_r in self.graph.nodes():
                self._add(bit_w, bit_r)


    def _add(self, src: str, dst: str) -> None:
        if src not in self.graph.nodes() or dst not in self.graph.nodes():
            return
        if any(e.kind == EdgeKind.FIFO for e in self.graph.get_edges(src, dst)):
            return
        self.graph.add_trace_edge(TraceEdge(
            src=src, dst=dst, kind=EdgeKind.FIFO,
            assign_type="fifo_state", confidence="medium",
            expression="FIFO state (sequential; write -> read)",
        ))
