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
import re
from pathlib import Path

import typer

from cli._common import _build_tracer, handle_compilation_error
from cli._output import emit_json
from cli.core.semantic.trace_common import resolve_signal, _load_tracer_from_snapshot
from trace.core.compiler import CompilationError
from trace.core.query.structural import StructuralError, symmetry_findings

verify_app = typer.Typer(help="客观检查：双向一致性 + claim verification (只读, JSON-first)")


# ----------------------------------------------------------------------------
# 共享
# ----------------------------------------------------------------------------
def _build(file, filelist, log_level: str, from_snapshot: str | None = None):
    if from_snapshot:
        if file or filelist:
            raise ValueError("--from-snapshot is mutually exclusive with --file/--filelist")
        return _load_tracer_from_snapshot(from_snapshot, log_level=log_level)
    if not file and not filelist:
        raise ValueError("Either --file, --filelist, or --from-snapshot must be provided")
    tracer = _build_tracer(file=file, filelist=filelist, log_level=log_level)
    tracer.build_graph()
    return tracer


def _emit(data: dict, json_output: bool, pretty: bool) -> None:
    if json_output:
        emit_json(data, pretty)
        return
    # 简短人类输出
    if data.get("command") == "verify_structural":
        r = data.get("result", {})
        print(f"structural findings: {r.get('total', 0)}")
        for f in r.get("findings", [])[:20]:
            print(f"  [{f.get('check')}] {f.get('message')}")
            print(f"    seeds: {', '.join(f.get('seeds', []))}")
        return
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
                  counterevidence: list | None = None,
                  unknown_kind: str = "") -> dict:
    result = {
        "claim": claim,
        "status": status,
        "reason": reason,
        "evidence": evidence or [],
        "counterevidence": counterevidence or [],
    }
    if status == "unknown":
        kind = unknown_kind or "unverifiable"
        result["machine"] = {
            "status": "unknown",
            "unknown_kind": kind,
            "unresolved_endpoint": kind == "unresolved_endpoint",
        }
    return result


# ----------------------------------------------------------------------------
# verify consistency
# ----------------------------------------------------------------------------
def _is_literal_id(nid: str) -> bool:
    import re
    return bool(re.match(r"^-?\d+'[sS]?[bodhBODH][0-9a-fA-F_]+$", nid or "")
                or re.match(r"^-?\d+$", nid or ""))


def _is_bit_like(node) -> bool:
    if node is None:
        return False
    if getattr(node, "parent", None) or getattr(node, "bit_range", None):
        return True
    import re
    return bool(re.search(r"\[[^\]]+\]$", getattr(node, "id", "") or ""))


def _has_data_edge(graph, a: str, b: str) -> bool:
    """Reciprocity is defined on DRIVER/CONNECTION edges only."""
    return any(e.kind.name in ("DRIVER", "CONNECTION")
               for e in graph.get_edges(a, b))


def _check_reciprocity(tracer, graph, signals: list[str] | None,
                       max_nodes: int, full: bool = False) -> dict:
    """全图/抽样 reciprocity。

    full=True 时遍历所有信号节点（无 truncated）；查询结果缓存，
    避免同一个节点的 fanin/fanout 被邻居重复计算。
    """
    if signals:
        nodes = signals
        truncated = False
        mode = "signal"
    elif full:
        nodes = sorted(graph.nodes())
        truncated = False
        mode = "full"
    else:
        nodes = sorted(graph.nodes())[:max_nodes]
        truncated = len(graph.nodes()) > max_nodes
        mode = "sample"
    violations = []
    checked = skipped = 0
    excluded = {"non_signal": 0, "bit_like": 0, "constant": 0}
    fanin_cache: dict[str, set[str]] = {}
    fanout_cache: dict[str, set[str]] = {}

    def _fanin(n):
        if n not in fanin_cache:
            fanin_cache[n] = {x.id for x in tracer.trace_fanin(n, depth=1)}
        return fanin_cache[n]

    def _fanout(n):
        if n not in fanout_cache:
            fanout_cache[n] = {x.id for x in tracer.trace_fanout(
                n, depth=1, include_clock=True, include_reset=True,
                include_conditional=True)}
        return fanout_cache[n]
    for n in nodes:
        if n not in graph:
            violations.append({"check": "reciprocity", "kind": "node_missing", "node": n})
            continue
        node = graph.get_node(n)
        kind_name = getattr(getattr(node, "kind", None), "name", "")
        if kind_name not in ("SIGNAL", "WIRE", "REG", "PORT_IN", "PORT_OUT", "PORT_INOUT"):
            excluded["non_signal"] += 1
            continue  # 实例/常量/class/表达式不参与 fanin/fanout 互逆
        if _is_bit_like(node):
            excluded["bit_like"] += 1
            continue  # 位/切片节点使用父总线回退，严格互逆不适用
        try:
            fanin = _fanin(n)
            fanout = _fanout(n)
        except Exception as e:
            violations.append({"check": "reciprocity", "kind": "query_error",
                               "node": n, "error": str(e)})
            continue
        for d in sorted(fanin):
            if d == n:
                continue
            d_node = graph.get_node(d)
            if _is_literal_id(d):
                excluded["constant"] += 1
                continue
            # 父总线/位切片是聚合关系，不是 fanin/fanout 的互逆边
            if (_is_bit_like(d_node) or getattr(node, "parent", None) == d
                    or getattr(d_node, "parent", None) == n):
                excluded["bit_like"] += 1
                continue
            if not _has_data_edge(graph, d, n):
                continue  # BIT_SELECT/hierarchy edge, not a data-flow pair
            d_out = _fanout(d)
            if n not in d_out:
                violations.append({"check": "reciprocity", "kind": "fanin_not_reciprocal",
                                   "node": n, "driver": d,
                                   "message": f"{d} in fanin({n}) but {n} not in fanout({d})"})
        for l in sorted(fanout):
            if l == n:
                continue
            l_node = graph.get_node(l)
            if _is_literal_id(l):
                excluded["constant"] += 1
                continue
            if (_is_bit_like(l_node) or getattr(node, "parent", None) == l
                    or getattr(l_node, "parent", None) == n):
                excluded["bit_like"] += 1
                continue
            if not _has_data_edge(graph, n, l):
                continue  # BIT_SELECT/hierarchy edge, not a data-flow pair
            l_in = _fanin(l)
            if n not in l_in:
                violations.append({"check": "reciprocity", "kind": "fanout_not_reciprocal",
                                   "node": n, "load": l,
                                   "message": f"{l} in fanout({n}) but {n} not in fanin({l})"})
        checked += 1
    # 非信号/父位聚合节点被排除，是显式范围，不当作 checked
    skipped = max(0, len(nodes) - checked - len([
        v for v in violations if v.get("kind") == "node_missing"]))
    return {"check": "reciprocity", "status": "fail" if violations else "pass",
            "checked": checked, "skipped": skipped, "violations": violations,
            "truncated": truncated, "mode": mode,
            "excluded": excluded,
            "coverage": {
                "scope": "signal_nodes_excluding_bit_like_and_constants",
                "checked": checked,
                "excluded": excluded,
                "bit_level_reciprocity": "not_applicable",
                "note": "bit/slice nodes use parent-bus fallback; strict edge reciprocity is not applicable",
            },
            "total_nodes": len(graph.nodes())}


def _check_bit_mapping(graph, signals: list[str] | None) -> dict:
    violations = []
    checked = skipped = index_like = range_checked = 0
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
        # Range-select primary node should have an edge to its parent.
        # Individual bit nodes expanded from a slice need not; struct members use
        # member naming and are checked by bit_range/width instead.
        is_range_primary = (node.bit_range is not None and ":" in node.bit_range
                            and n == f"{node.parent}[{node.bit_range}]")
        if is_range_primary and not any(
                e.kind.name in ("BIT_SELECT", "MEMBER_SELECT")
                for e in graph.get_edges(n, node.parent)):
            violations.append({"check": "bit_mapping", "kind": "parent_edge_missing",
                               "node": n, "parent": node.parent})
        has_bits = (node.parent_bit_start is not None
                    or node.parent_bit_end is not None
                    or node.bit_range is not None)
        if not has_bits:
            # unpacked array element / dynamic index: not a bit-select
            index_like += 1
            continue
        range_checked += 1
        if node.parent_bit_start is not None and node.parent_bit_end is not None:
            if node.parent_bit_start > node.parent_bit_end:
                # allow descending ranges (SV [7:4]); reverse is not itself a bug,
                # but record if width disagrees below.
                pass
            if node.width and node.width[0] is not None and node.width[1] is not None:
                # A single-bit slice has no real msb/lsb width; graph nodes
                # may store the (1,0) default sentinel.  Prefer the explicit
                # bit_range / single-bit parent span in that case.
                if ((node.bit_range and ":" not in node.bit_range)
                        or node.parent_bit_start == node.parent_bit_end):
                    nbits = 1
                else:
                    nbits = abs(int(node.width[0]) - int(node.width[1])) + 1
                want = abs(node.parent_bit_end - node.parent_bit_start) + 1
                if nbits != want:
                    violations.append({"check": "bit_mapping", "kind": "width_mismatch",
                                       "node": n, "node_bits": nbits,
                                       "parent_bits": want})
            if parent.width and parent.width[0] is not None and parent.width[1] is not None:
                lo = min(int(parent.width[0]), int(parent.width[1]))
                hi = max(int(parent.width[0]), int(parent.width[1]))
                for v in (node.parent_bit_start, node.parent_bit_end):
                    if v < lo or v > hi:
                        violations.append({"check": "bit_mapping",
                                           "kind": "parent_range_out_of_bounds",
                                           "node": n, "bit": v,
                                           "parent_range": [lo, hi]})
                        break
        if node.bit_range:
            m = re.match(r"^\[(\d+)(?::(\d+))?\]$", node.bit_range.strip())
            if m:
                b_hi = int(m.group(1)); b_lo = int(m.group(2) or m.group(1))
                if (node.parent_bit_start is not None
                        and node.parent_bit_end is not None
                        and {b_hi, b_lo} != {node.parent_bit_start,
                                             node.parent_bit_end}):
                    violations.append({"check": "bit_mapping",
                                       "kind": "bit_range_mismatch",
                                       "node": n, "bit_range": node.bit_range,
                                       "parent_bits": [node.parent_bit_start,
                                                       node.parent_bit_end]})
        # Only the node's immediate relation to its parent matters.  A bracketed
        # segment earlier in the hierarchy (generate/array) is not a bit-select
        # mismatch.
        direct_child = (n.startswith(node.parent + ".")
                        or n.startswith(node.parent + "["))
        if not direct_child:
            violations.append({"check": "bit_mapping", "kind": "id_parent_mismatch",
                               "node": n, "parent": node.parent})
    return {"check": "bit_mapping", "status": "fail" if violations else "pass",
            "checked": checked, "skipped": skipped,
            "bit_select_checked": range_checked, "index_like": index_like,
            "violations": violations, "truncated": False,
            "coverage": {"scope": "all_parent_nodes",
                         "bit_select_checked": range_checked,
                         "index_like": index_like}}




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
    from_snapshot: str = typer.Option(None, "--from-snapshot",
                                      help="load snapshot graph; connection check runs when "
                                           "module_graph is present, legacy snapshots report unknown"),
    checks: str = typer.Option("reciprocity,bit,connection", "--checks",
                               help="comma-separated: reciprocity,bit,connection"),
    signal: str = typer.Option(None, "--signal", "-s", help="limit reciprocity/bit check to one signal"),
    max_nodes: int = typer.Option(200, "--max-nodes", help="reciprocity sample cap"),
    full: bool = typer.Option(False, "--full", help="check all signal nodes (no sampling)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """双向一致性检查：fanin/fanout、bit mapping、connection。"""
    try:
        tracer = _build(file, filelist, log_level, from_snapshot=from_snapshot)
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
            results.append(_check_reciprocity(tracer, graph, signals, max_nodes, full))
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
                       "from_snapshot": from_snapshot,
                       "checks": wanted, "signal": signal, "max_nodes": max_nodes,
                       "full": full},
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
        return _claim_result(claim, "unknown",
                             reason=f"signal {sig!r} {sr['status']}",
                             unknown_kind="unresolved_endpoint")
    dr, did = _resolve(graph, drv)
    if not did:
        # 常量/字面量 driver 不在图里 → unknown，不伪造 contradicted
        return _claim_result(claim, "unknown",
                             reason=f"driver {drv!r} {dr['status']}",
                             unknown_kind="unresolved_endpoint")
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
                             reason=f"endpoint unresolved: {src!r}/{dst!r}",
                             unknown_kind="unresolved_endpoint")
    if nodes:
        resolved = []
        for n in nodes:
            r, rid = _resolve(graph, n)
            if not rid:
                return _claim_result(claim, "unknown",
                                     reason=f"path node {n!r} {r['status']}",
                                     unknown_kind="unresolved_endpoint")
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
    # no explicit nodes: check reachability through the path resolver with
    # PathResolver uses the structural graph only.
    try:
        resolver = tracer.get_path_resolver()
        if resolver is None:
            raise RuntimeError("path resolver unavailable")
        reachable = resolver.find_path(sid, did, directed=True) is not None
        bidirectional = bool(claim.get("bidirectional"))
        reverse = (resolver.find_path(did, sid, directed=True) is not None
                   if bidirectional else None)
    except Exception as e:
        return _claim_result(claim, "unknown", reason=f"path search failed: {e}")
    if reachable and (reverse is None or reverse):
        return _claim_result(claim, "verified", evidence=[{"kind": "reachable",
                                                           "from": sid, "to": did,
                                                           "bidirectional": bidirectional}])
    if reverse is None:
        reason = f"path check failed (forward={reachable})"
    else:
        reason = f"path check failed (forward={reachable}, reverse={reverse})"
    return _claim_result(claim, "contradicted", reason=reason)


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
                                    f"({tr['status']}/{sr['status']})",
                             unknown_kind="unresolved_endpoint")
    if tr["status"] == "bit_base_fallback" or sr["status"] == "bit_base_fallback":
        return _claim_result(claim, "unknown",
                             reason="bit node missing; only parent bus exists",
                             unknown_kind="unverifiable")
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
    from_snapshot: str = typer.Option(None, "--from-snapshot",
                                      help="Load graph from a saved snapshot tag (skip SV parse)"),
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
        tracer = _build(file, filelist, log_level, from_snapshot=from_snapshot)
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
                "params": {"file": str(file) if file else None,
                           "filelist": filelist,
                           "from_snapshot": from_snapshot},
                "result": result, "errors": []}
        _emit(data, json_output, pretty)
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        data = {"ok": False, "command": "verify_claim", "error": str(e),
                "errors": [str(e)]}
        _emit(data, json_output, pretty)
        raise typer.Exit(code=1) from None


def structural_cmd(
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) multi-file project"),
    checks: str = typer.Option("symmetry", "--checks",
                               help="comma-separated: symmetry"),
    max_findings: int = typer.Option(100, "--max-findings", help="hard finding cap"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """结构审查：sibling 端口集合对称性；只输出候选 + 证据。"""
    try:
        wanted = [c.strip() for c in checks.split(",") if c.strip()]
        unknown = [c for c in wanted if c != "symmetry"]
        if unknown:
            raise ValueError(f"unknown check(s): {', '.join(unknown)}")
        tracer = _build(file, filelist, log_level)
        graph = tracer.get_graph()
        result = symmetry_findings(graph, max_findings=max_findings)
        data = {
            "ok": True,
            "command": "verify_structural",
            "params": {"file": str(file) if file else None,
                        "filelist": filelist, "checks": wanted,
                        "max_findings": max_findings},
            "result": result,
            "errors": [],
        }
        _emit(data, json_output, pretty)
    except CompilationError as e:
        handle_compilation_error(e)
    except StructuralError as e:
        data = {"ok": False, "command": "verify_structural", "error": str(e),
                "errors": [str(e)]}
        _emit(data, json_output, pretty)
        raise typer.Exit(code=1) from None
    except Exception as e:
        data = {"ok": False, "command": "verify_structural", "error": str(e),
                "errors": [str(e)]}
        _emit(data, json_output, pretty)
        raise typer.Exit(code=1) from None


verify_app.command("consistency")(consistency_cmd)
verify_app.command("claim")(claim_cmd)
verify_app.command("structural")(structural_cmd)
