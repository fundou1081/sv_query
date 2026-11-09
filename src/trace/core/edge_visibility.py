"""Central edge visibility policy.

FIFO edges are sequential data boundaries, not combinational structure.  They
are stored in the graph only when explicitly built, and every default consumer
must ignore them unless it opts in.
"""
from __future__ import annotations


def edge_visible(edge, include_fifo: bool = False) -> bool:
    return include_fifo or str(getattr(edge, "kind", "")).split(".")[-1] != "FIFO"


def _collect(graph, node, candidates, include_fifo: bool, reverse: bool) -> list[str]:
    out = []
    for nxt in candidates:
        nd = graph.get_node(nxt) if hasattr(graph, "get_node") else None
        if (nd is not None and getattr(nd, "kind", None).name == "INSTANTIATED_MODULE"
                and "fifo" in str(getattr(nd, "module", "")).lower()):
            continue  # FIFO instance anchor: no structural shortcut
        edges = graph.get_edges(nxt, node) if reverse else graph.get_edges(node, nxt)
        if any(edge_visible(e, include_fifo) for e in edges):
            out.append(nxt)
    return out


def visible_neighbors(graph, node: str, directed: bool = False,
                      include_fifo: bool = False) -> list[str]:
    try:
        successors = list(graph.successors(node))
    except Exception:
        successors = []
    out = _collect(graph, node, successors, include_fifo, reverse=False)
    if directed:
        return out
    try:
        predecessors = list(graph.predecessors(node))
    except Exception:
        predecessors = []
    out.extend(_collect(graph, node, predecessors, include_fifo, reverse=True))
    return out
