"""[iter_330 / PLAN P34.1] 客观检查：双向一致性 + claim verification。

只读；所有输出 JSON-first。设计原则：
- verified / contradicted / unknown 三态，不把“无法证明”伪装成 false/true；
- 证据带 graph id / file:line（能拿到的）；
- 不做启发式推断。

命令：
  verify consistency   图/查询双向一致性 (reciprocity / bit / connection)
  verify claim         验证一条 claim (driver/path/connection/bit)
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from cli._common import _build_tracer, handle_compilation_error
from cli._output import emit_json
from cli.core.semantic.trace_common import resolve_signal
from trace.core.compiler import CompilationError

verify_app = typer.Typer(help="客观检查：双向一致性 + claim verification (只读, JSON-first)")


# ----------------------------------------------------------------------------
# 共享
# ----------------------------------------------------------------------------
def _build(file, filelist, log_level: str):
    tracer = _build_tracer(file=file, filelist=filelist, log_level=log_level)
    tracer.build_graph()
    return tracer


def _emit(data: dict, json_output: bool, pretty: bool) -> None:
    if json_output:
        emit_json(data, pretty)
        return
    # 简短人类输出
    if data.get("command") == "verify_claim":
        r = data.get("result", {})
        print(f"claim: {r.get('claim')}")
        print(f"status: {r.get('status')}")
        if r.get("reason"):
            print(f"reason: {r.get('reason')}")
        for ev in r.get("evidence", [])[:5]:
            print(f"  evidence: {ev}")
        return
    r = data.get("result", {})
    print(f"verified: {r.get('verified')}")
    print(f"violations: {r.get('total_violations')}")
    for c in r.get("checks", []):
        print(f"  {c.get('check')}: {c.get('status')} "
              f"(checked={c.get('checked')}, violations={len(c.get('violations', []))}, "
              f"skipped={c.get('skipped', 0)})")
        for v in c.get("violations", [])[:5]:
            print(f"    - {v}")


def _resolve(graph, sig: str):
    r = resolve_signal(graph, sig)
    return r, (r.get("resolved") if r.get("ok") else None)


def _claim_result(claim: dict, status: str, *, reason: str = "",
                  evidence: list | None = None,
                  counterevidence: list | None = None) -> dict:
    return {
        "claim": claim,
        "status": status,
        "reason": reason,
        "evidence": evidence or [],
        "counterevidence": counterevidence or [],
    }


# ----------------------------------------------------------------------------
# verify consistency
# ----------------------------------------------------------------------------
def _check_reciprocity(tracer, graph, signals: list[str] | None,
                       max_nodes: int) -> dict:
    nodes = signals if signals else sorted(graph.nodes())[:max_nodes]
    truncated = (signals is None and len(graph.nodes()) > max_nodes)
    violations = []
    checked = 0
    for n in nodes:
        if n not in graph:
            violations.append({"check": "reciprocity", "kind": "node_missing", "node": n})
            continue
        node = graph.get_node(n)
        kind_name = getattr(getattr(node, "kind", None), "name", "")
        if kind_name not in ("SIGNAL", "WIRE", "REG", "PORT_IN", "PORT_OUT", "PORT_INOUT"):
            continue  # 只检查信号节点；实例/常量/class/表达式不参与 fanin/fanout 互逆
        try:
            fanin = {x.id for x in tracer.trace_fanin(n, depth=1)}
            fanout = {x.id for x in tracer.trace_fanout(
                n, depth=1, include_clock=True, include_reset=True,
                include_conditional=True)}
        except Exception as e:
            violations.append({"check": "reciprocity", "kind": "query_error",
                               "node": n, "error": str(e)})
            continue
        for d in sorted(fanin):
            if d == n:
                continue
            d_node = graph.get_node(d)
            # 父总线/位切片是聚合关系，不是 fanin/fanout 的互逆边
            if getattr(node, "parent", None) == d or getattr(d_node, "parent", None) == n:
                continue
            d_out = {x.id for x in tracer.trace_fanout(
                d, depth=1, include_clock=True, include_reset=True,
                include_conditional=True)}
            if n not in d_out:
                violations.append({"check": "reciprocity", "kind": "fanin_not_reciprocal",
                                   "node": n, "driver": d,
                                   "message": f"{d} in fanin({n}) but {n} not in fanout({d})"})
        for l in sorted(fanout):
            if l == n:
                continue
            l_node = graph.get_node(l)
            if getattr(node, "parent", None) == l or getattr(l_node, "parent", None) == n:
                continue
            l_in = {x.id for x in tracer.trace_fanin(l, depth=1)}
            if n not in l_in:
                violations.append({"check": "reciprocity", "kind": "fanout_not_reciprocal",
                                   "node": n, "load": l,
                                   "message": f"{l} in fanout({n}) but {n} not in fanin({l})"})
        checked += 1
    return {"check": "reciprocity", "status": "fail" if violations else "pass",
            "checked": checked, "skipped": 0, "violations": violations,
            "truncated": truncated}


def _check_bit_mapping(graph, signals: list[str] | None) -> dict:
    violations = []
    checked = skipped = 0
    nodes = signals if signals else sorted(graph.nodes())
    for n in nodes:
        node = graph.get_node(n)
        if node is None or not node.parent:
            continue
        checked += 1
        parent = graph.get_node(node.parent)
        if parent is None:
            violations.append({"check": "bit_mapping", "kind": "parent_missing",
                               "node": n, "parent": node.parent})
            continue
        if node.parent_bit_start is None or node.parent_bit_end is None:
            skipped += 1
            continue
        if node.parent_bit_start > node.parent_bit_end:
            violations.append({"check": "bit_mapping", "kind": "parent_range_reversed",
                               "node": n, "start": node.parent_bit_start,
                               "end": node.parent_bit_end})
        if node.width and node.width[0] is not None and node.width[1] is not None:
            nbits = abs(int(node.width[0]) - int(node.width[1])) + 1
            want = node.parent_bit_end - node.parent_bit_start + 1
            if nbits != want:
                violations.append({"check": "bit_mapping", "kind": "width_mismatch",
                                   "node": n, "node_bits": nbits, "parent_bits": want})
        if not n.startswith(node.parent + "["):
            violations.append({"check": "bit_mapping", "kind": "id_parent_mismatch",
                               "node": n, "parent": node.parent})
    return {"check": "bit_mapping", "status": "fail" if violations else "pass",
            "checked": checked, "skipped": skipped, "violations": violations,
            "truncated": False}


def _check_connections(tracer, graph) -> dict:
    violations = []
    checked = skipped = 0
    try:
        mig = tracer.get_module_graph()
    except Exception as e:
        return {"check": "connection", "status": "unknown", "checked": 0,
                "skipped": 0, "violations": [],
                "error": f"module instance graph unavailable: {e}"}
    if mig is None:
        return {"check": "connection", "status": "unknown", "checked": 0,
                "skipped": 0, "violations": [], "error": "module instance graph missing"}
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
    return {"check": "connection", "status": "fail" if violations else "pass",
            "checked": checked, "skipped": skipped, "violations": violations,
            "truncated": False}


def consistency_cmd(
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    checks: str = typer.Option("reciprocity,bit,connection", "--checks",
                               help="comma-separated: reciprocity,bit,connection"),
    signal: str = typer.Option(None, "--signal", "-s", help="limit reciprocity/bit check to one signal"),
    max_nodes: int = typer.Option(200, "--max-nodes", help="reciprocity sample cap"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """双向一致性检查：fanin/fanout、bit mapping、connection。"""
    try:
        tracer = _build(file, filelist, log_level)
        graph = tracer.get_graph()
        wanted = [c.strip() for c in checks.split(",") if c.strip()]
        unknown = [c for c in wanted if c not in ("reciprocity", "bit", "connection")]
        if unknown:
            raise ValueError(f"unknown check(s): {', '.join(unknown)}")
        signals = None
        if signal:
            r = resolve_signal(graph, signal)
            if not r["ok"]:
                data = {"ok": False, "command": "verify_consistency",
                        "error": f"signal {signal!r} {r['status']}",
                        "errors": [{"signal": signal, "resolution": r["status"],
                                    "candidates": r.get("candidates", []),
                                    "suggestions": r.get("suggestions", [])}]}
                _emit(data, json_output, pretty)
                raise typer.Exit(code=1)
            signals = [r["resolved"]]
        if not wanted:
            raise ValueError("no checks selected (use --checks reciprocity,bit,connection)")
        results = []
        if "reciprocity" in wanted:
            results.append(_check_reciprocity(tracer, graph, signals, max_nodes))
        if "bit" in wanted:
            results.append(_check_bit_mapping(graph, signals))
        if "connection" in wanted:
            results.append(_check_connections(tracer, graph))
        total = sum(len(c.get("violations", [])) for c in results)
        all_known = all(c.get("status") in ("pass", "fail") for c in results)
        data = {
            "ok": True,
            "command": "verify_consistency",
            "params": {"file": str(file) if file else None, "filelist": filelist,
                       "checks": wanted, "signal": signal, "max_nodes": max_nodes},
            "result": {
                "verified": total == 0 and all_known,
                "total_violations": total,
                "unknown_checks": [c["check"] for c in results
                                   if c.get("status") not in ("pass", "fail")],
                "checks": results,
            },
            "errors": [],
        }
        _emit(data, json_output, pretty)
    except typer.Exit:
        raise
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        data = {"ok": False, "command": "verify_consistency", "error": str(e),
                "errors": [str(e)]}
        _emit(data, json_output, pretty)
        raise typer.Exit(code=1) from None


# ----------------------------------------------------------------------------
# verify claim
# ----------------------------------------------------------------------------
def _verify_driver(tracer, graph, claim: dict) -> dict:
    sig = claim.get("signal")
    drv = claim.get("driver")
    if not sig or not drv:
        return _claim_result(claim, "unknown", reason="claim requires signal + driver")
    sr, sid = _resolve(graph, sig)
    if not sid:
        return _claim_result(claim, "unknown", reason=f"signal {sig!r} {sr['status']}")
    dr, did = _resolve(graph, drv)
    if not did:
        # 常量/字面量 driver 不在图里 → unknown，不伪造 contradicted
        return _claim_result(claim, "unknown", reason=f"driver {drv!r} {dr['status']}")
    depth = None if claim.get("transitive") else 1
    drivers = {x.id for x in tracer.trace_fanin(sid, depth=depth)}
    if did in drivers:
        return _claim_result(claim, "verified",
                             evidence=[{"kind": "fanin", "signal": sid, "driver": did,
                                        "transitive": depth is None}])
    return _claim_result(claim, "contradicted",
                         reason=f"{did} is not in fanin({sid}, depth={depth})",
                         counterevidence=[{"kind": "fanin", "signal": sid,
                                           "actual_drivers": sorted(drivers)[:50]}])


def _verify_path(tracer, graph, claim: dict) -> dict:
    src, dst, nodes = claim.get("from"), claim.get("to"), claim.get("nodes")
    if not src or not dst:
        return _claim_result(claim, "unknown", reason="claim requires from + to")
    sr, sid = _resolve(graph, src)
    dr, did = _resolve(graph, dst)
    if not sid or not did:
        return _claim_result(claim, "unknown",
                             reason=f"endpoint unresolved: {src!r}/{dst!r}")
    if nodes:
        resolved = []
        for n in nodes:
            r, rid = _resolve(graph, n)
            if not rid:
                return _claim_result(claim, "unknown", reason=f"path node {n!r} {r['status']}")
            resolved.append(rid)
        if not resolved or resolved[0] != sid or resolved[-1] != did:
            return _claim_result(claim, "contradicted",
                                 reason="path endpoints do not match from/to")
        missing = []
        for a, b in zip(resolved, resolved[1:]):
            if not graph.has_edge(a, b):
                missing.append({"from": a, "to": b})
        if claim.get("bidirectional"):
            for a, b in zip(reversed(resolved), list(reversed(resolved))[1:]):
                if not graph.has_edge(a, b):
                    missing.append({"from": a, "to": b, "direction": "reverse"})
        if missing:
            return _claim_result(claim, "contradicted",
                                 reason="claimed path edges missing",
                                 counterevidence=missing)
        return _claim_result(claim, "verified",
                             evidence=[{"kind": "path", "nodes": resolved,
                                        "bidirectional": bool(claim.get("bidirectional"))}])
    # no explicit nodes: check reachability
    import networkx as nx
    try:
        reachable = nx.has_path(graph, sid, did)
        reverse = nx.has_path(graph, did, sid) if claim.get("bidirectional") else True
    except Exception as e:
        return _claim_result(claim, "unknown", reason=f"path search failed: {e}")
    if reachable and reverse:
        return _claim_result(claim, "verified", evidence=[{"kind": "reachable",
                                                           "from": sid, "to": did,
                                                           "bidirectional": bool(claim.get("bidirectional"))}])
    return _claim_result(claim, "contradicted",
                         reason=f"path check failed (forward={reachable}, reverse={reverse})")


def _verify_connection(tracer, graph, claim: dict) -> dict:
    inst_path, port_name, internal = claim.get("instance"), claim.get("port"), claim.get("internal")
    if not inst_path or not port_name or not internal:
        return _claim_result(claim, "unknown", reason="claim requires instance + port + internal")
    mig = tracer.get_module_graph()
    inst = mig.get_instance(inst_path) if mig is not None else None
    if inst is None:
        return _claim_result(claim, "unknown", reason=f"instance {inst_path!r} not found")
    port = getattr(inst, "ports", {}).get(port_name)
    if port is None:
        return _claim_result(claim, "unknown", reason=f"port {port_name!r} not found")
    actual = getattr(port, "internal_signal", None)
    if actual == internal:
        return _claim_result(claim, "verified",
                             evidence=[{"kind": "connection", "instance": inst_path,
                                        "port": port_name, "internal_signal": actual}])
    return _claim_result(claim, "contradicted", reason="internal signal mismatch",
                         counterevidence=[{"actual_internal_signal": actual}])


def _verify_bit(tracer, graph, claim: dict) -> dict:
    target, source = claim.get("target"), claim.get("source")
    if not target or not source:
        return _claim_result(claim, "unknown", reason="claim requires target + source")
    tr, tid = _resolve(graph, target)
    sr, sid = _resolve(graph, source)
    if not tid or not sid:
        return _claim_result(claim, "unknown",
                             reason=f"bit endpoint unresolved: {target!r}/{source!r} "
                                    f"({tr['status']}/{sr['status']})")
    if tr["status"] == "bit_base_fallback" or sr["status"] == "bit_base_fallback":
        return _claim_result(claim, "unknown",
                             reason="bit node missing; only parent bus exists")
    if graph.has_edge(sid, tid):
        return _claim_result(claim, "verified",
                             evidence=[{"kind": "edge", "from": sid, "to": tid}])
    return _claim_result(claim, "contradicted",
                         reason=f"no direct edge {sid} -> {tid}",
                         counterevidence=[{"from": sid, "to": tid}])


def claim_cmd(
    claim: str = typer.Option(None, "--claim", help="JSON claim string"),
    claim_file: Path = typer.Option(None, "--claim-file", help="JSON claim file"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """验证一条 claim；status = verified / contradicted / unknown。"""
    try:
        if not claim and not claim_file:
            raise ValueError("provide --claim JSON or --claim-file")
        raw = Path(claim_file).read_text() if claim_file else claim
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("claim must be a JSON object")
        typ = obj.get("type")
        tracer = _build(file, filelist, log_level)
        graph = tracer.get_graph()
        if typ == "driver":
            result = _verify_driver(tracer, graph, obj)
        elif typ == "path":
            result = _verify_path(tracer, graph, obj)
        elif typ == "connection":
            result = _verify_connection(tracer, graph, obj)
        elif typ == "bit":
            result = _verify_bit(tracer, graph, obj)
        else:
            raise ValueError(f"unknown claim type: {typ!r} "
                             "(driver|path|connection|bit)")
        data = {"ok": True, "command": "verify_claim",
                "params": {"file": str(file) if file else None, "filelist": filelist},
                "result": result, "errors": []}
        _emit(data, json_output, pretty)
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        data = {"ok": False, "command": "verify_claim", "error": str(e),
                "errors": [str(e)]}
        _emit(data, json_output, pretty)
        raise typer.Exit(code=1) from None


verify_app.command("consistency")(consistency_cmd)
verify_app.command("claim")(claim_cmd)
