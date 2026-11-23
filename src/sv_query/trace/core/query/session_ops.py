"""Read-only session query helpers for scope/instances/verify (P194.2f).

Kept below the CLI: GraphSession calls these against one already-built tracer.
Verification is intentionally conservative: unsupported checks are reported as
``unknown`` and never rounded up to ``verified``.
"""
from __future__ import annotations

from ..graph import contracts
from ..graph.models import NodeKind


def _resolve(graph, signal: str) -> tuple[str, str | None]:
    """Resolve an exact graph id, then a unique dotted suffix."""
    if signal in graph:
        return signal, "exact"
    suffix = "." + signal
    hits = [nid for nid in graph.nodes() if nid == signal or nid.endswith(suffix)]
    if len(hits) == 1:
        return hits[0], "relative"
    return "", None


def _claim_result(claim: dict, status: str, *, reason="", evidence=None,
                  counterevidence=None, unknown_kind="") -> dict:
    result = {"claim": claim, "status": status, "reason": reason,
              "evidence": evidence or [],
              "counterevidence": counterevidence or []}
    if status == "unknown":
        result["unknown_kind"] = unknown_kind or "unverifiable"
    return result


def _verify_driver(tracer, graph, claim: dict) -> dict:
    sid, _ = _resolve(graph, str(claim.get("signal", "")))
    did, _ = _resolve(graph, str(claim.get("driver", "")))
    if not sid or not did:
        return _claim_result(claim, "unknown",
                             reason="driver/signal endpoint unresolved",
                             unknown_kind="unresolved_endpoint")
    depth = None if claim.get("transitive") else 1
    drivers = {x.id for x in tracer.trace_fanin(sid, depth=depth)}
    if did in drivers:
        return _claim_result(claim, "verified",
                             evidence=[{"kind": "fanin", "signal": sid,
                                        "driver": did, "transitive": depth is None}])
    return _claim_result(claim, "contradicted",
                         reason=f"{did} is not in fanin({sid}, depth={depth})",
                         counterevidence=[{"actual_drivers": sorted(drivers)[:50]}])


def _verify_path_nodes(graph, claim: dict, nodes) -> dict | None:
    resolved = []
    for item in nodes:
        rid, _ = _resolve(graph, str(item))
        if not rid:
            return _claim_result(claim, "unknown",
                                 reason=f"path node {item!r} unresolved",
                                 unknown_kind="unresolved_endpoint")
        resolved.append(rid)
    missing = [{"from": a, "to": b} for a, b in zip(resolved, resolved[1:], strict=False)
               if not contracts.has_data_edge(graph.get_edges(a, b))]
    if missing:
        return _claim_result(claim, "contradicted",
                             reason="claimed path edges missing",
                             counterevidence=missing)
    return _claim_result(claim, "verified",
                         evidence=[{"kind": "path", "nodes": resolved}])


def _verify_path(tracer, graph, claim: dict) -> dict:
    sid, _ = _resolve(graph, str(claim.get("from", "")))
    did, _ = _resolve(graph, str(claim.get("to", "")))
    if not sid or not did:
        return _claim_result(claim, "unknown", reason="path endpoint unresolved",
                             unknown_kind="unresolved_endpoint")
    nodes = claim.get("nodes") or []
    if nodes:
        return _verify_path_nodes(graph, claim, nodes)
    resolver = tracer.get_path_resolver()
    if resolver is None:
        return _claim_result(claim, "unknown", reason="path resolver unavailable")
    if resolver.find_path(sid, did, directed=True) is not None:
        return _claim_result(claim, "verified",
                             evidence=[{"kind": "reachable", "from": sid, "to": did}])
    return _claim_result(claim, "contradicted",
                         reason=f"no directed data path {sid} -> {did}")


def _verify_connection(tracer, graph, claim: dict) -> dict:
    inst_path = str(claim.get("instance", ""))
    port_name = str(claim.get("port", ""))
    internal = str(claim.get("internal", ""))
    mig = tracer.get_module_graph()
    inst = mig.get_instance(inst_path) if mig is not None else None
    if inst is None:
        return _claim_result(claim, "unknown", reason="instance not found")
    port = getattr(inst, "ports", {}).get(port_name)
    if port is None:
        return _claim_result(claim, "unknown", reason="port not found")
    actual = getattr(port, "internal_signal", None)
    if actual == internal:
        return _claim_result(claim, "verified",
                             evidence=[{"kind": "connection", "instance": inst_path,
                                        "port": port_name, "internal_signal": actual}])
    return _claim_result(claim, "contradicted", reason="internal signal mismatch",
                         counterevidence=[{"actual_internal_signal": actual}])


def _verify_bit(tracer, graph, claim: dict) -> dict:
    target = str(claim.get("target", ""))
    source = str(claim.get("source", ""))
    tid, _ = _resolve(graph, target)
    sid, _ = _resolve(graph, source)
    if not tid or not sid:
        return _claim_result(claim, "unknown", reason="bit endpoint unresolved",
                             unknown_kind="unresolved_endpoint")
    if graph.has_edge(sid, tid):
        return _claim_result(claim, "verified",
                             evidence=[{"kind": "edge", "from": sid, "to": tid}])
    return _claim_result(claim, "contradicted", reason=f"no direct edge {sid} -> {tid}")


def verify_claim(tracer, claim: object) -> dict:
    """Verify driver/path/connection/bit claims against one tracer."""
    if not isinstance(claim, dict):
        raise ValueError("claim must be an object")
    graph = tracer.get_graph()
    typ = claim.get("type")
    handlers = {"driver": _verify_driver, "path": _verify_path,
                "connection": _verify_connection, "bit": _verify_bit}
    fn = handlers.get(typ)
    if fn is None:
        return _claim_result(claim, "unknown",
                             reason=f"unsupported claim type: {typ!r}")
    return fn(tracer, graph, claim)


def _connection_check(tracer, graph) -> dict:
    mig = tracer.get_module_graph()
    if mig is None:
        return {"check": "connection", "status": "unknown", "checked": 0,
                "skipped": 0, "violations": [],
                "error": "module instance graph missing"}
    violations = []
    checked = skipped = 0
    for inst_path, inst in sorted(mig.instances.items()):
        for port_name, port in sorted(getattr(inst, "ports", {}).items()):
            internal = getattr(port, "internal_signal", None)
            if not internal:
                skipped += 1
                continue
            checked += 1
            if internal not in graph:
                violations.append({"check": "connection", "kind": "internal_missing",
                                   "instance": inst_path, "port": port_name,
                                   "internal_signal": internal})
    status = "unknown" if checked == 0 else ("fail" if violations else "pass")
    result = {"check": "connection", "status": status,
              "checked": checked, "skipped": skipped, "violations": violations,
              "truncated": False}
    if checked == 0:
        result["error"] = "no applicable instance ports"
    return result


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
