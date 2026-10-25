"""[iter_288 / PLAN P3.3] 设计审计分析 —— 原 exp 10 条创意的重新实现。

十条想法（docs/EXP_IDEAS.md）在这里落成 8 个可锁定语义的检查：
  1. protocols            总线协议识别（名称模式，pattern）
  2. handshakes           valid/ready 配对与依赖方向（图可达性，heuristic）
  3. backpressure_cycles  反压环路候选（heuristic）
  4. assertions           SVA 覆盖（measured）+ 关键信号缺口
  5. coverage             covergroup 覆盖（measured）+ 建议
  6. verification_gaps    验证缺口排序（4+5+风险 聚合）
  7. risk                 改动风险分级（结构启发式）
  8. constraints          rand 变量与约束覆盖（文本模式，pattern）
  9. cdc                  跨时钟域候选（clock_domain 边 + 同步器名称，heuristic）
 10. timing               组合链长度估计（结构，heuristic）

为什么不把旧 exp 代码搬回来：旧实现输出的是"结论"（协议判定/死锁），
本模块输出"证据 + 候选 + 置信度"，并且每条规则都有可复现的测试。
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

CHECKS = (
    "protocols", "handshakes", "backpressure_cycles", "assertions",
    "coverage", "verification_gaps", "risk", "constraints", "cdc", "timing",
)

# 关键信号角色（用于缺口/风险排序）
_CLOCK_RE = re.compile(r"(^|_)(clk|clock|aclk|hclk|pclk|sclk)(_|$)", re.I)
_RESET_RE = re.compile(r"(^|_)(rst|reset|arst|rst_n|resetn|por)(_|$)", re.I)
_VALID_RE = re.compile(r"valid|req$|_req|grant|gnt", re.I)
_READY_RE = re.compile(r"ready|ack", re.I)

# 协议签名：端口名后缀 → 协议
_PROTOCOL_SIGS: dict[str, dict] = {
    "axi4": {
        "core": ("awvalid", "awready", "wvalid", "wready", "bvalid", "bready",
                 "arvalid", "arready", "rvalid", "rready"),
        "min": 6,
        "channels": {"aw": ("aw",), "w": ("w",), "b": ("b",), "ar": ("ar",), "r": ("r",)},
    },
    "axi4_stream": {
        "core": ("tvalid", "tready", "tdata", "tlast"),
        "min": 3,
        "channels": {"stream": ("t",)},
    },
    "apb": {
        "core": ("psel", "penable", "pwrite", "paddr", "pwdata", "prdata", "pready"),
        "min": 4,
        "channels": {"apb": ("p",)},
    },
    "ahb": {
        "core": ("hsel", "hready", "htrans", "haddr", "hwrite", "hrdata", "hwdata"),
        "min": 4,
        "channels": {"ahb": ("h",)},
    },
    "wishbone": {
        "core": ("cyc", "stb", "ack", "we", "adr", "dat_o", "dat_i"),
        "min": 4,
        "channels": {"wb": ("",)},
    },
    "tilelink": {
        "core": ("a_valid", "a_ready", "d_valid", "d_ready", "a_opcode", "d_opcode"),
        "min": 4,
        "channels": {"a": ("a_",), "d": ("d_",)},
    },
}


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _instances(tracer) -> dict:
    """MIG 实例 → {instance_id: ModuleInstanceNode}（无 MIG 时返回空）。"""
    mig = tracer.get_module_graph()
    return dict(getattr(mig, "instances", {}) or {})


def _port_names(inst) -> list[str]:
    return [str(p).lower() for p in getattr(inst, "ports", {}) or {}]


def _node_id(inst_id: str, port: str) -> str:
    return f"{inst_id}.{port}"


def _reachable(graph, src: str, dst: str, max_depth: int = 8) -> bool:
    """图上 src 是否能到 dst（只走 DRIVER/CONNECTION，限深）。"""
    if src not in graph or dst not in graph:
        return False
    if src == dst:
        return False
    seen = {src}
    q = deque([(src, 0)])
    while q:
        cur, depth = q.popleft()
        if depth >= max_depth:
            continue
        for nxt in graph.successors(cur):
            if nxt == dst:
                return True
            if nxt in seen:
                continue
            seen.add(nxt)
            q.append((nxt, depth + 1))
    return False


def _common_prefix(a: str, b: str) -> str:
    n = 0
    for ca, cb in zip(a.lower(), b.lower(), strict=False):
        if ca != cb:
            break
        n += 1
    return a[:n]


# ---------------------------------------------------------------------------
# 1. 协议识别（pattern）
# ---------------------------------------------------------------------------
def check_protocols(tracer) -> list[dict]:
    out = []
    for inst_id, inst in sorted(_instances(tracer).items()):
        names = _port_names(inst)
        matches = []
        for proto, sig in _PROTOCOL_SIGS.items():
            hits = sorted({n for n in names if any(n.endswith(tok) for tok in sig["core"])})
            if len(hits) < sig["min"]:
                continue
            # 置信度：核心端口命中比例
            ratio = len(hits) / len(sig["core"])
            matches.append({
                "protocol": proto,
                "confidence": "pattern",
                "matched_ports": hits,
                "core_coverage": round(ratio, 2),
            })
        if matches:
            matches.sort(key=lambda m: -m["core_coverage"])
            out.append({"instance": inst_id, "module_type": getattr(inst, "module_type", ""),
                        "candidates": matches})
    return out


# ---------------------------------------------------------------------------
# 2. valid/ready 握手对 + 依赖方向
# ---------------------------------------------------------------------------
def _handshake_pairs(tracer) -> list[dict]:
    pairs = []
    for inst_id, inst in sorted(_instances(tracer).items()):
        by_prefix: dict[str, dict[str, str]] = defaultdict(dict)
        for pname in getattr(inst, "ports", {}) or {}:
            low = pname.lower()
            if _VALID_RE.search(low) and "valid" in low or low.endswith("req"):
                prefix = _common_prefix(low, re.sub(r"(valid|req)$", "", low))
                by_prefix[prefix]["valid"] = pname
            elif _READY_RE.search(low):
                prefix = _common_prefix(low, re.sub(r"(ready|ack|gnt|grant)$", "", low))
                by_prefix[prefix]["ready"] = pname
        for prefix, ports in by_prefix.items():
            if "valid" in ports and "ready" in ports:
                pairs.append({
                    "instance": inst_id,
                    "prefix": prefix or "(whole)",
                    "valid": _node_id(inst_id, ports["valid"]),
                    "ready": _node_id(inst_id, ports["ready"]),
                })
    return pairs


def check_handshakes(tracer) -> list[dict]:
    graph = tracer.get_graph()
    out = []
    for pair in _handshake_pairs(tracer):
        v2r = _reachable(graph, pair["valid"], pair["ready"])
        r2v = _reachable(graph, pair["ready"], pair["valid"])
        if v2r and r2v:
            classification = "combinational_dependency"
        elif v2r:
            classification = "ready_depends_on_valid"
        elif r2v:
            classification = "valid_depends_on_ready"
        else:
            classification = "independent_or_registered"
        out.append({**pair, "classification": classification,
                    "confidence": "heuristic"})
    return out


# ---------------------------------------------------------------------------
# 3. 反压环路候选
# ---------------------------------------------------------------------------
def check_backpressure_cycles(tracer) -> list[dict]:
    graph = tracer.get_graph()
    pairs = check_handshakes(tracer)
    ready_edges: dict[str, set[str]] = defaultdict(set)
    for a in pairs:
        for b in pairs:
            if a is b or a["instance"] != b["instance"]:
                continue
            # a 的 ready 依赖 b 的 ready → 反压边 b → a
            if _reachable(graph, b["ready"], a["ready"]):
                ready_edges[b["valid"]].add(a["valid"])
    # 找简单环（限长 6）
    cycles = []

    def dfs(node, path, start):
        if len(path) > 6:
            return
        for nxt in sorted(ready_edges.get(node, ())):
            if nxt == start:
                cycles.append(path + [nxt])
            elif nxt not in path:
                dfs(nxt, path + [nxt], start)

    for node in sorted(ready_edges):
        dfs(node, [node], node)
    # 去重（同一环的不同起点）
    uniq = []
    for c in cycles:
        key = tuple(sorted(c[:-1]))
        if all(tuple(sorted(u[:-1])) != key for u in uniq):
            uniq.append(c)
    return [{"candidate_cycle": c, "confidence": "heuristic"} for c in uniq[:10]]


# ---------------------------------------------------------------------------
# 4. SVA 断言覆盖
# ---------------------------------------------------------------------------
def _sources_for_audit(tracer) -> dict[str, str]:
    sources = dict(getattr(tracer, "_sources", {}) or {})
    if sources:
        return sources
    from pathlib import Path

    filelist = getattr(tracer, "_filelist", None)
    if not filelist:
        return {}
    base = Path(filelist).parent
    for raw in Path(filelist).read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith(("//", "#", "+incdir+", "+define+")):
            continue
        p = Path(line)
        p = p if p.is_absolute() else base / p
        if p.is_file():
            sources[str(p)] = p.read_text(errors="replace")
    return sources


def check_assertions(tracer) -> dict:
    from ..sva_extractor import SVAExtractor

    sources = _sources_for_audit(tracer)
    if not sources:
        return {"assertions": 0, "signal_refs": {}, "errors": ["no sources"]}
    sva = SVAExtractor(sources).extract()
    refs = {sig: len(ids) for sig, ids in (sva.signal_refs or {}).items()}
    return {
        "assertions": len(sva.assertions),
        "properties": len(sva.properties),
        "sequences": len(sva.sequences),
        "signal_refs": dict(sorted(refs.items(), key=lambda kv: -kv[1])[:50]),
        "errors": list(sva.errors),
        "confidence": "measured",
    }


# ---------------------------------------------------------------------------
# 5. covergroup 覆盖
# ---------------------------------------------------------------------------
def check_coverage(tracer) -> dict:
    from ..covergroup_extractor import CovergroupExtractor

    sources = _sources_for_audit(tracer)
    if not sources:
        return {"covergroups": 0, "coverpoints": 0, "samples": [], "errors": ["no sources"]}
    try:
        cgs = CovergroupExtractor(sources, compiler=tracer._get_compiler()).extract()
    except Exception as e:  # 覆盖提取失败不能拖垮 audit
        return {"covergroups": 0, "coverpoints": 0, "samples": [],
                "errors": [f"{type(e).__name__}: {e}"]}
    samples = []
    total_cp = 0
    for cg in cgs:
        total_cp += len(cg.coverpoints)
        for cp in cg.coverpoints:
            samples.append({"covergroup": cg.name, "coverpoint": getattr(cp, "name", ""),
                            "signal": getattr(cp, "signal", ""),
                            "bins": len(getattr(cp, "bins", []) or [])})
    return {"covergroups": len(cgs), "coverpoints": total_cp,
            "samples": samples[:50], "suggested": _suggest_covergroups(tracer, samples),
            "errors": [], "confidence": "measured"}


def _suggest_covergroups(tracer, samples: list[dict], limit: int = 10) -> list[dict]:
    """给"没有任何 coverpoint"的 valid/ready 握手对生成**建议片段**（不写文件）。"""
    covered = {str(s.get("signal", "")).lower() for s in samples}
    out = []
    for pair in check_handshakes(tracer):
        valid, ready = pair["valid"], pair["ready"]
        if valid.lower() in covered or ready.lower() in covered:
            continue
        inst = pair["instance"]
        inst_node = _instances(tracer).get(inst)
        clock_port = None
        for pname in (getattr(inst_node, "ports", {}) or {}):
            if _CLOCK_RE.search(pname):
                clock_port = _node_id(inst, pname)
                break
        if clock_port is None:
            continue
        tag = re.sub(r"\W+", "_", pair["prefix"] or "hs")
        out.append({
            "for": {"instance": inst, "prefix": pair["prefix"]},
            "code": (
                f"covergroup cg_{tag} @(posedge {clock_port.rsplit('.', 1)[-1]});\n"
                f"  cp_valid: coverpoint {valid.rsplit('.', 1)[-1]};\n"
                f"  cp_ready: coverpoint {ready.rsplit('.', 1)[-1]};\n"
                f"  cross_valid_ready: cross cp_valid, cp_ready;\n"
                f"endgroup"
            ),
            "note": "建议片段（未落盘）；cross 覆盖 valid/ready 四象限",
        })
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# 6. 验证缺口（断言 + 覆盖 + 风险 聚合）
# ---------------------------------------------------------------------------
def check_verification_gaps(tracer, assertions: dict, coverage: dict) -> list[dict]:
    graph = tracer.get_graph()
    sva_refs = {k.lower() for k in (assertions.get("signal_refs") or {})}
    cov_sigs = {s.get("signal", "").lower() for s in (coverage.get("samples") or [])}
    gaps = []
    for node_id in graph.nodes():
        name = node_id.rsplit(".", 1)[-1].lower()
        if not (_CLOCK_RE.search(name) or _RESET_RE.search(name)
                or _VALID_RE.search(name) or _READY_RE.search(name)):
            continue
        has_sva = any(name in ref or ref in name for ref in sva_refs if ref)
        has_cov = any(name == s or name in s for s in cov_sigs if s)
        load_count = len(list(graph.successors(node_id))) if node_id in graph else 0
        if has_sva or has_cov:
            continue
        if load_count < 2:
            continue
        gaps.append({"signal": node_id, "role": _role(name),
                     "loads": load_count,
                     "has_assertion": has_sva, "has_coverage": has_cov})
    gaps.sort(key=lambda g: (-g["loads"], g["signal"]))
    return gaps[:40]


def _role(name: str) -> str:
    if _CLOCK_RE.search(name):
        return "clock"
    if _RESET_RE.search(name):
        return "reset"
    if _VALID_RE.search(name):
        return "valid"
    if _READY_RE.search(name):
        return "ready"
    return "data"


# ---------------------------------------------------------------------------
# 7. 改动风险分级
# ---------------------------------------------------------------------------
def check_risk(tracer) -> list[dict]:
    graph = tracer.get_graph()
    rows = []
    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue
        name = node_id.rsplit(".", 1)[-1].lower()
        if node.kind.name not in ("SIGNAL", "REG", "PORT_IN", "PORT_OUT", "PORT_INOUT"):
            continue
        role = _role(name)
        base = {"clock": 3, "reset": 3, "valid": 2, "ready": 2}.get(role, 1)
        loads = len(list(graph.successors(node_id)))
        drivers = len(list(graph.predecessors(node_id)))
        import math

        score = base * (1 + math.log10(1 + loads + drivers))
        rows.append({"signal": node_id, "role": role, "loads": loads,
                     "drivers": drivers, "score": round(score, 2)})
    rows.sort(key=lambda r: (-r["score"], r["signal"]))
    return rows[:30]


# ---------------------------------------------------------------------------
# 8. rand 变量与约束覆盖（文本模式）
# ---------------------------------------------------------------------------
_CLASS_RE = re.compile(r"\bclass\s+(\w+)")
# `rand bit [7:0] addr;` / `rand int x;` / `rand my_type y;` / `randc bit z;`
_RAND_RE = re.compile(
    r"\brandc?\b\s+(?:(?:bit|logic|int|byte|shortint)\s*)?(?:\[[^\]]*\]\s*)?"
    r"(?:[A-Za-z_]\w*\s+)?([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*;"
)
_CONSTRAINT_RE = re.compile(r"\bconstraint\s+(\w+)\s*\{", re.S)


def check_constraints(tracer) -> dict:
    sources = _sources_for_audit(tracer)
    classes = []
    for text in sources.values():
        for m in _CLASS_RE.finditer(text):
            name = m.group(1)
            end = text.find("endclass", m.end())
            body = text[m.end(): end if end != -1 else len(text)]
            rand_vars = sorted(set(_RAND_RE.findall(body)))
            constraints = [c.group(1) for c in _CONSTRAINT_RE.finditer(body)]
            mentioned = {v for v in rand_vars for c in re.finditer(
                r"constraint\s+\w+\s*\{(.*?)\}", body, re.S) if v in c.group(1)}
            unconstrained = [v for v in rand_vars if v not in mentioned]
            if rand_vars or constraints:
                classes.append({
                    "class": name, "rand_vars": rand_vars,
                    "constraints": constraints,
                    "rand_vars_without_constraint": unconstrained,
                })
    return {"classes": classes, "confidence": "pattern",
            "note": "文本模式：只覆盖 rand 声明与 constraint 块的存在性，不判定约束可达性"}


# ---------------------------------------------------------------------------
# 9. CDC 候选
# ---------------------------------------------------------------------------
_SYNC_RE = re.compile(r"sync|ff2|meta|cdc|async", re.I)


def check_cdc(tracer) -> list[dict]:
    """跨时钟域候选：把 DRIVER 边上的 clock_domain 沿 CONNECTION 传播 2 跳，
    同一网络节点上出现 ≥2 个域 → 候选；路径上有 sync/ff2/meta 命名 → 标注可能已同步。

    只报"候选"：同步器判定是名称启发式，不保证正确（见 confidence）。
    """
    graph = tracer.get_graph()
    CONN = "CONNECTION"
    domains_on: dict[str, set[str]] = defaultdict(set)

    def spread(start_node: str, domain: str, forward: bool, hops: int = 2) -> None:
        domains_on[start_node].add(domain)
        frontier = [(start_node, 0)]
        seen = {start_node}
        while frontier:
            cur, depth = frontier.pop()
            if depth >= hops:
                continue
            nbrs = graph.successors(cur) if forward else graph.predecessors(cur)
            for nxt in nbrs:
                edges = (graph.get_edges(cur, nxt) if forward else graph.get_edges(nxt, cur))
                if not any(e.kind.name == CONN for e in edges):
                    continue
                domains_on[nxt].add(domain)
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append((nxt, depth + 1))

    for (src, dst), edges in graph._edge_data.items():
        for e in edges:
            if e.kind.name != "DRIVER" or not e.clock_domain:
                continue
            spread(dst, e.clock_domain, forward=True)    # 驱动端寄存器 → 后续网络
            spread(src, e.clock_domain, forward=False)   # 采样端寄存器 → 上游网络

    out = []
    for node_id, domains in sorted(domains_on.items()):
        if len(domains) < 2:
            continue
        node = graph.get_node(node_id)
        if node is None or node.kind.name not in ("SIGNAL", "REG", "PORT_IN", "PORT_OUT"):
            continue
        out.append({
            "signal": node_id,
            "domains": sorted(domains),
            "has_sync_hint": _has_sync_between(graph, node_id),
            "confidence": "heuristic",
        })
        if len(out) >= 30:
            break
    return out


def _has_sync_between(graph, node_id: str, max_depth: int = 6) -> bool:
    seen = {node_id}
    q = deque([(node_id, 0)])
    while q:
        cur, depth = q.popleft()
        if depth >= max_depth:
            continue
        for nxt in list(graph.successors(cur)) + list(graph.predecessors(cur)):
            if _SYNC_RE.search(nxt.rsplit(".", 1)[-1]):
                return True
            if nxt in seen:
                continue
            seen.add(nxt)
            q.append((nxt, depth + 1))
    return False


# ---------------------------------------------------------------------------
# 10. 组合链长度估计
# ---------------------------------------------------------------------------
def check_timing(tracer, top_n: int = 10) -> list[dict]:
    graph = tracer.get_graph()
    comb_kinds = {"DRIVER", "CONNECTION"}

    def is_comb(node_id: str) -> bool:
        node = graph.get_node(node_id)
        if node is None:
            return False
        return not (node.is_clock or node.is_reset)

    # 拓扑/DFS 记忆化最长链（含环保护）
    memo: dict[str, tuple[int, list[str]]] = {}
    visiting: set[str] = set()

    def longest(node_id: str) -> tuple[int, list[str]]:
        if node_id in memo:
            return memo[node_id]
        if node_id in visiting:
            return (0, [node_id])
        visiting.add(node_id)
        best = (0, [node_id])
        for nxt in graph.successors(node_id):
            if nxt == node_id or not is_comb(nxt):
                continue
            if not any(e.kind.name in comb_kinds for e in graph.get_edges(node_id, nxt)):
                continue
            length, chain = longest(nxt)
            if length + 1 > best[0]:
                best = (length + 1, [node_id] + chain)
        visiting.discard(node_id)
        memo[node_id] = best
        return best

    chains = []
    for node_id in graph.nodes():
        if not is_comb(node_id):
            continue
        length, chain = longest(node_id)
        if length >= 3:
            chains.append((length, chain))
    seen: set[tuple[str, ...]] = set()
    rows = []
    for length, chain in sorted(chains, key=lambda x: -x[0]):
        key = tuple(chain[:3])
        if key in seen:
            continue
        seen.add(key)
        rows.append({"length": length, "chain": chain, "confidence": "heuristic"})
        if len(rows) >= top_n:
            break
    return rows


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def run_audit(tracer, checks: list[str] | None = None) -> dict:
    """跑选定的检查，返回结构化结果（未知检查名 → 立即报错）。"""
    wanted = list(checks or CHECKS)
    unknown = [c for c in wanted if c not in CHECKS]
    if unknown:
        raise ValueError(f"未知检查项: {unknown}（可用: {list(CHECKS)}）")

    result: dict = {"target": getattr(tracer, "_target_module", None) or None,
                    "checks": wanted, "sections": {}}
    assertions = None
    coverage = None
    for name in wanted:
        if name == "protocols":
            value = check_protocols(tracer)
        elif name == "handshakes":
            value = check_handshakes(tracer)
        elif name == "backpressure_cycles":
            value = check_backpressure_cycles(tracer)
        elif name == "assertions":
            assertions = check_assertions(tracer)
            value = assertions
        elif name == "coverage":
            coverage = check_coverage(tracer)
            value = coverage
        elif name == "verification_gaps":
            if assertions is None:
                assertions = check_assertions(tracer)
            if coverage is None:
                coverage = check_coverage(tracer)
            value = check_verification_gaps(tracer, assertions, coverage)
        elif name == "risk":
            value = check_risk(tracer)
        elif name == "constraints":
            value = check_constraints(tracer)
        elif name == "cdc":
            value = check_cdc(tracer)
        elif name == "timing":
            value = check_timing(tracer)
        result["sections"][name] = value

    result["summary"] = {
        "checks": len(result["sections"]),
        "findings": sum(
            v if isinstance(v, int) else len(v)
            for v in result["sections"].values()
        ),
    }
    return result
