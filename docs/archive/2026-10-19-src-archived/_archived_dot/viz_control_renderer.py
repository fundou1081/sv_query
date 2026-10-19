"""
viz_control_renderer.py — Control 图 DOT 渲染器 (V7.0)

纯渲染层 — 从 ControlTree 读取数据，输出 DOT 字符串。
不包含任何分组/构建逻辑。

设计:
  - render_control_dot() 是主入口
  - render_mux_node / render_branch / render_simple / render_target 是稳定基本单元
  - 所有样式集中在 StyleConfig
"""

from __future__ import annotations
from dataclasses import dataclass

from .control_tree import ControlTree, MuxBranch, MuxNode, SimpleCondition, build_control_tree
from .viz_data_models import VizData, VizEdge, VizNode


# ═══════════════════════════════════════════════════════
# 样式配置
# ═══════════════════════════════════════════════════════

@dataclass
class StyleConfig:
    """Control 图所有可调样式。微调只改这里。"""
    # 布局
    rankdir: str = "LR"
    nodesep: float = 0.5
    ranksep: float = 1.2

    # 默认字体
    font_name: str = "Helvetica"
    label_font: str = "Courier"
    font_size: int = 10

    # 节点默认
    node_shape: str = 'box style="rounded,filled"'

    # ── Mux 节点样式 ──
    mux_shape: str = "diamond"
    mux_fontsize: int = 11
    mux_penwidth: int = 2
    mux_outer_fill: str = "#e3f2fd"
    mux_outer_border: str = "#1565c0"
    mux_inner_fill: str = "#bbdefb"
    mux_inner_border: str = "#0d47a1"

    # ── Mux 分支边 ──
    branch_to_child_color: str = "#1565c0"
    branch_to_child_penwidth: float = 1.5
    branch_to_child_fontsize: int = 9

    # ── Mux 叶边 (→ 目标) ──
    branch_to_target_color: str = "#666666"
    branch_to_target_fontsize: int = 7

    # ── 简单条件 ──
    simple_shape: str = "diamond"
    simple_fill: str = "#fff8e1"
    simple_border: str = "#f57f17"
    simple_fontsize: int = 9
    simple_to_target_color: str = "#888888"
    simple_to_target_fontsize: int = 7

    # ── 目标节点 ──
    target_shape: str = "box"
    target_fill: str = "#eeeeee"
    target_border: str = "#999999"
    target_fontsize: int = 11
    target_penwidth: int = 2


# ═══════════════════════════════════════════════════════
# DOT helpers
# ═══════════════════════════════════════════════════════

def _did(*parts: str) -> str:
    s = "_".join(str(p) for p in parts)
    r = []
    for ch in s:
        if ch.isalnum() or ch == "_":
            r.append(ch)
        else:
            r.append(f"_{ord(ch)}_")
    return "n" + "".join(r[:60])


def _esc(s: str) -> str:
    return s.replace('"', '\\"').replace('\n', '\\n')


# ═══════════════════════════════════════════════════════
# 渲染函数 (稳定基本单元)
# ═══════════════════════════════════════════════════════

def _render_mux_node(mux: MuxNode, s: StyleConfig) -> str:
    """渲染单个 mux 菱形节点。"""
    fc = s.mux_outer_fill if mux.depth == 0 else s.mux_inner_fill
    oc = s.mux_outer_border if mux.depth == 0 else s.mux_inner_border
    return (
        f'  {_did(mux.id)} [label="{_esc(mux.label)}" shape={s.mux_shape} '
        f'fillcolor="{fc}" color="{oc}" '
        f'fontsize={s.mux_fontsize} penwidth={s.mux_penwidth}];'
    )


def _render_branch(parent_id: str, branch: MuxBranch, s: StyleConfig) -> list[str]:
    """渲染一个 mux 分支 → 子节点或目标。"""
    lines = []
    if branch.child:
        lines.append(
            f'  {_did(parent_id)} -> {_did(branch.child.id)} '
            f'[label="{_esc(branch.condition)}" '
            f'fontsize={s.branch_to_child_fontsize} '
            f'color="{s.branch_to_child_color}" '
            f'penwidth={s.branch_to_child_penwidth} arrowhead=open];'
        )
    else:
        label = f"{_esc(branch.condition)} → {_esc(branch.source_signal)}"
        lines.append(
            f'  {_did(parent_id)} -> {_did(branch.target_node)} '
            f'[label="{label}" '
            f'fontsize={s.branch_to_target_fontsize} '
            f'color="{s.branch_to_target_color}"];'
        )
    return lines


def _render_simple_cond(sc: SimpleCondition, s: StyleConfig) -> list[str]:
    """渲染单边简单条件: 父 mux → 条件菱形 → 目标。"""
    lines = []
    cid = _did(sc.id)
    dn = _did(sc.target_node)

    lines.append(
        f'  {cid} [label="{_esc(sc.condition)}" shape={s.simple_shape} '
        f'fillcolor="{s.simple_fill}" color="{s.simple_border}" '
        f'fontsize={s.simple_fontsize}];'
    )

    if sc.parent_mux_id:
        lines.append(
            f'  {_did(sc.parent_mux_id)} -> {cid} '
            f'[label="{_esc(sc.condition)}" fontsize=8 color="{s.simple_border}"];'
        )

    lines.append(
        f'  {cid} -> {dn} [label="{_esc(sc.source_signal)}" '
        f'fontsize={s.simple_to_target_fontsize} color="{s.simple_to_target_color}"];'
    )
    return lines


def _render_target(dst: str, label: str, s: StyleConfig) -> str:
    """渲染目标信号节点。"""
    dn = _did(dst)
    return (
        f'  {dn} [label="{_esc(label)}" shape={s.target_shape} '
        f'fillcolor="{s.target_fill}" color="{s.target_border}" '
        f'fontsize={s.target_fontsize} penwidth={s.target_penwidth}];'
    )


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def render_control_dot(viz: VizData, config: dict | None = None) -> str:
    """从 VizData 渲染 Control 图 DOT 字符串。

    1. 从 VizData 提取所有带 condition_chain 的 VizEdge
    2. 按 dst 分组，每组构建一个 ControlTree
    3. 用稳定的渲染单元输出 DOT
    """
    cfg = config or {}
    title = cfg.get("title", "Control Flow")
    s = StyleConfig(
        rankdir=cfg.get("layout", "LR"),
        nodesep=cfg.get("nodesep", 0.5),
        ranksep=cfg.get("ranksep", 1.2),
    )

    out = [
        "digraph control {",
        f'  label="{title}"; labelloc=t; rankdir={s.rankdir};',
        f"  splines=polyline; nodesep={s.nodesep}; ranksep={s.ranksep}; bgcolor=white;",
        f'  node [shape={s.node_shape} fontname="{s.font_name}" fontsize={s.font_size}];',
        f'  edge [fontname="{s.label_font}" fontsize=8];',
        "",
    ]
    emit = out.append

    # ── 收集带条件边 ──
    from collections import defaultdict
    by_dst: dict[str, list[VizEdge]] = defaultdict(list)
    node_map = {n.id: n for n in viz.nodes}

    for ed in viz.edges:
        ch = getattr(ed, "condition_chain", None) or []
        if not ch or ed.kind in ("CLOCK", "RESET"):
            continue
        by_dst[ed.dst].append(ed)

    if not by_dst:
        emit("  // (none)")
        emit("}")
        return "\n".join(out)

    # ── 为每个 target 构建 ControlTree 并渲染 ──
    for dst, edges in by_dst.items():
        tree = build_control_tree(dst, edges, node_map)

        # 1. 渲染所有 mux 节点
        for mux in tree.sorted_muxes():
            emit(_render_mux_node(mux, s))

        # 2. 渲染所有 mux 分支
        for mux in tree.sorted_muxes():
            for branch in mux.branches:
                for line in _render_branch(mux.id, branch, s):
                    emit(line)

        # 3. 渲染简单条件
        for sc in tree.simples:
            for line in _render_simple_cond(sc, s):
                emit(line)

        # 4. 渲染目标节点
        emit(_render_target(dst, tree.target_label, s))

    emit("}")
    return "\n".join(out)
