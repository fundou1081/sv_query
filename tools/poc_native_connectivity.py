#!/usr/bin/env python3
"""
poc_native_connectivity.py — **POC** (概念验证, 不是生产工具)

════════════════════════════════════════════════════════════════════════
⚠️ 这是 POC，不是产品代码
════════════════════════════════════════════════════════════════════════

【要回答的问题】
    用 pyslang **原生 elaborated 端口连接** (`InstanceSymbol.portConnections`
    + `PortSymbol.internalSymbol`) 建出来的连通图，和现在 `paths`(PathResolver)
    / `dataflow analyze`(DataFlowGraph) 的结论差多少？差异在哪一类信号对上？

【适用场景】
    ✅ 评估"要不要把两套路径实现换成 slang-native 单一连通层"
    ✅ 盘点现有图里的"模块定义命名空间影子节点"占比
    ✅ 为后续迁移列出**具体的**差异信号对（而不是靠推断）

【优点】
    1. 不碰 src/ —— 只在 tools/ 下读 + 算，零产品风险
    2. 原生侧只用 public API：`Compilation` / `root.topInstances` /
       `portConnections` / `hierarchicalPath`，不猜、不正则
    3. 输出**可用于决策**的三张表：原生独有 / 旧实现独有 / 两边不一致
    4. 结论可复现：同一 fixture + 同一采样种子 → 同一份报告

【缺陷 / 已知局限（务必先读）】
    1. **只比较可达性，不比较路径质量**：同一条可达的路径，两边跳数/经过节点
       可能不同；本 POC 不判断"哪条路径更对"。
    2. **只覆盖端口连接 + 现成 SignalGraph**：原生侧 POC 只从 `portConnections`
       建"跨模块边"，模块内部的 dataflow 边仍借用旧 SignalGraph —— 所以它测的是
       "跨模块这一层对不对"，**不是**完整原生重写。
    3. **legacy_directed 用 `nx.has_path` 近似 `dataflow analyze`**：
       dataflow 用 `all_simple_paths(cutoff=50)`，深于 50 跳的路径它也会报不可达；
       本 POC 的 `has_path` 没有 cutoff → 极深路径上两者可能不一致（报告里会标注）。
    4. **不做 generate-block 实例展开**（沿用项目 D2 决策：generate 内部信号不进图）。
    5. **不评估性能收益**：只记录建图耗时，不宣称加速（样本太小，无统计意义）。
    6. 仅在**小 fixture** 上验证过（minimal_3module / golden_mini / scheduler_minimal）；
       大工程（OpenTitan）未跑。

【明确不做】
    ❌ 不改 src/、不注册 CLI、不进 capabilities
    ❌ 不删除任何旧实现
    ❌ 不下"必须迁移"的结论 —— 只给数据

【用法】
    python3 tools/poc_native_connectivity.py --filelist sim/tests/fixtures/minimal_3module/filelist.f
    python3 tools/poc_native_connectivity.py --filelist F --json /tmp/poc.json
    python3 tools/poc_native_connectivity.py --filelist F --max-pairs 40 --seed 7

退出码: 0 = 报告已生成; 1 = 输入/编译失败 (不静默)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import REPO_ROOT, ensure_src_first  # noqa: E402

ensure_src_first()

import pyslang  # noqa: E402
from pyslang import ast  # noqa: E402


# ==============================================================================
# 原生侧: 用 elaborated AST 建跨模块连通边
# ==============================================================================

def _safe_path(sym) -> str | None:
    """取 symbol 的 hierarchicalPath; 非 utf8 标识符会抛 UnicodeDecodeError。"""
    try:
        hp = sym.hierarchicalPath
        return str(hp) if hp is not None else None
    except (UnicodeDecodeError, TypeError, AttributeError):
        return None


def _resolve_conn_expr(expr) -> tuple[str | None, str]:
    """从端口连接表达式取父侧 symbol 路径。

    返回 (path, note)。note 说明用了哪条规则, 便于人工核对。
      - input  : NamedValueExpression → .symbol
      - input  : Conversion/ElementSelect 壳 → 剥壳后取 symbol
      - output : AssignmentExpression → .left.symbol
    """
    if expr is None:
        return None, "expr=None"

    kind = str(getattr(expr, "kind", ""))
    if "Assignment" in kind:                      # 输出端口 .q(sig)
        left = getattr(expr, "left", None)
        if left is not None:
            sym = getattr(left, "symbol", None)
            if sym is not None:
                return _safe_path(sym), "assignment.left.symbol"
        return None, "assignment(no left.symbol)"

    # 输入端口: 可能是 NamedValue / Conversion / ElementSelect / RangeSelect 壳
    node = expr
    for _ in range(8):                            # 防病态嵌套
        sym = getattr(node, "symbol", None)
        if sym is not None:
            return _safe_path(sym), f"{kind}.symbol"
        nxt = getattr(node, "operand", None)
        if nxt is None:
            break
        node, kind = nxt, str(getattr(nxt, "kind", ""))

    if "IntegerLiteral" in kind or "EmptyArgument" in kind:
        return None, f"{kind}(常量/悬空)"
    return None, f"unresolved({kind})"


def build_native(filelist: Path) -> dict:
    """建原生跨模块边集。

    Returns:
        {"nodes": set, "edges": [(src, dst, port, direction)], "stats": {...},
         "unresolved": [(instance, port, note)]}
    """
    files = _read_filelist(filelist)
    t0 = time.time()

    comp = ast.Compilation()
    for f in files:
        comp.addSyntaxTree(pyslang.syntax.SyntaxTree.fromText(f.read_text(errors="replace"), name=str(f)))

    nodes: set[str] = set()
    instance_paths: set[str] = set()
    edges: list[tuple[str, str, str, str]] = []
    unresolved: list[tuple[str, str, str]] = []
    inst_count = 0

    def walk(inst, depth: int = 0) -> None:
        nonlocal inst_count
        if depth > 40:                            # 防御: 病态层级
            return
        ipath = _safe_path(inst)
        if ipath:
            instance_paths.add(ipath)
        for conn in inst.portConnections:
            port = getattr(conn, "port", None)
            if port is None:
                continue
            port_name = _safe_name(port)
            child = _safe_path(getattr(port, "internalSymbol", None))
            parent, note = _resolve_conn_expr(getattr(conn, "expression", None))
            direction = str(getattr(port, "direction", "")).split(".")[-1].lower()
            if child:
                nodes.add(child)
            if parent:
                nodes.add(parent)
            if not child or not parent:
                unresolved.append((_safe_path(inst) or "?", port_name, note))
                continue
            # In: 父 → 子;  Out: 子 → 父;  InOut: 双向
            if direction in ("in", "input"):
                edges.append((parent, child, port_name, "in"))
            elif direction in ("out", "output"):
                edges.append((child, parent, port_name, "out"))
            else:
                edges.append((parent, child, port_name, direction or "?"))
                edges.append((child, parent, port_name, direction or "?"))

        for m in getattr(inst, "body", []) or []:
            if type(m).__name__ == "InstanceSymbol":
                inst_count += 1
                walk(m, depth + 1)

    root = comp.getRoot()
    tops = list(getattr(root, "topInstances", []) or [])
    for top in tops:
        walk(top)

    return {
        "nodes": nodes,
        "instance_paths": instance_paths,
        "edges": edges,
        "unresolved": unresolved,
        "stats": {
            "files": len(files),
            "top_instances": len(tops),
            "child_instances": inst_count,
            "native_nodes": len(nodes),
            "port_edges": len(edges),
            "build_seconds": round(time.time() - t0, 3),
        },
    }


def _safe_name(sym) -> str:
    try:
        return str(sym.name)
    except (UnicodeDecodeError, TypeError, AttributeError):
        return "<non-utf8>"


def _read_filelist(filelist: Path) -> list[Path]:
    """读 filelist: 支持绝对/相对路径与 +incdir+ (POC 只取 .sv/.v 条目)。"""
    base = filelist.parent
    out: list[Path] = []
    for raw in filelist.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith(("//", "#", "+incdir+", "+define+")):
            continue
        p = Path(line)
        p = p if p.is_absolute() else (base / p)
        if p.exists() and p.suffix in (".sv", ".v", ".svh", ".vh"):
            out.append(p)
    if not out:
        raise SystemExit(f"filelist 里没有可用的 .sv/.v 条目: {filelist}")
    return out

# ==============================================================================
# 旧实现侧: UnifiedTracer 的图 / PathResolver
# ==============================================================================

def build_legacy(filelist: Path) -> dict:
    from trace.unified_tracer import UnifiedTracer

    t0 = time.time()
    tracer = UnifiedTracer(filelist=str(filelist), log_level="ERROR",
                           preprocess_macros=True)
    graph = tracer.build_graph()
    return {
        "tracer": tracer,
        "graph": graph,
        "resolver": tracer.get_path_resolver(),
        "nodes": set(graph.nodes()),
        "edges": [(u, v) for u, v in graph.edges()],
        "build_seconds": round(time.time() - t0, 3),
    }


# ==============================================================================
# 图算法 (POC 自实现, 不依赖 networkx 之外的假设)
# ==============================================================================

def build_adj(edges, directed: bool = True) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for src, dst in edges:
        adj[src].add(dst)
        if not directed:
            adj[dst].add(src)
    return adj


def reachable(adj: dict[str, set[str]], src: str, dst: str) -> bool:
    if src == dst:
        return True
    seen = {src}
    q = deque([src])
    while q:
        cur = q.popleft()
        for nxt in adj.get(cur, ()):
            if nxt in seen:
                continue
            if nxt == dst:
                return True
            seen.add(nxt)
            q.append(nxt)
    return False


# ==============================================================================
# 采样
# ==============================================================================

def collect_pairs(native: dict, legacy: dict, max_pairs: int, seed: int) -> list[tuple[str, str, str]]:
    """生成对比信号对。

    1. port  —— 每条原生端口边的两端 (正反两向)
    2. cross —— 顶层端口 → 实例端口 (跨模块)
    3. rand  —— 双方命名空间交集内随机 (确定性种子)
    """
    pairs: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    universe = legacy["nodes"] | native["nodes"]

    def add(src: str, dst: str, tag: str) -> None:
        if src == dst or (src, dst) in seen:
            return
        if src not in universe or dst not in universe:
            return
        seen.add((src, dst))
        pairs.append((src, dst, tag))

    for src, dst, _port, _d in native["edges"]:
        add(src, dst, "port")
        add(dst, src, "port-reverse")

    # 跨模块深链: 父网 ↔ 该实例内部更深节点 (这是"跨模块能力"的真正考点)
    all_nodes = sorted(universe)
    for src, dst, _port, _d in native["edges"]:
        # child 形如 top.u.port → 所属实例是 top.u
        prefix = dst.rsplit(".", 1)[0] + "."
        descendants = [n for n in all_nodes if n.startswith(prefix) and n != dst]
        for d in descendants[:3]:
            add(src, d, "deep")
            add(d, src, "deep-reverse")

    rng = random.Random(seed)
    common = sorted(legacy["nodes"] & native["nodes"])
    if len(common) >= 2:
        for _ in range(min(max_pairs, 200)):
            a, b = rng.sample(common, 2)
            add(a, b, "rand")

    return pairs[:max_pairs] if max_pairs > 0 else pairs


# ==============================================================================
# 对比
# ==============================================================================

def compare(native: dict, legacy: dict, pairs, max_pairs: int) -> dict:
    legacy_edges = legacy["edges"]
    aug_edges = list(legacy_edges) + [(s, d) for s, d, _p, _dir in native["edges"]]
    adj_legacy_dir = build_adj(legacy_edges, directed=True)
    adj_aug_dir = build_adj(aug_edges, directed=True)
    adj_aug_undir = build_adj(aug_edges, directed=False)

    rows = []
    for src, dst, tag in pairs:
        legacy_dir = reachable(adj_legacy_dir, src, dst)
        aug_dir = reachable(adj_aug_dir, src, dst)
        aug_undir = reachable(adj_aug_undir, src, dst)

        resolver_found = False
        endpoint_ok = None
        path_len = None
        if legacy["resolver"] is not None:
            try:
                path = legacy["resolver"].find_path(src, dst)
            except Exception:
                path = None
            if path:
                resolver_found = True
                path_len = len(path) - 1
                endpoint_ok = (path[-1] == dst)

        if aug_dir and not legacy_dir:
            cls = "A. 增强后可达 / 旧有向不可达 (跨模块缺口)"
        elif legacy_dir and not aug_dir:
            cls = "B. 旧有向可达 / 增强后不可达 (异常)"
        elif aug_undir != resolver_found:
            cls = "C. PathResolver 无向结论与图不符"
        else:
            cls = "D. 一致"

        rows.append({
            "src": src, "dst": dst, "tag": tag, "class": cls,
            "legacy_directed": legacy_dir,
            "aug_directed": aug_dir,
            "aug_undirected": aug_undir,
            "resolver_found": resolver_found,
            "resolver_endpoint_ok": endpoint_ok,
            "resolver_hops": path_len,
        })

    # 方向性统计: 无向可达但有向不可达 (说明"路径"其实是逆着数据流)
    reverse_only_aug = sum(
        1 for r in rows if r["aug_undirected"] and not r["aug_directed"]
    )
    resolver_bad_endpoint = [
        r for r in rows if r["resolver_found"] and r["resolver_endpoint_ok"] is False
    ]

    return {
        "rows": rows,
        "summary": dict(Counter(r["class"] for r in rows)),
        "reverse_only_pairs": reverse_only_aug,
        "resolver_bad_endpoint_count": len(resolver_bad_endpoint),
        "resolver_bad_endpoint_examples": resolver_bad_endpoint[:10],
        "edge_counts": {
            "legacy_edges": len(legacy_edges),
            "native_port_edges": len(native["edges"]),
            "augmented_edges": len(aug_edges),
        },
    }


def _make_is_shadow(native: dict):
    """实例作用域判定: 节点必须位于某个**实例**的子树下。

    (旧版只看"首段是否出现在原生节点里" → 把顶层模块自己的节点误判成影子.)
    """
    ips = sorted(native.get("instance_paths") or (), key=len, reverse=True)

    def is_shadow(node: str) -> bool:
        for ip in ips:
            if node == ip or node.startswith(ip + "."):
                return False
        return True

    return is_shadow


def namespace_stats(legacy: dict, native: dict) -> dict:
    """量化"双命名空间"问题: 实例作用域 vs 模块定义影子。

    实例作用域 = 该 id 的首段出现在原生 (slang) 节点里
    影子       = 首段不在原生节点里 (我们自己合成的模块定义图)
    """
    is_shadow = _make_is_shadow(native)

    inst_nodes = [n for n in legacy["nodes"] if not is_shadow(n)]
    shadow_nodes = [n for n in legacy["nodes"] if is_shadow(n)]

    inst_edges = shadow_edges = cross_edges = 0
    for u, v in legacy["edges"]:
        su, sv = is_shadow(u), is_shadow(v)
        if su and sv:
            shadow_edges += 1
        elif not su and not sv:
            inst_edges += 1
        else:
            cross_edges += 1

    # 弱连通分量 (整图)
    import networkx as nx
    comps = list(nx.weakly_connected_components(legacy["graph"]))
    comps.sort(key=len, reverse=True)

    # 影子子图自身是否成岛 (不含任何实例节点)
    shadow_graph = legacy["graph"].subgraph(shadow_nodes)
    shadow_isolated_like = [n for n in shadow_nodes if shadow_graph.degree(n) == 0]

    return {
        "instance_nodes": len(inst_nodes),
        "shadow_nodes": len(shadow_nodes),
        "instance_edges": inst_edges,
        "shadow_edges": shadow_edges,
        "cross_namespace_edges": cross_edges,
        "weak_components": len(comps),
        "largest_component": len(comps[0]) if comps else 0,
        "shadow_isolated_in_subgraph": len(shadow_isolated_like),
    }


def reachability_island(legacy: dict, native: dict) -> dict:
    """从"顶层输入端口"出发, 有向可达的节点里, 实例命名空间 / 影子命名空间各占多少。

    这是最硬的一条: 影子节点如果大面积不可达, 说明它们是与主图断开的平行图,
    任何以影子节点结尾的 `paths` 结果都不是真实数据流路径。
    """
    is_shadow = _make_is_shadow(native)

    sources = [n for n in native["nodes"]
               if not is_shadow(n) and n.count(".") == 1
               and n.split(".")[-1] in {"clk", "rst_n", "valid_i", "data_i", "a", "b",
                                        "phy_tx_start", "s_final", "req_i", "gnt_o"}]
    # 兜底: 用原生节点里所有"顶层模块的直接子节点"
    if not sources:
        sources = [n for n in native["nodes"] if not is_shadow(n) and n.count(".") == 1]

    adj = build_adj(legacy["edges"], directed=True)
    seen: set[str] = set()
    q = deque(sources)
    seen.update(sources)
    while q:
        cur = q.popleft()
        for nxt in adj.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)

    reached_inst = [n for n in seen if not is_shadow(n)]
    reached_shadow = [n for n in seen if is_shadow(n)]
    total_inst = [n for n in legacy["nodes"] if not is_shadow(n)]
    total_shadow = [n for n in legacy["nodes"] if is_shadow(n)]
    return {
        "sources": len(sources),
        "reachable_instance": f"{len(reached_inst)}/{len(total_inst)}",
        "reachable_shadow": f"{len(reached_shadow)}/{len(total_shadow)}",
        "unreachable_shadow_examples": sorted(set(total_shadow) - set(reached_shadow))[:6],
    }


def shadow_stats(legacy: dict, native: dict) -> dict:
    is_shadow = _make_is_shadow(native)
    graph = legacy["graph"]
    shadow = [n for n in legacy["nodes"] if is_shadow(n)]
    isolated = [n for n in shadow if graph.degree(n) == 0]
    return {
        "legacy_nodes": len(legacy["nodes"]),
        "shadow_nodes": len(shadow),
        "shadow_ratio": round(len(shadow) / max(1, len(legacy["nodes"])), 3),
        "shadow_isolated": len(isolated),
        "shadow_examples": sorted(shadow)[:8],
    }


# ==============================================================================
# 报告
# ==============================================================================

def render(report: dict) -> str:
    lines: list[str] = []
    add = lines.append
    add("=" * 78)
    add("POC: slang-native 端口连通性 vs 现有实现")
    add("=" * 78)
    add(f"fixture: {report['filelist']}")
    add("")
    add("--- 原生侧 (portConnections) ---")
    for k, v in report["native"]["stats"].items():
        add(f"  {k:22s} {v}")
    add("")
    add("--- 旧实现侧 ---")
    for k, v in report["legacy"].items():
        add(f"  {k:22s} {v}")
    add("")
    add("--- 图规模 ---")
    for k, v in report["compare"]["edge_counts"].items():
        add(f"  {k:22s} {v}")
    add("")
    add("--- 双命名空间量化 ---")
    for k, v in report["namespace"].items():
        add(f"  {k:30s} {v}")
    add("")
    add("--- 从顶层输入出发的有向可达 (命名空间对比) ---")
    for k, v in report["island"].items():
        add(f"  {k:30s} {v}")
    add("")
    add("--- 影子节点 (旧图有 / slang 无) ---")
    for k, v in report["shadow"].items():
        add(f"  {k:22s} {v}")
    add("")
    add("--- 可达性对比 ---")
    for k, v in sorted(report["compare"]["summary"].items()):
        add(f"  {k:46s} {v}")
    add(f"  {'无向可达但有向不可达 (逆流路径)':46s} {report['compare']['reverse_only_pairs']}")
    add(f"  {'PathResolver 终点 != 请求 dst':46s} {report['compare']['resolver_bad_endpoint_count']}")
    add("")
    bad = report["compare"]["resolver_bad_endpoint_examples"]
    if bad:
        add("--- 终点错误的样例 (PathResolver 返回的路径越过了 dst) ---")
        for r in bad:
            add(f"  {r['src']} → {r['dst']}  ({r['resolver_hops']} hops)")
    add("")
    disagree = [r for r in report["compare"]["rows"] if not r["class"].startswith("D.")]
    if disagree:
        add(f"--- 不一致明细 (前 20 条, 共 {len(disagree)}) ---")
        add(f"  {'src':36s} {'dst':36s} {'tag':10s} 类")
        for r in disagree[:20]:
            add(f"  {r['src']:36s} {r['dst']:36s} {r['tag']:10s} {r['class'][:1]}")
    else:
        add("--- 无不一致 ---")
    add("")
    if report["native"]["unresolved"]:
        add("--- 未解析的端口连接 ---")
        for inst, port, note in report["native"]["unresolved"][:10]:
            add(f"  {inst}.{port}: {note}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="POC: 对比 slang-native 端口连通性与现有实现")
    ap.add_argument("--filelist", required=True)
    ap.add_argument("--max-pairs", type=int, default=120)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    fl = Path(args.filelist)
    if not fl.exists():
        print(f"filelist 不存在: {fl}", file=sys.stderr)
        return 1

    native = build_native(fl)
    legacy = build_legacy(fl)
    pairs = collect_pairs(native, legacy, args.max_pairs, args.seed)

    report = {
        "poc": True,
        "filelist": str(fl),
        "native": {"stats": native["stats"], "unresolved": native["unresolved"][:50]},
        "legacy": {
            "nodes": len(legacy["nodes"]),
            "edges": len(legacy["edges"]),
            "build_seconds": legacy["build_seconds"],
        },
        "shadow": shadow_stats(legacy, native),
        "island": reachability_island(legacy, native),
        "namespace": namespace_stats(legacy, native),
        "compare": compare(native, legacy, pairs, args.max_pairs),
    }

    print(render(report))
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\nJSON 已写入: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
