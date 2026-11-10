"""Boundary-aware trace frontier.

This is deliberately generic: it reports where a structural trace stops and
which probes an agent should run next.  It never classifies a boundary as a
FIFO or invents a missing edge.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

_STRUCTURAL = {"DRIVER", "CONNECTION", "BIT_SELECT"}


@dataclass
class Frontier:
    direction: str
    node: str
    path: list[str]
    reason: str
    instance: str = ""
    next_probes: list[str] = field(default_factory=list)


def _owner(node_id: str) -> str:
    base = node_id
    if "[" in base:
        base = base.split("[", 1)[0]
    return base.rsplit(".", 1)[0] if "." in base else ""


def _structural_neighbors(graph, node: str, direction: str) -> list[str]:
    try:
        nxts = (graph.successors(node) if direction == "fanout"
                else graph.predecessors(node))
    except Exception:
        return []
    out = []
    for nxt in nxts:
        edges = (graph.get_edges(node, nxt) if direction == "fanout"
                 else graph.get_edges(nxt, node))
        if any(str(getattr(e, "kind", "")).split(".")[-1] in _STRUCTURAL
               for e in edges):
            out.append(nxt)
    return out


def _boundary(graph, node: str, direction: str, path: list[str],
              reason: str) -> Frontier:
    nd = graph.get_node(node) if hasattr(graph, "get_node") else None
    owner = _owner(node)
    probes = ([f"connections {owner}", f"instances {owner}", f"ports {owner}"]
              if owner else [f"drivers {node}", f"loads {node}",
                             f"evidence {node}"])
    return Frontier(direction, node, path, reason, owner, probes)


def _boundary_for_step(graph, nxt: str, direction: str, path: list[str],
                       depth: int, max_depth: int) -> Frontier | None:
    nd = graph.get_node(nxt) if hasattr(graph, "get_node") else None
    if nd is not None and getattr(nd, "kind", None).name == "INSTANTIATED_MODULE":
        return _boundary(graph, nxt, direction, path + [nxt], "instance_boundary")
    if depth + 1 >= max_depth:
        return _boundary(graph, nxt, direction, path + [nxt], "depth_limit")
    return None


def _walk_direction(graph, signal: str, direction: str,
                    max_depth: int, max_frontier: int) -> tuple[list[Frontier], bool]:
    frontier: list[Frontier] = []
    visited_total = 0
    truncated = False
    queue = deque([(signal, [signal], 0)])
    seen = {signal}
    while queue:
        cur, path, depth = queue.popleft()
        visited_total += 1
        if visited_total > 2000 or len(frontier) >= max_frontier:
            truncated = True
            break
        nxts = _structural_neighbors(graph, cur, direction)
        if not nxts:
            frontier.append(_boundary(graph, cur, direction, path, "no_structural_edge"))
            continue
        for nxt in nxts:
            if nxt in seen:
                continue
            boundary = _boundary_for_step(graph, nxt, direction, path,
                                          depth, max_depth)
            if boundary is not None:
                frontier.append(boundary)
                continue
            seen.add(nxt)
            queue.append((nxt, path + [nxt], depth + 1))
    return frontier, truncated

def analyze_frontier(graph, signal: str, direction: str = "both",
                     max_depth: int = 8, max_frontier: int = 50) -> dict:
    directions = ["fanin", "fanout"] if direction == "both" else [direction]
    rows = []
    truncated = False
    for d in directions:
        found, cut = _walk_direction(graph, signal, d, max_depth, max_frontier)
        truncated = truncated or cut
        rows.extend({
            "direction": f.direction, "node": f.node, "reason": f.reason,
            "instance": f.instance, "path": f.path,
            "next_probes": f.next_probes,
        } for f in found)
    return {"signal": signal, "frontier": rows,
            "summary": {"frontier_count": len(rows), "truncated": truncated,
                        "max_depth": max_depth},
            "note": "generic boundary frontier; not a FIFO classification"}
