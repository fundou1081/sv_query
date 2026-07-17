"""Shared helpers for dataflow_viz + pipeline_viz (DOT generation).

[P1-5 2026-06-13] 提取 _sanitize_dot_id / classify_graph 包装 / legend 块
到共享模块, 消除 ~30 行重复。

Public API:
    sanitize_dot_id(node_id)  - safe DOT node identifier
    safe_classify(graph)      - classify_graph with try/except guard
    node_width(cn)            - compute width in bits from a ClassifiedNode
    STANDARD_DOT_HEADER       - common digraph header lines
    signal_class_color()      - SignalClass -> (fill, border, font)
"""
from __future__ import annotations

from typing import Optional, Tuple

from .signal_classifier import (
    SignalClass,
    SignalClassification,
    classify_graph,
)
from ..models import SignalGraph


def sanitize_dot_id(node_id: str) -> str:
    """[P1-5 2026-06-13] 统一 sanitize: 替换 dataflow_viz + pipeline_viz 两份。

    清理策略:
      1. 过滤 control chars (< 0x20) 和 non-ASCII (> 0x7E)
      2. 移除 DOT 特殊字符 (", {, }, \\)
      3. 空字符串时返回 _node_<hash> 占位
    """
    if not isinstance(node_id, str):
        node_id = str(node_id)
    safe = ''.join(c for c in node_id if 0x20 <= ord(c) < 0x7F)
    safe = safe.replace('"', '').replace('{', '').replace('}', '').replace('\\', '').strip()
    return safe if safe else f"_node_{(hash(node_id) & 0xFFFF):04x}"


def safe_classify(graph: SignalGraph) -> SignalClassification | None:
    """[P1-5] classify_graph + try/except 包装, 返回 None 表示分类失败。

    两处 viz 都用相同的 fallback: 失败时返回 None, 然后生成最简 DOT。
    """
    try:
        return classify_graph(graph)
    except (UnicodeDecodeError, ValueError, TypeError):
        return None


def node_width(cn) -> int:
    """[P1-5] 从 ClassifiedNode 算位宽 (bits), 缺失返 0。"""
    if cn is None or cn.node is None:
        return 0
    w_msb, w_lsb = cn.node.width
    if w_msb < w_lsb:
        return 0
    return abs(w_msb - w_lsb) + 1


# SignalClass → (fillcolor, bordercolor, fontcolor)
SIGNAL_CLASS_COLORS: dict[SignalClass, tuple[str, str, str]] = {
    SignalClass.DATA:    ("#4488cc", "#226699", "white"),
    SignalClass.CONTROL: ("#cc8844", "#996622", "white"),
    SignalClass.CLOCK:   ("#888888", "#666666", "white"),
    SignalClass.RESET:   ("#cc4444", "#992222", "white"),
    SignalClass.UNKNOWN: ("#aaaaaa", "#888888", "black"),
}


def signal_class_color(sc: SignalClass) -> tuple[str, str, str]:
    """[P1-5] 拿 SignalClass 的 DOT 颜色三元组。"""
    return SIGNAL_CLASS_COLORS.get(sc, ("#aaaaaa", "#888888", "black"))


# 公共 DOT 头部 (rankdir / label 在调用方设置)
COMMON_DOT_DEFAULTS = [
    "splines=polyline;",
    "labelloc=t;",
    "fontsize=14;",
]



# ---------------------------------------------------------------------------
# Phase B (2026-07-17) — moved from cli/commands/visualize.py so all viz
# subcommands can share them.
# ---------------------------------------------------------------------------

def escape_dot_label(s: str) -> str:
    """[Phase B] Escape DOT special characters in label.

    DOT inside "..." labels needs: [ ] " < > { } | escaped with backslash.
    Used by chain/auto mode labels where signal IDs can contain any of these.
    """
    s = s.replace("[", "\\[")
    s = s.replace("]", "\\]")
    s = s.replace("\"", "\\\"")
    s = s.replace("<", "\\<")
    s = s.replace(">", "\\>")
    s = s.replace("{", "\\{")
    s = s.replace("}", "\\}")
    s = s.replace("|", "\\|")
    return s


def format_node_label_chain(node_id: str, top: str) -> str:
    """[Phase B] Format a hierarchical signal ID as a multi-line DOT label.

    Strategy:
      - Strip the "<top>." prefix (it is already shown as the graph label).
      - Split on "." and join parts with "\\n." (graphviz newline).
      - 4+ parts keep first 2 + last (with "…" ellipsis in between).
      - All parts DOT-escaped via escape_dot_label().

    Example: 'dot11_tx.ifft64.revstage.i_clk' (top='dot11_tx') →
             'ifft64\\n.revstage\\n.i_clk'
    """
    if node_id.startswith(f"{top}."):
        rest = node_id[len(top) + 1:]
    else:
        rest = node_id
    parts = rest.split(".")
    if len(parts) == 1:
        return escape_dot_label(parts[0])
    if len(parts) == 2:
        return f"{escape_dot_label(parts[0])}\\n.{escape_dot_label(parts[1])}"
    if len(parts) <= 4:
        return "\\n.".join(escape_dot_label(p) for p in parts)
    # 5+: first + second + … + last
    escaped = [escape_dot_label(p) for p in parts]
    return f"{escaped[0]}\\n.{escaped[1]}\\n…\\n.{escaped[-1]}"


def sanitize_dot_id_inner(s: str) -> str:
    """[Phase B] Sanitize signal ID for DOT (chain-friendly variant).

    Replaces characters that graphviz treats as structural (`.`, `[`, `]`, space)
    with underscores. Slightly different from sanitize_dot_id() (which strips
    unsafe chars silently) — this one keeps the original visible shape.
    """
    return s.replace(".", "_").replace("[", "_").replace("]", "_").replace(" ", "_")


def render_with_engine(dot_text: str, output_path: str, engine: str = "dot", fmt: str = "png") -> int:
    """[Phase B] Render DOT text via the named graphviz engine (dot/neato/fdp).

    Writes a temp .dot, then invokes `<engine> -T<fmt> -o <output_path>`.
    Returns the engine's exit code. Raises OSError if the engine binary is not
    on PATH.
    """
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as tmp:
        tmp.write(dot_text)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            [engine, f"-T{fmt}", tmp_path, "-o", output_path],
            capture_output=True,
            text=True,
        )
        return proc.returncode
    finally:
        try:
            import os
            os.unlink(tmp_path)
        except OSError:
            pass
