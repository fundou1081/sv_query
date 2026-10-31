# ==============================================================================
# trace_common.py — trace 命令的共享 helper
# ==============================================================================
"""
[iter_253 T3-3] 从 `semantic/trace.py` 拆出: 这些 helper 被 fanin/fanout/impact/
evidence/overview 共用。拆开是为了让各命令模块能独立引用, 同时保持
`cli.core.semantic.trace` 的既有导入路径 (`_load_tracer_from_snapshot` 被
`cli/_evidence_helpers.py` 引用) —— trace.py 会 re-export。
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import typer

from cli._output import emit_json
from trace.core.graph.models import EdgeKind
from trace.unified_tracer import UnifiedTracer

logger = logging.getLogger(__name__)

def _sanitize_trace_dot_id(s: str) -> str:
    """Sanitize signal ID for DOT. Replace non-alphanumeric with underscore.

    [Phase 2 2026-07-09] Required because trace DOT uses signal IDs as node names.
    E.g. "top.q" → "top_q", "openofdm_tx.dot11_tx.i_clk" → "openofdm_tx_dot11_tx_i_clk".
    """
    import re
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def _format_trace_label(node_id: str, max_len: int = 25) -> str:
    """Format signal ID for DOT label. Truncate if too long."""
    return node_id if len(node_id) <= max_len else "..." + node_id[-(max_len - 3):]


def _generate_trace_dot(
    signal: str,
    drivers_or_loads: list,  # list of driver/load nodes (TraceNode or dict)
    direction: str = "fanin",  # "fanin" or "fanout"
    depth: int | None = None,
    node_kinds: dict | None = None,
) -> str:
    """[Phase 2 2026-07-09] Generate DOT for trace fanin/fanout visualization.

    Layout: 中央 source signal, 多个 drivers/loads as neighbors.
    Edges 标 [+N cycle] 类似 chain (但简化为 +1 each hop).
    REG 节点用粗框 (penwidth=3), CONST 浅绿色, SIGNAL 默认。
    """
    lines = ["digraph trace {"]

    # 标题
    title = (
        f"Trace {direction} of {signal}\\n"
        f"({len(drivers_or_loads)} {'drivers' if direction == 'fanin' else 'loads'}"
    )
    if depth:
        title += f", max-depth={depth}"
    title += ")"
    lines.append(f'  label="{title}";')
    lines.append("  labelloc=t;")
    lines.append("  fontsize=14;")
    lines.append('  fontname="Helvetica-Bold";')
    lines.append("  rankdir=LR;")
    lines.append("  splines=true;")
    lines.append("  bgcolor=white;")
    lines.append("  pad=0.5;")
    lines.append("  nodesep=0.5;")
    lines.append("  ranksep=1.0;")
    lines.append("")

    # 中央 source node
    safe_signal = _sanitize_trace_dot_id(signal)
    short_label = _format_trace_label(signal)
    lines.append(
        f'  "{safe_signal}" [label="{short_label}" '
        f'shape=box style="filled,rounded,bold" '
        f'fillcolor="#3366cc" fontcolor="white" '
        f'fontsize=13 fontname="Helvetica-Bold" penwidth=3];'
    )
    lines.append("")

    # drivers/loads 节点
    target_set = set()
    for item in drivers_or_loads:
        # item may be a dict (from _node_to_dict) or a TraceNode
        if isinstance(item, dict):
            node_id = item.get("id", "")
        else:
            node_id = getattr(item, "id", str(item))

        if not node_id or node_id == signal:
            continue
        target_set.add(node_id)
        safe_id = _sanitize_trace_dot_id(node_id)
        label = _format_trace_label(node_id)

        # kind-based styling
        kind = (node_kinds.get(node_id, "") if node_kinds else "")
        if kind == "REG":
            # REG: 粗框 (penwidth=3)
            color = "#dd8822"
            font_color = "white"
            penwidth = 3
            shape = "box"
        elif kind == "CONST" or node_id.startswith("1'b") or node_id.startswith("32'd"):
            # CONST: 浅绿色
            color = "#ddeedd"
            font_color = "#225522"
            penwidth = 1
            shape = "box"
        elif kind in ("PORT_IN", "PORT_OUT"):
            # PORT: 浅灰色
            color = "#dddddd"
            font_color = "#333333"
            penwidth = 2
            shape = "invhouse"
        else:
            # SIGNAL/default: 白底黑框
            color = "#ffffff"
            font_color = "#000000"
            penwidth = 1
            shape = "box"

        lines.append(
            f'  "{safe_id}" [label="{label}\\n({kind or "SIGNAL"})" '
            f'shape={shape} style="filled,rounded" '
            f'fillcolor="{color}" fontcolor="{font_color}" '
            f'fontsize=11 fontname="Helvetica" penwidth={penwidth}];'
        )

    lines.append("")

    # 边
    for node_id in sorted(target_set):
        safe_id = _sanitize_trace_dot_id(node_id)
        if direction == "fanin":
            # driver -> signal
            lines.append(
                f'  "{safe_id}" -> "{safe_signal}" '
                f'[label="+1 cycle" color="#3366cc" penwidth=1.5 arrowhead=normal];'
            )
        else:
            # signal -> load
            lines.append(
                f'  "{safe_signal}" -> "{safe_id}" '
                f'[label="+1 cycle" color="#3366cc" penwidth=1.5 arrowhead=normal];'
            )

    lines.append("}")
    return "\n".join(lines)


def _collect_signals(
    signal: str | None,
    batch_file: str | None,
    batch: str | None,
) -> list[str]:
    """[B1 2026-07-03] Collect signals from positional + --batch-file + --batch.

    Priority: dedup, preserves first occurrence order.
    Comment lines (#) and empty lines in batch_file are skipped.
    Returns: list of unique signals (at least 1 if any source provided).

    Raises:
        ValueError: batch_file not found, or no signals collected from any source.
    """
    signals: list[str] = []
    if signal:
        signals.append(signal)
    if batch_file:
        try:
            with open(batch_file) as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    signals.append(s)
        except FileNotFoundError as e:
            raise ValueError(f"batch file not found: {batch_file}") from e
    if batch:
        for s in batch.split(","):
            s = s.strip()
            if s:
                signals.append(s)
    # dedup, preserve order
    seen: set[str] = set()
    deduped = [s for s in signals if not (s in seen or seen.add(s))]
    if not deduped:
        raise ValueError(
            "No signals: provide SIGNAL, --batch-file PATH, or --batch 'sig1,sig2'"
        )
    return deduped


_BIT_SUFFIX_RE = re.compile(r"\[\d+\]$")
_CONST_WIDTH_RE = re.compile(r"^-?(\d+)'[sS]?[bodhBODH][0-9a-fA-F_]+$")


_DYNAMIC_INDEX_RE = re.compile(r"\[[^\]]*[A-Za-z_?][^\]]*\]$")


def node_is_runtime_system_call(node) -> bool:
    """[iter_322 / PLAN P26.2] 运行期系统调用结果节点（$random 等）。"""
    return bool((getattr(node, "extra", None) or {}).get("runtime_system_call"))


def node_is_function_call(node) -> bool:
    """[iter_313 / PLAN P18.2] 函数调用结果节点（图级标记）。"""
    return bool((getattr(node, "extra", None) or {}).get("function_call"))


def node_is_dynamic(node) -> bool:
    """[iter_310 / PLAN P16] 节点是否动态索引派生（图级传播标记或动态 id）。"""
    if node is None:
        return False
    if (getattr(node, "extra", None) or {}).get("dynamic"):
        return True
    return is_dynamic_index(getattr(node, "id", "") or "")


def is_dynamic_index(node_id: str) -> bool:
    """[iter_308 / PLAN P14.1] 动态索引（`mem[i]` / `bus[?:?]`）→ 运行期决定。"""
    return bool(_DYNAMIC_INDEX_RE.search(node_id or ""))


def has_dynamic_index(graph, node_id: str | None, incoming: bool = True) -> bool:
    """[iter_308 / PLAN P14.1] 查询涉及的边/节点里是否有动态索引。

    动态 memory 读的图表示是 `mem --(expr="mem[i]")--> y`（目标节点仍是数组），
    所以只看返回节点 id 不够，要扫查询根的直接入射/出射边的 expression。
    """
    if graph is None or node_id is None:
        return False
    node = graph.get_node(node_id)
    if node_is_dynamic(node):
        return True
    neighbors = (graph.predecessors(node_id) if incoming
                 else graph.successors(node_id))
    for other in neighbors:
        edge = (graph.get_edge(other, node_id) if incoming
                else graph.get_edge(node_id, other))
        if edge is None:
            continue
        if _DYNAMIC_INDEX_RE.search(getattr(edge, "expression", "") or ""):
            return True
    return False


def node_precision(node) -> str:
    """[iter_303 / PLAN P13.2] 单个结果节点的粒度: bit / bus / constant。

    - `1'b0/1'b1`：位常量
    - `N'...`（N>1）：常量总线（未分解）
    - id 带 `[k]` 或宽度 1：位
    - 其余：总线/切片/成员聚合
    """
    nid = getattr(node, "id", "") or ""
    if node_is_function_call(node) or node_is_runtime_system_call(node) or is_dynamic_index(nid):
        return "unknown"
    if re.match(r"^1'b[01]$", nid):
        return "bit"
    m = _CONST_WIDTH_RE.match(nid)
    if m:
        return "bit" if int(m.group(1)) == 1 else "constant"
    width = 0
    wt = getattr(node, "width", None)
    if isinstance(wt, (tuple, list)) and len(wt) >= 2:
        try:
            width = max(0, int(wt[0]) - int(wt[1]) + 1)
        except (TypeError, ValueError):
            width = 0
    if _BIT_SUFFIX_RE.search(nid) or width == 1:
        return "bit"
    return "bus"


def query_precision(signal: str, items: list[dict]) -> tuple[str, bool]:
    """[iter_303 / PLAN P13.2] 本次查询的粒度结论 + 是否粗粒度回退。

    返回 `(precision, coarse_fallback)`：
      - 非位查询（总线/切片）→ `("bus", False)`（总线粒度是查询本身的粒度）
      - 位查询空结果 → `("unknown", False)`
      - 位查询且结果全是位 → `("bit", False)`
      - 位查询但混入总线/常量总线 → `("bus", True)`（回落/混合，agent 应降级解读）
    """
    bit_query = bool(_BIT_SUFFIX_RE.search((signal or "").strip()))
    if not bit_query:
        return "bus", False
    if not items:
        return "unknown", False
    precs = {it.get("precision", "bus") for it in items}
    if precs <= {"bit"}:
        return "bit", False
    return "bus", True


def resolve_node_id(graph, signal_id: str) -> str | None:
    """[iter_307 / PLAN P13.6] 驱动统计用节点 id。

    位查询优先用**父总线**统计（多驱动冲突是总线级事实；位节点可能只建了一部分边）；
    unpacked array 元素节点例外（它本身是完整元素）。
    """
    if graph is None:
        return None
    node = graph.get_node(signal_id)
    if node is not None:
        if is_dynamic_index(signal_id):
            return signal_id  # 动态索引节点自身就是"未知"来源，不再回退父数组
        parent = getattr(node, "parent", None)
        if (parent in graph and not (node.extra or {}).get("array_element")):
            w = getattr(node, "width", None)
            width = 0
            if isinstance(w, (tuple, list)) and len(w) >= 2:
                try:
                    width = int(w[0]) - int(w[1]) + 1
                except (TypeError, ValueError):
                    width = 0
            if width == 1:
                return parent
        if not (node.extra or {}).get("array_element") and "[" in signal_id:
            base = signal_id.rsplit("[", 1)[0]
            if base in graph:
                return base
        return signal_id
    if "[" in signal_id:
        base = signal_id.rsplit("[", 1)[0]
        if base in graph:
            return base
    return None


def driver_stats(graph, node_id: str | None) -> tuple[int, bool, bool]:
    """[iter_307 / PLAN P13.6] 直接驱动统计。

    返回 `(driver_count, multi_driver, conditional_drivers)`：
      - driver_count: 直接 DRIVER 边的**不同源**数量（含条件分支）
      - multi_driver: 有 >=2 个**无条件**直接源（潜在冲突；条件 mux 不算）
      - conditional_drivers: 存在带条件的直接驱动（ternary/case/if）
    """
    if graph is None or node_id is None or node_id not in graph:
        return 0, False, False
    srcs = set()
    unconditional = set()
    conditional = False
    for src, dst in graph.edges():
        if dst != node_id:
            continue
        for e in graph.get_edges(src, dst):
            if getattr(e.kind, "name", "") != "DRIVER":
                continue
            srcs.add(src)
            if getattr(e, "condition", ""):
                conditional = True
            else:
                unconditional.add(src)
    return len(srcs), len(unconditional) >= 2, conditional


def detect_cycles(graph, root: str | None, reverse: bool,
                  max_nodes: int = 20000, max_edges: int = 100000) -> bool | None:
    """[iter_321 / PLAN P26.1] 从查询根沿遍历方向检测可达环。

    reverse=True (fanin): 沿 predecessors；False (fanout): successors。
    capped 三态：True=有环；False=无环；None=触顶无法判定（不静默当 false）。
    """
    if graph is None or root is None or root not in graph:
        return False
    color: dict[str, int] = {root: 1}
    neighbor = (lambda n: graph.predecessors(n) if reverse else graph.successors(n))
    stack: list[tuple[str, object]] = [(root, iter(list(neighbor(root))))]
    nodes = 1
    edges = 0
    while stack:
        cur, it = stack[-1]
        advanced = False
        for nxt in it:
            edges += 1
            if edges > max_edges:
                return None
            state = color.get(nxt, 0)
            if state == 0:
                nodes += 1
                if nodes > max_nodes:
                    return None
                color[nxt] = 1
                stack.append((nxt, iter(list(neighbor(nxt)))))
                advanced = True
                break
            if state == 1:
                return True
        if not advanced:
            color[cur] = 2
            stack.pop()
    return False


def truncated_by_depth(graph, items: list[dict], depth: int | None,
                       reverse: bool) -> bool:
    """[iter_321 / PLAN P26.1] depth 边界节点是否仍有未展开的边。"""
    if graph is None or depth is None:
        return False
    neighbor = (lambda n: graph.predecessors(n) if reverse else graph.successors(n))
    for item in items:
        nid = item.get("id")
        if not nid or item.get("distance") != depth or nid not in graph:
            continue
        if next(iter(neighbor(nid)), None) is not None:
            return True
    return False


class SignalResolutionError(ValueError):
    """[iter_329 / PLAN P33.1] 信号无法唯一解析到图节点。"""

    def __init__(self, message: str, *, error_code: str, resolution: str,
                 candidates: list[str] | None = None,
                 suggestions: list[str] | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.resolution = resolution
        self.candidates = candidates or []
        self.suggestions = suggestions or []


def resolve_signal(graph, raw: str, max_candidates: int = 20) -> dict:
    """[iter_329 / PLAN P33.1] 把用户信号解析到图节点，返回可解释结果。

    status:
      - exact: 完整 id 命中
      - relative: 唯一后缀命中（u.a / a）
      - bit_base_fallback: 位/切片节点不存在，但父总线存在（保留现有位查询回退）
      - ambiguous: 多个候选
      - not_found: 无候选
    """
    if graph is None:
        return {"ok": False, "status": "not_found", "resolved": None,
                "candidates": [], "suggestions": [], "bit_fallback": False}
    nodes = set(graph.nodes())
    if raw in nodes:
        return {"ok": True, "status": "exact", "resolved": raw,
                "candidates": [], "suggestions": [], "bit_fallback": False}

    import re as _re
    m = _re.match(r"^(.*)(\[[^\]]+\])$", raw or "")
    if m:
        base_raw, suffix = m.group(1), m.group(2)
        base = resolve_signal(graph, base_raw, max_candidates=max_candidates)
        if not base["ok"]:
            if base["status"] == "ambiguous":
                return base
        elif base["resolved"]:
            candidate = base["resolved"] + suffix
            if candidate in nodes:
                return {"ok": True, "status": "relative", "resolved": candidate,
                        "candidates": [], "suggestions": [], "bit_fallback": False}
            return {"ok": True, "status": "bit_base_fallback", "resolved": candidate,
                    "base": base["resolved"], "candidates": [], "suggestions": [],
                    "bit_fallback": True}

    # 唯一后缀匹配：u.a -> top.u.a；a -> 唯一 top.a
    suffix = "." + raw
    matches = sorted(n for n in nodes if n.endswith(suffix))
    if len(matches) == 1:
        return {"ok": True, "status": "relative", "resolved": matches[0],
                "candidates": [], "suggestions": [], "bit_fallback": False}
    if len(matches) > 1:
        return {"ok": False, "status": "ambiguous", "resolved": None,
                "candidates": matches[:max_candidates], "suggestions": [],
                "bit_fallback": False, "match_count": len(matches)}

    leaf = (raw or "").split(".")[-1].split("[")[0]
    suggestions = sorted({n for n in nodes if leaf and leaf.lower() in n.lower()})[:10]
    return {"ok": False, "status": "not_found", "resolved": None,
            "candidates": [], "suggestions": suggestions, "bit_fallback": False}


def resolution_error_message(raw: str, result: dict) -> str:
    status = result.get("status")
    if status == "ambiguous":
        cands = ", ".join(result.get("candidates", [])[:8])
        total = result.get("match_count", len(result.get("candidates", [])))
        return (f"signal {raw!r} is ambiguous ({total} matches); "
                f"use a longer path or one of: {cands}")
    sugg = ", ".join(result.get("suggestions", [])[:8])
    msg = f"signal {raw!r} not found in graph"
    if sugg:
        msg += f"; candidates: {sugg}"
    return msg


def resolution_fields(result: dict) -> dict:
    """把 resolve_signal 结果转成 JSON 字段（trace signal 通用）。"""
    return {
        "resolved_signal": result.get("resolved"),
        "resolution": result.get("status"),
        "candidates": result.get("candidates", []),
        "suggestions": result.get("suggestions", []),
    }


def _edge_condition_text(edge) -> str:
    """[iter_318 / PLAN P22.1] 单条边的条件文本（优先 condition，退化 chain/effective）。"""
    chain = getattr(edge, "condition_chain", None) or []
    parts = [c.strip() for c in chain if c and c.strip()]
    if len(parts) > 1:
        # [iter_319] 嵌套 if/ternary: condition 只存最外层，chain 才是完整条件
        return " && ".join(parts)
    text = (getattr(edge, "condition", "") or "").strip()
    if text:
        return text
    if parts:
        return parts[0]
    return (getattr(edge, "effective_condition", "") or "").strip()


# [iter_320 / PLAN P24.1] 多路径枚举上限：防止组合爆炸
MAX_PATHS_PER_NODE = 8
MAX_PATH_DEPTH = 20
MAX_PATH_EXPANSIONS = 5000


def _condition_edges(edge) -> bool:
    return getattr(edge.kind, "name", "") in ("DRIVER", "CONNECTION")


def _build_condition_adjacency(graph, reverse: bool) -> dict[str, list[tuple[str, object]]]:
    """条件路径邻接（node→root DFS）。

    fanin (reverse=True): 沿数据流 node→root → 正向邻接 u→v。
    fanout: 路径 root→node，从 node 反向走到 root → 反向邻接 v→(u,edge)。
    """
    adj: dict[str, list[tuple[str, object]]] = {}
    for src, dst in graph.edges():
        for edge in graph.get_edges(src, dst):
            if not _condition_edges(edge):
                continue
            if reverse:
                adj.setdefault(src, []).append((dst, edge))
            else:
                adj.setdefault(dst, []).append((src, edge))
    return adj


def _find_paths(node: str, root: str, back_adj: dict) -> tuple[list[list], bool]:
    """枚举 node→root 的简单路径（最多 MAX_PATHS_PER_NODE 条）。

    返回 (paths, truncated)。truncated=True 表示命中路径数/深度/展开预算上限。
    """
    paths: list[list] = []
    truncated = False
    expansions = 0
    visited = {node}
    edges: list = []

    def dfs(cur: str) -> None:
        nonlocal truncated, expansions
        if len(paths) >= MAX_PATHS_PER_NODE or expansions >= MAX_PATH_EXPANSIONS:
            truncated = True
            return
        if cur == root:
            paths.append(list(edges))
            return
        if len(edges) >= MAX_PATH_DEPTH:
            truncated = True
            return
        for parent, edge in back_adj.get(cur, ()):  # type: ignore[arg-type]
            if parent in visited:
                continue
            expansions += 1
            if expansions > MAX_PATH_EXPANSIONS:
                truncated = True
                return
            visited.add(parent)
            edges.append(edge)
            dfs(parent)
            edges.pop()
            visited.remove(parent)
            if len(paths) >= MAX_PATHS_PER_NODE:
                truncated = True
                return

    dfs(node)
    return paths, truncated


def _path_condition(path: list, reverse: bool) -> tuple[str, list[str]]:
    """一条路径的条件：path 是 node→root 的边序列；fanout 反向成 root→node。"""
    ordered = path if reverse else list(reversed(path))
    parts = [c for c in (_edge_condition_text(e) for e in ordered) if c]
    combined = " && ".join(f"({c})" if len(parts) > 1 else c for c in parts)
    return combined, parts


def _or_conditions(conds: list[str]) -> str:
    """条件 OR；为空表示无条件。调用方需先处理空条件路径。"""
    if not conds:
        return ""
    if len(conds) == 1:
        return conds[0]
    return " || ".join(f"({c})" for c in conds)


def _direct_paths(graph, nid: str, eps: list[str], reverse: bool) -> list[dict]:
    """直接边条件（depth=1 / 路径枚举失败时的回退）。"""
    paths: list[dict] = []
    if nid not in graph:
        return paths
    for ep in eps:
        if ep not in graph:
            continue
        src, dst = (nid, ep) if reverse else (ep, nid)
        for edge in graph.get_edges(src, dst):
            if getattr(edge.kind, "name", "") == "BIT_SELECT":
                continue
            text = _edge_condition_text(edge)
            paths.append({"condition": text, "path": [text] if text else []})
    return paths


def _apply_paths(item: dict, path_infos: list[dict], truncated: bool) -> list[str]:
    """把路径结果写进 item；返回其中非空条件（供 signal 级汇总）。"""
    conds = [x["condition"] for x in path_infos if x["condition"]]
    uncond = any(not x["condition"] for x in path_infos)
    item["condition_paths"] = path_infos
    item["conditions"] = conds
    item["condition_path"] = path_infos[0]["path"] if path_infos else []
    item["condition_unconditional"] = uncond
    item["condition"] = "" if uncond else _or_conditions(conds)
    item["condition_truncated"] = truncated
    return conds


def attach_edge_conditions(graph, items: list[dict], endpoints: list[str | None],
                           reverse: bool, depth: int | None = None) -> list[str]:
    """给 fanin/fanout 结果补条件（直接边 + 多路径 OR）。

    每节点输出：
      - condition: 直接边 OR / 多路径 OR（`(p1) || (p2)`）；无条件路径 -> ""
      - conditions: 保留原本多条件（直接边原列表 / 每路径组合）
      - condition_paths: [{condition, path:[原始条件...]}, ...]
      - condition_path: 第一条路径的原始条件（兼容 P23）
      - condition_unconditional: 是否存在无条件路径
      - condition_truncated: 路径枚举是否触顶
    depth=1 只取直接边；depth=None/递归才枚举多路径。
    """
    if graph is None:
        return []
    # sig 与 _root 可能是同一节点：去重，避免同一条边被算两次
    eps = list(dict.fromkeys(e for e in endpoints if e))
    root = next((e for e in eps if e in graph), None)
    all_conditions: list[str] = []
    adj = None
    if depth != 1:
        adj = _build_condition_adjacency(graph, reverse)

    for item in items:
        nid = item.get("id")
        path_infos: list[dict] = []
        truncated = False
        if nid and nid != root and root and adj is not None:
            paths, truncated = _find_paths(nid, root, adj)
            for path in paths:
                text, raw = _path_condition(path, reverse)
                path_infos.append({"condition": text, "path": raw})
        if not path_infos:
            # depth=1，或位提升等图上无完整路径：回退直接边（不猜测路径）
            path_infos = _direct_paths(graph, nid, eps, reverse)
            truncated = False
        for c in _apply_paths(item, path_infos, truncated):
            if c not in all_conditions:
                all_conditions.append(c)

    return all_conditions


def _node_to_dict(node) -> dict:
    """[B2 2026-07-03] Convert TraceNode to dict with module + width info.

    暴露 module (for --module filter) + width_msb/width_lsb/width (for --width-min/max).
    原有 id/kind/distance 字段保留 (向后兼容).
    """
    width_tuple = getattr(node, "width", (0, 0))
    if isinstance(width_tuple, (tuple, list)) and len(width_tuple) >= 2:
        width_msb = width_tuple[0]
        width_lsb = width_tuple[1]
        width = max(0, width_msb - width_lsb + 1)
    else:
        width_msb = width_lsb = width = 0
    return {
        "id": node.id,
        "kind": getattr(node, "kind", "UNKNOWN").name if hasattr(node, "kind") else "UNKNOWN",
        "module": getattr(node, "module", ""),
        "width_msb": width_msb,
        "width_lsb": width_lsb,
        "width": width,
        "distance": getattr(node, "distance", 1) if hasattr(node, "distance") else 1,
        # [iter_303 / PLAN P13.2] 结果粒度标记（bit/bus/constant）
        "precision": node_precision(node),
        # [iter_304 / PLAN P13.3] 图元数据（signedness / 位段归属）
        "is_signed": getattr(node, "is_signed", None),
        "parent": getattr(node, "parent", None),
        "bit_range": getattr(node, "bit_range", None),
        # [iter_308 / PLAN P14.1] 动态索引（运行期决定）
        "dynamic_index": node_is_dynamic(node),
        # [iter_313 / PLAN P18.2] 函数调用结果（未 inline，仅诚实标记）
        "function_call": node_is_function_call(node),
        "runtime_system_call": node_is_runtime_system_call(node),
        # [iter_318 / PLAN P22.1] 由 attach_edge_conditions 填（直接边条件）
        "condition": "",
        "conditions": [],
        "condition_path": [],
        "condition_paths": [],
        "condition_unconditional": False,
        "condition_truncated": False,
    }


def attach_distances(graph, root: str, items: list[dict], reverse: bool = False) -> None:
    """[iter_278] 给 loads/drivers 结果填**真实跳数** (就地改 `distance` 字段)。

    历史: `_node_to_dict` 一直写 `distance=1`（KNOWN_LIMITATIONS §3.3-2），因为
    TraceNode 上没有深度信息，而**不能**在共享节点上写属性（同一图会被多次查询）。

    这里在响应组装阶段做一次 BFS（fanout 沿 successors / fanin 沿 predecessors），
    按最短跳数填 distance。只在内存 dict 上写，不碰图节点。
    """
    if graph is None or not items:
        return
    # [iter_303 / P13.2] 位查询可能查"图中不存在的位"（由 fanin 回退父总线回答）；
    # root 不在图里时 BFS 会抛 networkx 错误，这里保持 distance 默认值即可。
    if root not in graph:
        return
    from collections import deque

    adj = (lambda n: list(graph.predecessors(n))) if reverse else (lambda n: list(graph.successors(n)))
    depth = {root: 0}
    q = deque([root])
    remaining = {it["id"] for it in items}
    while q and remaining:
        cur = q.popleft()
        for nxt in adj(cur):
            if nxt in depth:
                continue
            depth[nxt] = depth[cur] + 1
            if nxt in remaining:
                remaining.discard(nxt)
            q.append(nxt)
    for it in items:
        it["distance"] = depth.get(it["id"], it.get("distance", 1))


def _apply_filters(
    items: list[dict],
    type_filter: str | None = None,
    module_filter: str | None = None,
    width_min: int | None = None,
    width_max: int | None = None,
    exclude: str | None = None,
) -> list[dict]:
    """[B2 2026-07-03] Apply 5 filters to driver/load dicts.

    Uses fnmatch (NOT regex - project discipline: no regex in src/trace/core/).
    Returns filtered list (preserves order). Empty list if all filtered out.
    """
    import fnmatch
    out = items
    if type_filter:
        types = {t.strip().upper() for t in type_filter.split(",") if t.strip()}
        out = [d for d in out if d.get("kind", "").upper() in types]
    if module_filter:
        # [Phase 8 / Fix F 2026-7-14] Include CONST literal nodes regardless of module
        # Reason: literal drivers like '0', '1' from `q <= 0` are conceptually
        # in the target module (they're the RHS values assigned in that module's
        # always block), but their node.module is empty. They're useful info for
        # trace_fanin queries (e.g., picorv32.trap drivers = [0, 1]).
        out = [
            d for d in out
            if fnmatch.fnmatch(d.get("module", ""), module_filter)
            or d.get("kind") == "CONST"
        ]
    if width_min is not None:
        out = [d for d in out if d.get("width", 0) >= width_min]
    if width_max is not None:
        out = [d for d in out if d.get("width", 0) <= width_max]
    if exclude:
        out = [d for d in out if not fnmatch.fnmatch(d.get("id", ""), exclude)]
    return out


def _load_tracer_from_snapshot(
    tag: str,
    log_level: str = "ERROR",
        preprocess_macros: bool = True,
) -> "UnifiedTracer":
    """[B4 2026-07-03] Build UnifiedTracer from saved snapshot, skip SV parse.

    用途: 同一 graph 跑多次 trace 命令, parse 1 次 (snapshot save) + trace N 次.
    加速: 大项目 (50+ SV) 跑 4 子命令各 1 次 = 4× parse, 现在 1×.

    [A2 2026-07-04] Use SignalGraph.from_dict() instead of manual add_trace_node/edge
    (1 line vs 30 lines, prevents field drift).

    Returns: UnifiedTracer with _graph + _signal_tracer pre-populated from snapshot JSON.

    Raises:
        ValueError: snapshot tag not found.
    """
    from trace.core.graph.models import SignalGraph
    from trace.core.query.signal import SignalTracer
    from trace.core.snapshot_manager import SnapshotManager

    manager = SnapshotManager()
    snap = manager.load(tag)
    if snap is None:
        raise ValueError(f"Snapshot not found: {tag}")

    # [A2 2026-07-04] Use from_dict (handles all node/edge fields)
    # Snapshot extra fields (version, files, elaboration_errors, ...) are ignored
    # by from_dict, which is what we want.
    graph = SignalGraph.from_dict(snap)

    # Stub tracer: pre-populate _graph + _signal_tracer
    tracer = UnifiedTracer(
        sources={}, log_level=log_level, preprocess_macros=preprocess_macros,
    )
    tracer._graph = graph
    tracer._signal_tracer = SignalTracer(graph, mig=None)
    return tracer
