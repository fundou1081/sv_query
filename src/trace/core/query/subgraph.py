"""[iter_362 / PLAN P60.2] 局部子图查询（core，无渲染依赖）。

给定 canonical seed，沿选定边类型做有预算的 k-hop 邻域遍历。
输出 nodes / edges / boundary / truncated / stats；不做全图 BFS，
不返回布局/颜色/HTML。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..graph.models import EdgeKind, SignalGraph, TraceEdge, TraceNode


class SubgraphError(ValueError):
    """非法参数或未知 seed。"""


_EDGE_NAMES = {
    "driver": {EdgeKind.DRIVER},
    "connection": {EdgeKind.CONNECTION},
    "clock": {EdgeKind.CLOCK},
    "reset": {EdgeKind.RESET},
    "bit_select": {EdgeKind.BIT_SELECT},
    "member_select": {EdgeKind.MEMBER_SELECT},
    "branch": {
        EdgeKind.BRANCH_CONDITION, EdgeKind.BRANCH_TRUE,
        EdgeKind.BRANCH_FALSE, EdgeKind.BRANCH_RESULT,
        EdgeKind.CASE_SELECT, EdgeKind.CASE_ITEM, EdgeKind.CASE_RESULT,
    },
}
_ALLOWED = set(_EDGE_NAMES) | {"control"}
_DEFAULT_KINDS = ("driver", "connection")


@dataclass(frozen=True)
class SubgraphOptions:
    depth: int = 2
    direction: str = "both"
    edge_kinds: tuple[str, ...] = _DEFAULT_KINDS
    max_nodes: int = 80
    max_edges: int = 160
    include_evidence: bool = False


def _parse_kinds(raw: Iterable[str] | None) -> tuple[str, ...]:
    if raw is None:
        return _DEFAULT_KINDS
    if isinstance(raw, str):
        raw = [raw]
    out: list[str] = []
    for item in raw:
        for part in str(item).split(","):
            name = part.strip().lower()
            if not name:
                continue
            if name not in _ALLOWED:
                raise SubgraphError(
                    f"unknown edge kind {name!r}; allowed={sorted(_ALLOWED)}"
                )
            if name not in out:
                out.append(name)
    if not out:
        raise SubgraphError("edge_kinds must not be empty")
    return tuple(out)


def _edge_matches(edge: TraceEdge, kinds: set[str]) -> bool:
    if "control" in kinds and edge.kind == EdgeKind.DRIVER:
        return bool(getattr(edge, "condition", "") or getattr(edge, "condition_chain", None))
    return any(name in kinds and edge.kind in accepted
               for name, accepted in _EDGE_NAMES.items())


def _width_meta(node: TraceNode) -> tuple[int, int, int]:
    w = getattr(node, "width", None)
    if not isinstance(w, (tuple, list)) or len(w) < 2:
        return 0, 0, 0
    try:
        msb, lsb = int(w[0]), int(w[1])
    except (TypeError, ValueError):
        return 0, 0, 0
    return msb, lsb, max(0, abs(msb - lsb) + 1)


def _precision(node: TraceNode, width: int) -> str:
    if getattr(getattr(node, "kind", None), "name", "") == "CONST":
        return "constant"
    if width == 1:
        return "bit"
    if width > 1:
        return "bus"
    return "unknown"


def _node_dict(node: TraceNode, include_evidence: bool) -> dict:
    msb, lsb, width = _width_meta(node)
    item = {
        "id": node.id,
        "kind": getattr(getattr(node, "kind", None), "name", "UNKNOWN"),
        "module": getattr(node, "module", ""),
        "width_msb": msb,
        "width_lsb": lsb,
        "width": width,
        "precision": _precision(node, width),
        "parent": getattr(node, "parent", None),
        "bit_range": getattr(node, "bit_range", None),
        "is_signed": getattr(node, "is_signed", None),
    }
    if include_evidence:
        item["file"] = getattr(node, "file", "") or ""
        item["line"] = getattr(node, "line", 0) or 0
    return item


def _edge_dict(edge: TraceEdge, include_evidence: bool) -> dict:
    item = {
        "src": edge.src,
        "dst": edge.dst,
        "kind": getattr(edge.kind, "name", str(edge.kind)),
        "expression": getattr(edge, "expression", "") or "",
        "condition": getattr(edge, "condition", "") or "",
        "bit_slice": getattr(edge, "bit_slice", "") or "",
        "assign_type": getattr(edge, "assign_type", "") or "",
    }
    if include_evidence:
        loc = getattr(edge, "source_location", None)
        item["file"] = getattr(loc, "file", "") if loc is not None else ""
        item["line"] = getattr(loc, "line_start", 0) if loc is not None else 0
    return item


def _edge_sort_key(edge: TraceEdge):
    return (
        edge.src, edge.dst, getattr(edge.kind, "name", str(edge.kind)),
        getattr(edge, "condition", "") or "",
        getattr(edge, "expression", "") or "",
        getattr(edge, "bit_slice", "") or "",
    )


def _with_overrides(opts: SubgraphOptions, **values) -> SubgraphOptions:
    data = dict(opts.__dict__)
    for key, value in values.items():
        if value is not None:
            data[key] = value
    return SubgraphOptions(**data)


def _validate(opts: SubgraphOptions) -> tuple[str, ...]:
    if opts.depth < 0:
        raise SubgraphError("depth must be >= 0")
    if opts.max_nodes < 1:
        raise SubgraphError("max_nodes must be >= 1")
    if opts.max_edges < 0:
        raise SubgraphError("max_edges must be >= 0")
    if opts.direction not in ("in", "out", "both"):
        raise SubgraphError("direction must be in/out/both")
    return _parse_kinds(opts.edge_kinds)


def _canonical_seeds(graph: SignalGraph, seeds: Iterable[str]) -> list[str]:
    seed_list = []
    for s in seeds:
        sid = str(s).strip()
        if sid and sid not in seed_list:
            seed_list.append(sid)
    if not seed_list:
        raise SubgraphError("at least one seed is required")
    missing = [s for s in seed_list if s not in graph]
    if missing:
        raise SubgraphError(f"seed not in graph: {missing}")
    return seed_list


def _adjacency(graph: SignalGraph, kinds: tuple[str, ...], direction: str):
    out_adj: dict[str, list[tuple[str, TraceEdge]]] = {}
    in_adj: dict[str, list[tuple[str, TraceEdge]]] = {}
    selected: list[TraceEdge] = []
    kind_set = set(kinds)
    for src, dst in graph.edges():
        for edge in graph.get_edges(src, dst):
            if not _edge_matches(edge, kind_set):
                continue
            selected.append(edge)
            if direction in ("out", "both"):
                out_adj.setdefault(src, []).append((dst, edge))
            if direction in ("in", "both"):
                in_adj.setdefault(dst, []).append((src, edge))
    return out_adj, in_adj, selected


def _neighbors(nid: str, opts: SubgraphOptions, out_adj, in_adj):
    acc: list[tuple[str, TraceEdge]] = []
    if opts.direction in ("out", "both"):
        acc.extend(out_adj.get(nid, []))
    if opts.direction in ("in", "both"):
        acc.extend(in_adj.get(nid, []))
    return sorted(acc, key=lambda x: (x[0], _edge_sort_key(x[1])))


def _walk(seed_list, opts: SubgraphOptions, out_adj, in_adj):
    included = set(seed_list)
    boundary: set[str] = set()
    depth_truncated = False
    node_truncated = False
    max_depth = 0
    queue = [(s, 0) for s in seed_list]
    qidx = 0
    while qidx < len(queue):
        cur, cur_depth = queue[qidx]
        qidx += 1
        for nxt, _edge in _neighbors(cur, opts, out_adj, in_adj):
            if nxt in included:
                continue
            if cur_depth >= opts.depth:
                boundary.add(nxt)
                depth_truncated = True
                continue
            if len(included) >= opts.max_nodes:
                boundary.add(nxt)
                node_truncated = True
                continue
            included.add(nxt)
            max_depth = max(max_depth, cur_depth + 1)
            queue.append((nxt, cur_depth + 1))
    return included, boundary, depth_truncated, node_truncated, max_depth


def _select_edges(selected, included, max_edges):
    edges = [e for e in selected if e.src in included and e.dst in included]
    edges.sort(key=_edge_sort_key)
    truncated = len(edges) > max_edges
    return (edges[:max_edges] if truncated else edges), truncated


def _result(graph, opts, included, boundary, edges, flags, max_depth):
    depth_truncated, node_truncated, edge_truncated = flags
    nodes = [graph.get_node(n) for n in sorted(included)]
    nodes = [n for n in nodes if n is not None]
    return {
        "nodes": [_node_dict(n, opts.include_evidence) for n in nodes],
        "edges": [_edge_dict(e, opts.include_evidence) for e in edges],
        "boundary": sorted(boundary),
        "truncated": {
            "nodes": node_truncated,
            "edges": edge_truncated,
            "depth": depth_truncated,
        },
        "stats": {
            "visited": len(included),
            "returned_nodes": len(nodes),
            "returned_edges": len(edges),
            "max_depth": max_depth,
        },
    }


def build_subgraph(
    graph: SignalGraph,
    seeds: Iterable[str],
    *,
    options: SubgraphOptions | None = None,
    depth: int | None = None,
    direction: str | None = None,
    edge_kinds: Iterable[str] | None = None,
    max_nodes: int | None = None,
    max_edges: int | None = None,
    include_evidence: bool | None = None,
) -> dict:
    """构建 seed 的局部子图；core 只接受 canonical seed。"""
    opts = options or SubgraphOptions()
    opts = _with_overrides(
        opts,
        depth=depth,
        direction=direction,
        edge_kinds=tuple(edge_kinds) if edge_kinds is not None else None,
        max_nodes=max_nodes,
        max_edges=max_edges,
        include_evidence=include_evidence,
    )
    kinds = _validate(opts)
    seed_list = _canonical_seeds(graph, seeds)
    out_adj, in_adj, selected = _adjacency(graph, kinds, opts.direction)
    included, boundary, depth_trunc, node_trunc, max_depth = _walk(
        seed_list, opts, out_adj, in_adj
    )
    edges, edge_trunc = _select_edges(selected, included, opts.max_edges)
    return _result(graph, opts, included, boundary, edges,
                   (depth_trunc, node_trunc, edge_trunc), max_depth)
