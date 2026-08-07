"""
control_tree.py — Control 图数据层 (V7.0)

纯数据模型 — 将 condition_chain 列表转换为嵌套 MuxNode 树。
构建逻辑和渲染逻辑完全分离，便于微调和测试。

用法:
    tree = build_control_tree(dst, edges)
    # edges = 属于同一个 dst 的所有带 condition_chain 的 VizEdge
    # tree.muxes = 嵌套 mux 节点列表
    # tree.simples = 单边简单条件列表
"""

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .viz_data_models import VizEdge


# ═══════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════

@dataclass
class MuxBranch:
    """Mux 节点的一个分支。"""
    condition: str           # 分支条件文本 ("sel", "sel_d == 2'd0", "default", ...)
    source_signal: str       # 源信号名 (短名)
    target_node: str         # 目标节点 ID
    child: MuxNode | None = None  # 内层子 mux (嵌套时)


@dataclass
class MuxNode:
    """一个选择/条件决策节点 (if/case/ternary)。

    对应 condition_chain 的一个层级前缀。
    同一 prefix 下 >= 2 条边 → 形成此 mux。
    """
    id: str                  # 唯一标识 (DOT 节点用)
    signal: str              # 决策信号名 ("sel_a", "sel_d", ...)
    depth: int               # 嵌套深度 (0=最外层)
    parent_condition: str    # 父条件文本 (括号里显示的, 如 "sel_d == 2'b0")
    branches: list[MuxBranch] = field(default_factory=list)

    @property
    def label(self) -> str:
        """节点标签文本"""
        if self.parent_condition:
            p = self.parent_condition
            if len(p) > 28:
                p = p[:25] + "..."
            return f"{self.signal}\n[{p}]"
        return self.signal

    @property
    def fill_color(self) -> str:
        return "#e3f2fd" if self.depth == 0 else "#bbdefb"

    @property
    def border_color(self) -> str:
        return "#1565c0" if self.depth == 0 else "#0d47a1"


@dataclass
class SimpleCondition:
    """不在任何 mux 中的单边条件。"""
    id: str
    condition: str           # 条件文本 ("en", "en && valid", ...)
    source_signal: str       # 源信号名
    target_node: str         # 目标节点 ID
    parent_mux_id: str = ""  # 所属父 mux (通过边连接)


@dataclass
class ControlTree:
    """一个目标信号的控制流树。"""
    target: str              # 目标节点 ID (如 "mux_demo.y_deep")
    target_label: str        # 目标标签 (短名 + 位宽)
    muxes: dict[tuple, MuxNode] = field(default_factory=dict)  # prefix → MuxNode
    simples: list[SimpleCondition] = field(default_factory=list)

    def sorted_muxes(self) -> list[MuxNode]:
        """按深度排序的 mux 列表 (外层→内层)"""
        return sorted(self.muxes.values(), key=lambda m: (m.depth, m.id))


# ═══════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════

def _short(s: str) -> str:
    return s.split(".")[-1] if "." in s else s


def _extract_signal(cond: str) -> str:
    """从条件字符串提取决策信号名"""
    if "==" in cond:
        return cond.split("==")[0].strip()
    if cond.startswith("!"):
        return cond[1:].strip()
    return cond


# ═══════════════════════════════════════════════════════
# 构建函数
# ═══════════════════════════════════════════════════════

def build_control_tree(
    dst: str,
    edges: list,
    node_map: dict | None = None,
) -> ControlTree:
    """从同一个 dst 的所有 VizEdge 构建 ControlTree。

    Args:
        dst: 目标信号 ID (如 "mux_demo.y_deep")
        edges: 属于这个 dst 的 VizEdge 列表 (必须有 condition_chain)
        node_map: VizNode 映射 (可选, 用于获取位宽信息)

    Returns:
        ControlTree 实例
    """
    from .viz_data_models import VizEdge, VizNode

    # ── 目标标签 ──
    label = _short(dst)
    if node_map:
        n = node_map.get(dst)
        if n and n.width and n.width != (0, 0):
            msb, lsb = n.width
            w = f"[{msb}:{lsb}]" if msb != lsb else f"[{msb}]"
            label = f"{_short(dst)}\n{w}"

    # ── 按 (chain[:-1]) 前缀分组 ──
    groups: dict[tuple, list] = defaultdict(list)
    for ed in edges:
        ch = ed.condition_chain
        pre = tuple(ch[:-1]) if len(ch) > 1 else ()
        groups[pre].append(ed)

    prefixes = sorted(groups.keys(), key=lambda p: (len(p), str(p)))
    max_d = max((len(p) for p in prefixes), default=0)

    muxes: dict[tuple, MuxNode] = {}

    # ── 建外层 mux ──
    p0 = tuple()
    p0g = groups.get(p0, [])
    need_outer = len(p0g) >= 2 or max_d >= 1
    if need_outer:
        outer_sig = ""
        if p0g:
            outer_sig = _extract_signal(p0g[0].condition_chain[-1])
        elif max_d >= 1:
            for p in prefixes:
                if p and len(groups[p]) >= 2:
                    outer_sig = _extract_signal(groups[p][0].condition_chain[0])
                    break
        muxes[p0] = MuxNode(
            id=f"mux_L0_{_short(dst)}",
            signal=outer_sig,
            depth=0,
            parent_condition="",
        )

    # ── 建内层 mux ──
    for p in prefixes:
        if not p:
            continue
        g = groups[p]
        if len(g) >= 2:
            sel = _extract_signal(g[0].condition_chain[-1])
            muxes[p] = MuxNode(
                id=f"mux_L{len(p)}_{_short(dst)}_{_short(sel)}",
                signal=sel,
                depth=len(p),
                parent_condition=" && ".join(p),
            )

    # ── 填充分支 ──
    for pre, mn in muxes.items():
        d = mn.depth
        g = groups.get(pre, [])

        for ed in g:
            full = ed.condition_chain
            bcond = full[-1]
            src = _short(ed.src)

            child = None
            if len(full) > d + 1:
                sub_key = tuple(full[:d + 1])
                child = muxes.get(sub_key)

            mn.branches.append(MuxBranch(
                condition=bcond,
                source_signal=src,
                target_node=dst,
                child=child,
            ))

        # 外层 mux 额外连接内层子 mux (不在 g 中的)
        if d == 0:
            for sub_pre, sub_mn in muxes.items():
                if not sub_pre:
                    continue
                if sub_pre[:-1] == pre:
                    outer_cond = sub_pre[0]
                    already = any(b.condition == outer_cond for b in mn.branches)
                    if not already:
                        mn.branches.append(MuxBranch(
                            condition=outer_cond,
                            source_signal="",
                            target_node=dst,
                            child=sub_mn,
                        ))

    # ── 单边简单条件 ──
    simples: list[SimpleCondition] = []
    for pre, g in groups.items():
        if pre in muxes:
            continue
        if len(g) != 1:
            continue
        ed = g[0]
        clabel = " && ".join(ed.condition_chain)
        src = _short(ed.src)

        pp = pre[:-1] if pre else None
        parent_id = ""
        if pp:
            parent_mux = muxes.get(pp)
            parent_id = parent_mux.id if parent_mux else ""
        elif muxes.get(tuple()):
            parent_id = muxes[tuple()].id

        simples.append(SimpleCondition(
            id=f"cond_{_short(dst)}_{_short(clabel[:20])}",
            condition=clabel,
            source_signal=src,
            target_node=dst,
            parent_mux_id=parent_id,
        ))

    return ControlTree(
        target=dst,
        target_label=label,
        muxes=muxes,
        simples=simples,
    )
