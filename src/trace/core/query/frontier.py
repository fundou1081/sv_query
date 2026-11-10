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
    except Exception as e:
        raise ValueError(f"frontier traversal failed: {e}") from e
    out = []
    for nxt in nxts:
        edges = (graph.get_edges(node, nxt) if direction == "fanout"
                 else graph.get_edges(nxt, node))
        if any(str(getattr(e, "kind", "")).split(".")[-1] in _STRUCTURAL
               for e in edges):
            out.append(nxt)
    return out


def _probes_for_node(graph, node: str, instance: str) -> tuple[str, list[str]]:
    if instance:
        return instance, [f"connections {instance}", f"instances {instance}",
                          f"ports {instance}"]
    nd = graph.get_node(node) if hasattr(graph, "get_node") else None
    kind = getattr(getattr(nd, "kind", None), "name", "")
    owner = _owner(node) if kind.startswith("PORT") else ""
    if owner:
        return owner, [f"connections {owner}", f"instances {owner}",
                       f"ports {owner}"]
    return "", [f"drivers {node}", f"loads {node}", f"evidence {node}"]


def _boundary(graph, node: str, direction: str, path: list[str],
              reason: str, instance: str = "") -> Frontier:
    owner, probes = _probes_for_node(graph, node, instance)
    return Frontier(direction, node, path, reason, owner, probes)

def _boundary_for_step(graph, nxt: str, direction: str, path: list[str],
                       depth: int, max_depth: int) -> Frontier | None:
    nd = graph.get_node(nxt) if hasattr(graph, "get_node") else None
    if nd is not None and getattr(nd, "kind", None).name == "INSTANTIATED_MODULE":
        return _boundary(graph, nxt, direction, path + [nxt],
                         "instance_boundary", instance=nxt)
    if depth + 1 > max_depth:
        return _boundary(graph, nxt, direction, path + [nxt], "depth_limit")
    return None


def _consume_neighbors(graph, cur: str, nxts: list[str], direction: str,
                        path: list[str], depth: int, max_depth: int,
                        max_frontier: int, seen: set[str],
                        queue: deque, frontier: list[Frontier]) -> tuple[bool, bool]:
    progress = False
    for nxt in nxts:
        if nxt in seen:
            continue
        boundary = _boundary_for_step(graph, nxt, direction, path,
                                      depth, max_depth)
        if boundary is not None:
            if len(frontier) >= max_frontier:
                return True, True
            frontier.append(boundary)
            progress = True
            continue
        seen.add(nxt)
        queue.append((nxt, path + [nxt], depth + 1))
        progress = True
    return progress, False


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
        progress, capped = _consume_neighbors(
            graph, cur, nxts, direction, path, depth, max_depth,
            max_frontier, seen, queue, frontier)
        if capped:
            truncated = True
            break
        if not progress:
            if len(frontier) >= max_frontier:
                truncated = True
                break
            frontier.append(_boundary(graph, cur, direction, path,
                                      "cycle_or_all_seen"))
    return frontier, truncated

def _dedupe_frontier(frontier: list[Frontier]) -> list[Frontier]:
    best: dict[tuple[str, str], Frontier] = {}
    for item in frontier:
        key = (item.direction, item.node)
        old = best.get(key)
        if old is None or len(item.path) < len(old.path):
            best[key] = item
    return list(best.values())


def _validate_limits(max_depth: int, max_frontier: int) -> None:
    if max_depth < 1:
        raise ValueError("--max-depth must be >= 1")
    if max_frontier < 1:
        raise ValueError("--max-frontier must be >= 1")



def analyze_frontier(graph, signal: str, direction: str = "both",
                     max_depth: int = 8, max_frontier: int = 50) -> dict:
    _validate_limits(max_depth, max_frontier)
    directions = ["fanin", "fanout"] if direction == "both" else [direction]
    found_all: list[Frontier] = []
    truncated = False
    for d in directions:
        remaining = max_frontier - len(found_all)
        if remaining <= 0:
            truncated = True
            break
        found, cut = _walk_direction(graph, signal, d, max_depth, remaining)
        found_all.extend(found)
        truncated = truncated or cut or len(found_all) >= max_frontier
    found_all = _dedupe_frontier(found_all)
    rows = [{
        "direction": f.direction, "node": f.node, "reason": f.reason,
        "instance": f.instance, "path": f.path,
        "next_probes": f.next_probes,
    } for f in found_all]
    return {"signal": signal, "frontier": rows,
            "summary": {"frontier_count": len(rows), "truncated": truncated,
                        "max_depth": max_depth, "max_frontier": max_frontier},
            "note": "generic boundary frontier; no semantic classification"}
