"""Read-only session query helpers for scope/instances/verify (P194.2f).

Kept below the CLI: GraphSession calls these against one already-built tracer.
Verification is intentionally conservative: unsupported checks are reported as
``unknown`` and never rounded up to ``verified``.
"""
from __future__ import annotations

from ..graph.models import NodeKind
from . import verification as shared_verify


def _resolve(graph, signal: str) -> tuple[str, str | None]:
    """Resolve an exact graph id, then a unique dotted suffix."""
    if signal in graph:
        return signal, "exact"
    suffix = "." + signal
    hits = [nid for nid in graph.nodes() if nid == signal or nid.endswith(suffix)]
    if len(hits) == 1:
        return hits[0], "relative"
    return "", None


def _session_resolve(graph, signal: str):
    rid, status = _resolve(graph, signal)
    return rid, status


def _claim_result(claim: dict, status: str, *, reason="", evidence=None,
                  counterevidence=None, unknown_kind="") -> dict:
    return shared_verify.claim_result(
        claim, status, reason=reason, evidence=evidence,
        counterevidence=counterevidence, unknown_kind=unknown_kind)


def verify_claim(tracer, claim: object) -> dict:
    return shared_verify.verify_claim(
        tracer, claim, _session_resolve, strict_type=False)


def _connection_check(tracer, graph) -> dict:
    return shared_verify.connection_check(tracer, graph)


def verify_consistency(tracer, checks=("connection",), signal=None,
                       max_nodes=200, full=False) -> dict:
    """Conservative consistency report; only connection is implemented here."""
    graph = tracer.get_graph()
    wanted = [str(c) for c in checks]
    results = []
    for name in wanted:
        if name == "connection":
            results.append(_connection_check(tracer, graph))
        else:
            results.append({"check": name, "status": "unknown", "checked": 0,
                            "skipped": 0, "violations": [],
                            "error": "check not implemented in local session"})
    total = sum(len(c.get("violations", [])) for c in results)
    unknown = [c["check"] for c in results if c.get("status") not in ("pass", "fail")]
    coverage = not unknown and not any(c.get("truncated") for c in results)
    return {"verified": total == 0 and coverage,
            "coverage_complete": coverage,
            "partial_checks": [],
            "total_violations": total,
            "unknown_checks": unknown,
            "checks": results}


def _instance_rows(tracer) -> list[dict]:
    return [{"full_path": i.full_path, "name": i.name,
             "module_type": i.module_type, "parent": i.parent}
            for i in tracer.get_instances()]


def _instance_ports(tracer, path: str) -> list[dict]:
    mig = tracer.get_module_graph()
    inst = mig.get_instance(path) if mig is not None else None
    if inst is None:
        return []
    return [{"port": name, "direction": port.direction,
             "width": list(port.width) if port.width else None,
             "internal_signal": port.internal_signal}
            for name, port in sorted(inst.ports.items())]


def _instance_detail(tracer, rows: list[dict], path: str) -> dict:
    me = next((r for r in rows if r["full_path"] == path), None)
    if me is None:
        raise ValueError(f"instance not found: {path}")
    return {"instance": me,
            "children": [r for r in rows if r["parent"] == path],
            "ports": _instance_ports(tracer, path)}


def instances(tracer, path=None, module=None, depth=None) -> dict:
    rows = _instance_rows(tracer)
    if path:
        return _instance_detail(tracer, rows, path)
    if module:
        rows = [r for r in rows if r["parent"] == module or r["full_path"] == module]
    if depth is not None:
        rows = [r for r in rows if r["full_path"].count(".") < depth]
    return {"instances": rows, "count": len(rows)}


def _signals_under(graph, path: str) -> list[dict]:
    out = []
    prefix = path + "."
    for nid in graph.nodes():
        if not nid.startswith(prefix):
            continue
        rest = nid[len(prefix):]
        if not rest or "." in rest:
            continue
        node = graph.get_node(nid)
        if node is None or node.kind in (NodeKind.INSTANTIATED_MODULE,
                                         NodeKind.GENERATE_BLOCK):
            continue
        out.append({"name": rest, "canonical_id": nid,
                    "kind": getattr(node.kind, "name", str(node.kind)),
                    "width": list(node.width) if node.width else None})
    return sorted(out, key=lambda x: x["name"])


def scope(tracer, path: str) -> dict:
    mig = tracer.get_module_graph()
    inst = mig.get_instance(path) if mig is not None else None
    if inst is None:
        raise ValueError(f"scope not found: {path}")
    children = [{"full_path": i.full_path, "name": i.name,
                 "module_type": i.module_type}
                for i in tracer.get_instances() if i.parent == path]
    ports = [{"name": name, "direction": p.direction,
              "width": list(p.width) if p.width else None,
              "canonical_id": f"{path}.{name}",
              "internal_signal": p.internal_signal}
             for name, p in sorted(inst.ports.items())]
    return {"ok": True, "scope": path, "canonical_id": path,
            "kind": "instance", "module_type": inst.module_type,
            "parent": inst.parent, "children": children, "ports": ports,
            "parameters": [], "signals": _signals_under(tracer.get_graph(), path)}
