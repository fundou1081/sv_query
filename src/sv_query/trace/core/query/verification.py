"""Shared claim/connection verification semantics (P197.2).

The CLI and GraphSession must never implement different verdicts for the same
claim. Resolution policy is injected by the caller; graph/edge semantics live
here exactly once.
"""
from __future__ import annotations

from ..graph import contracts


def claim_result(claim: dict, status: str, *, reason="", evidence=None,
                 counterevidence=None, unknown_kind="") -> dict:
    result = {"claim": claim, "status": status, "reason": reason,
              "evidence": evidence or [], "counterevidence": counterevidence or []}
    if status == "unknown":
        kind = unknown_kind or "unverifiable"
        result["machine"] = {
            "status": "unknown",
            "unknown_kind": kind,
            "unresolved_endpoint": kind == "unresolved_endpoint",
        }
    return result


def verify_driver(tracer, graph, claim: dict, resolve) -> dict:
    sig, drv = claim.get("signal"), claim.get("driver")
    if not sig or not drv:
        return claim_result(claim, "unknown", reason="claim requires signal + driver")
    sid, sstat = resolve(graph, sig)
    if not sid:
        return claim_result(claim, "unknown", reason=f"signal {sig!r} {sstat}",
                            unknown_kind="unresolved_endpoint")
    did, dstat = resolve(graph, drv)
    if not did:
        return claim_result(claim, "unknown", reason=f"driver {drv!r} {dstat}",
                            unknown_kind="unresolved_endpoint")
    depth = None if claim.get("transitive") else 1
    drivers = {x.id for x in tracer.trace_fanin(sid, depth=depth)}
    if did in drivers:
        return claim_result(claim, "verified", evidence=[
            {"kind": "fanin", "signal": sid, "driver": did,
             "transitive": depth is None}])
    return claim_result(claim, "contradicted",
                        reason=f"{did} is not in fanin({sid}, depth={depth})",
                        counterevidence=[{"kind": "fanin", "signal": sid,
                                          "actual_drivers": sorted(drivers)[:50]}])


def _explicit_path(claim, graph, resolved, sid, did) -> dict:
    if not resolved or resolved[0] != sid or resolved[-1] != did:
        return claim_result(claim, "contradicted",
                            reason="path endpoints do not match from/to")
    missing = []
    for a, b in zip(resolved, resolved[1:], strict=False):
        if not contracts.has_data_edge(graph.get_edges(a, b)):
            missing.append({"from": a, "to": b})
    if claim.get("bidirectional"):
        rev = list(reversed(resolved))
        for a, b in zip(rev, rev[1:], strict=False):
            if not contracts.has_data_edge(graph.get_edges(a, b)):
                missing.append({"from": a, "to": b, "direction": "reverse"})
    if missing:
        return claim_result(claim, "contradicted",
                            reason="claimed path edges missing (data edges only)",
                            counterevidence=missing)
    return claim_result(claim, "verified", evidence=[
        {"kind": "path", "nodes": resolved, "edge_policy": "data_edges_only",
         "bidirectional": bool(claim.get("bidirectional"))}])


def _reachable_path(tracer, claim, sid, did) -> dict:
    try:
        resolver = tracer.get_path_resolver()
        if resolver is None:
            raise RuntimeError("path resolver unavailable")
        reachable = resolver.find_path(sid, did, directed=True) is not None
        bidirectional = bool(claim.get("bidirectional"))
        reverse = (resolver.find_path(did, sid, directed=True) is not None
                   if bidirectional else None)
    except Exception as exc:
        return claim_result(claim, "unknown", reason=f"path search failed: {exc}")
    if reachable and (reverse is None or reverse):
        return claim_result(claim, "verified", evidence=[
            {"kind": "reachable", "from": sid, "to": did,
             "bidirectional": bidirectional}])
    if reverse is None:
        reason = f"path check failed (forward={reachable})"
    else:
        reason = f"path check failed (forward={reachable}, reverse={reverse})"
    return claim_result(claim, "contradicted", reason=reason)


def _resolve_path_node(graph, value, resolve):
    rid, status = resolve(graph, value)
    if not rid or status == "bit_base_fallback":
        return "", status or "unresolved_endpoint"
    return rid, status


def verify_path(tracer, graph, claim: dict, resolve) -> dict:
    src, dst, nodes = claim.get("from"), claim.get("to"), claim.get("nodes")
    if not src or not dst:
        return claim_result(claim, "unknown", reason="claim requires from + to")
    sid, _ = _resolve_path_node(graph, src, resolve)
    did, _ = _resolve_path_node(graph, dst, resolve)
    if not sid or not did:
        return claim_result(claim, "unknown",
                            reason=f"endpoint unresolved: {src!r}/{dst!r}",
                            unknown_kind="unresolved_endpoint")
    if not nodes:
        return _reachable_path(tracer, claim, sid, did)
    resolved = []
    for n in nodes:
        rid, rstat = _resolve_path_node(graph, n, resolve)
        if not rid:
            return claim_result(claim, "unknown",
                                reason=f"path node {n!r} {rstat}",
                                unknown_kind="unresolved_endpoint")
        resolved.append(rid)
    return _explicit_path(claim, graph, resolved, sid, did)


def verify_connection(tracer, graph, claim: dict, resolve=None) -> dict:
    inst_path = claim.get("instance")
    port_name = claim.get("port")
    internal = claim.get("internal")
    if not inst_path or not port_name or not internal:
        return claim_result(claim, "unknown",
                            reason="claim requires instance + port + internal")
    mig = tracer.get_module_graph()
    inst = mig.get_instance(inst_path) if mig is not None else None
    if inst is None:
        return claim_result(claim, "unknown", reason=f"instance {inst_path!r} not found")
    port = getattr(inst, "ports", {}).get(port_name)
    if port is None:
        return claim_result(claim, "unknown", reason=f"port {port_name!r} not found")
    actual = getattr(port, "internal_signal", None)
    if actual == internal:
        return claim_result(claim, "verified", evidence=[
            {"kind": "connection", "instance": inst_path,
             "port": port_name, "internal_signal": actual}])
    return claim_result(claim, "contradicted", reason="internal signal mismatch",
                        counterevidence=[{"actual_internal_signal": actual}])


def verify_bit(tracer, graph, claim: dict, resolve) -> dict:
    target, source = claim.get("target"), claim.get("source")
    if not target or not source:
        return claim_result(claim, "unknown", reason="claim requires target + source")
    tid, tstat = resolve(graph, target)
    sid, sstat = resolve(graph, source)
    if not tid or not sid:
        return claim_result(claim, "unknown",
                            reason=f"bit endpoint unresolved: {target!r}/{source!r}",
                            unknown_kind="unresolved_endpoint")
    if tstat == "bit_base_fallback" or sstat == "bit_base_fallback":
        return claim_result(claim, "unknown",
                            reason="bit node missing; only parent bus exists",
                            unknown_kind="unverifiable")
    if graph.has_edge(sid, tid):
        return claim_result(claim, "verified", evidence=[
            {"kind": "edge", "from": sid, "to": tid}])
    return claim_result(claim, "contradicted",
                        reason=f"no direct edge {sid} -> {tid}",
                        counterevidence=[{"from": sid, "to": tid}])


def verify_claim(tracer, claim: object, resolve, *, strict_type: bool = False) -> dict:
    if not isinstance(claim, dict):
        raise ValueError("claim must be an object")
    typ = claim.get("type")
    handlers = {"driver": verify_driver, "path": verify_path,
                "connection": verify_connection, "bit": verify_bit}
    fn = handlers.get(typ) if isinstance(typ, str) else None
    if fn is None:
        if strict_type:
            raise ValueError(f"unknown claim type: {typ!r} (driver|path|connection|bit)")
        return claim_result(claim, "unknown",
                            reason=f"unsupported claim type: {typ!r}")
    graph = tracer.get_graph()
    return fn(tracer, graph, claim, resolve)


def connection_check(tracer, graph) -> dict:
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
                continue
            port_id = f"{inst_path}.{port_name}"
            if port_id not in graph:
                violations.append({"check": "connection", "kind": "port_node_missing",
                                   "instance": inst_path, "port": port_name,
                                   "port_id": port_id, "internal_signal": internal})
    status = "unknown" if checked == 0 else ("fail" if violations else "pass")
    result = {"check": "connection", "status": status, "checked": checked,
              "skipped": skipped, "violations": violations, "truncated": False}
    if checked == 0:
        result["error"] = "no applicable instance ports"
    return result
