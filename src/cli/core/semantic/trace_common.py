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
    }


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

    # [A2 2026-07-04] Use from_dict (handles all node/edge fields + port_to_internal)
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
