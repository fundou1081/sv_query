"""[iter_363 / PLAN P61.1] 结构审查 findings（对称性/端口集合）。

只做可证明的局部结构：
- 同 parent、同 module type 的 sibling 实例；
- 某个端口只在一部分 sibling 上有 CONNECTION；
- 输出 finding + evidence + subgraph 查询参数。
不猜功能等价，不做宽度/命名启发式。
"""
from __future__ import annotations

from typing import Iterable

from ..graph.models import EdgeKind, SignalGraph


class StructuralError(ValueError):
    """非法参数。"""


def _instances(graph: SignalGraph) -> dict[tuple[str, str], list[str]]:
    groups: dict[tuple[str, str], list[str]] = {}
    for nid in graph.nodes():
        node = graph.get_node(nid)
        if node is None or getattr(node.kind, "name", "") != "INSTANTIATED_MODULE":
            continue
        mod_type = getattr(node, "module", "") or ""
        if not mod_type:
            continue
        parent = nid.rsplit(".", 1)[0] if "." in nid else ""
        groups.setdefault((parent, mod_type), []).append(nid)
    return groups


def _direct_port(inst: str, endpoint: str) -> str | None:
    prefix = inst + "."
    if not endpoint.startswith(prefix):
        return None
    rest = endpoint[len(prefix):]
    if not rest or "." in rest:
        return None
    return rest


def _record_port(out, seen, edge, endpoint: str, id_set: set[str]) -> None:
    parent, sep, port = endpoint.rpartition(".")
    if not sep or not port or "." in port or parent not in id_set:
        return
    key = (id(edge), parent, port)
    if key in seen:
        return
    seen.add(key)
    out[parent].setdefault(port, []).append(edge)


def _port_index(graph: SignalGraph, instances: list[str]) -> dict[str, dict[str, list]]:
    """Build port -> CONNECTION edges for all sibling instances in one pass.

    P165.1: this used to call a full `graph.edges()` scan once per instance
    (O(instances × edges)); use the adjacency view once (O(V + E)).
    """
    id_set = set(instances)
    out: dict[str, dict[str, list]] = {inst: {} for inst in instances}
    seen: set[tuple[int, str, str]] = set()
    for src in graph.nodes():
        for dst in graph.successors(src):
            for edge in graph.get_edges(src, dst):
                if edge.kind != EdgeKind.CONNECTION:
                    continue
                for endpoint in (src, dst):
                    _record_port(out, seen, edge, endpoint, id_set)
    return out


def _finding(insts: list[str], port: str, missing: list[str],
             present: list[str], edges: list) -> dict:
    endpoints = {x for e in edges for x in (e.src, e.dst)}
    seeds = sorted(set(insts) | endpoints)
    return {
        "id": f"symmetry.port_set:{port}:{insts[0]}",
        "check": "symmetry.port_set",
        "severity": "warning",
        "confidence": "medium",
        "message": (f"{len(missing)}/{len(insts)} sibling instance(s) "
                    f"missing port {port!r}"),
        "seeds": seeds,
        "expected": {"port": port, "connected_instances": present},
        "actual": {"missing_instances": missing},
        "evidence": [
            {"src": e.src, "dst": e.dst, "kind": e.kind.name,
             "condition": getattr(e, "condition", "") or "",
             "expression": getattr(e, "expression", "") or ""}
            for e in edges
        ],
        "subgraph": {
            "seeds": seeds,
            "depth": 1,
            "direction": "both",
            "edge_kinds": ["connection", "driver"],
        },
    }


def _group_findings(group_key: tuple[str, str], insts: list[str],
                    port_maps: dict[str, dict[str, list]]) -> list[dict]:
    if len(insts) < 2:
        return []
    maps = {inst: port_maps.get(inst, {}) for inst in insts}
    union: set[str] = set()
    for pm in maps.values():
        union.update(pm)
    findings = []
    for port in sorted(union):
        present = [i for i in insts if port in maps[i]]
        missing = [i for i in insts if port not in maps[i]]
        if not missing:
            continue
        edges = []
        for inst in present:
            edges.extend(maps[inst][port])
        findings.append(_finding(insts, port, sorted(missing), sorted(present), edges))
    return findings


def symmetry_findings(graph: SignalGraph, max_findings: int = 100) -> dict:
    if max_findings < 1:
        raise StructuralError("max_findings must be >= 1")
    groups = _instances(graph)
    all_instances = [inst for insts in groups.values() for inst in insts]
    port_maps = _port_index(graph, all_instances)
    findings: list[dict] = []
    checked_groups = 0
    for key in sorted(groups):
        insts = sorted(groups[key])
        if len(insts) < 2:
            continue
        checked_groups += 1
        findings.extend(_group_findings(key, insts, port_maps))
    findings.sort(key=lambda f: f["id"])
    truncated = len(findings) > max_findings
    if truncated:
        findings = findings[:max_findings]
    return {
        "findings": findings,
        "total": len(findings),
        "truncated": truncated,
        "checks": [{
            "check": "symmetry.port_set",
            "status": "fail" if findings else "pass",
            "checked": checked_groups,
            "findings": len(findings),
        }],
    }
