"""
viz_new.py — V8.0 全新渲染引擎

对标 Chip Design Reference 风格:
  - 黑+白+蓝 三色调
  - 直角矩形 (box shape, no rounded corners)
  - 无箭头实线
  - 蓝色虚线 cluster
  - Courier 等宽字体

三个独立渲染器：
  render_signal_v8()   — 信号拓扑图 ("谁和谁有关系？")
  render_dataflow_v8() — 数据流图 ("怎么算的？")
  render_control_v8()  — 控制流图 ("谁来控制？")
"""

from __future__ import annotations
from collections import defaultdict
from .viz_data_models import VizData, VizEdge, VizNode
from ..analyzer.stage_inferrer import infer_stages_bfs


# ══════════════════════════════════════════════
# 共享工具
# ══════════════════════════════════════════════

def _dot_id(s: str) -> str:
    """生成安全的 DOT 标识符"""
    buf = []
    for ch in s:
        if ch.isalnum() or ch == "_": buf.append(ch)
        else: buf.append("_")
    result = "".join(buf)
    if result and result[0].isdigit():
        result = "x_" + result
    return "G" + result[:50]


def _short(s: str) -> str:
    """模块前缀剥离"""
    return s.split(".")[-1]


def _width_str(n: VizNode) -> str:
    """位宽标注 {msb:lsb} or {msb}"""
    if n.width and n.width != (0, 0):
        msb, lsb = n.width
        return f"{{{msb}}}" if msb == lsb else f"{{{msb}:{lsb}}}"
    return ""


# OP 符号映射
_OP_SYM = {
    "Add": "+", "Subtract": "−", "Multiply": "×", "Divide": "÷",
    "BinaryAnd": "&", "BinaryOr": "|", "BinaryXor": "^",
    "LogicalShiftLeft": "<<", "LogicalShiftRight": ">>",
    "ArithmeticShiftLeft": "<<<", "ArithmeticShiftRight": ">>>",
    "Equality": "==", "GreaterThan": ">", "LessThan": "<",
    "GreaterThanEqual": ">=", "LessThanEqual": "<=",
    "Inequality": "!=", "BinaryNand": "~&", "BinaryNor": "~|",
    "LogicalAnd": "&&", "LogicalOr": "||", "Mod": "%",
}


# ══════════════════════════════════════════════
# 1. SIGNAL 图
# ══════════════════════════════════════════════

def render_signal_v8(viz: VizData, config: dict | None = None):
    """
    信号拓扑图 - 纯信号级别的连接关系。
    输入在左 → 中间信号 → 输出在右。
    蓝色虚线圈定逻辑分区。
    """
    cfg = config or {}
    title = cfg.get("title", "Signal Topology")

    lines = []
    L = lines.append

    # ── 图头 ──
    L('digraph signal_v8 {')
    L(f'  label="{title}"; labelloc=t; fontsize=14; fontname="Helvetica";')
    L('  rankdir=LR; bgcolor=white;')
    L('  nodesep=0.4; ranksep=0.8;')
    L('  node [shape=box style=solid color=black fillcolor=white '
      'fontname="Courier" fontsize=9 penwidth=1];')
    L('  edge [color=black arrowhead=none penwidth=1];')
    L('')

    # ── 分组 ──
    inputs, outputs, mids, clk_rst = [], [], [], []
    for n in viz.nodes:
        k = n.kind
        if k in ("PORT_IN", "CONST"): inputs.append(n)
        elif k in ("PORT_OUT", "PORT_INOUT"): outputs.append(n)
        elif k in ("CLOCK", "RESET"): clk_rst.append(n)
        else: mids.append(n)

    for lst in (inputs, outputs, mids, clk_rst):
        lst.sort(key=lambda n: _short(n.id))

    def cluster(label_text, nodes, bg="#f8faff"):
        if not nodes: return
        L(f'  subgraph cluster_{_dot_id(label_text)} {{')
        L(f'    label="{label_text}"; fontsize=10; fontname="Helvetica";')
        L(f'    style=dashed; color="#2563eb"; bgcolor="{bg}";')
        for n in nodes:
            ws = _width_str(n)
            lbl = f"{_short(n.id)} {ws}" if ws else _short(n.id)
            L(f'    {_dot_id(n.id)} [label="{lbl}" fontname="Courier" fontcolor=black];')
        L('  }')
        L('')

    cluster("Inputs", inputs)
    if clk_rst:
        cluster("Clock/Reset", clk_rst, "#f5f5f5")
    cluster("Internal Signals", mids)
    cluster("Outputs", outputs)

    # ── Rank 约束 ──
    all_in = inputs + clk_rst
    if all_in and mids:
        L(f'  {_dot_id(all_in[0].id)} -> {_dot_id(mids[0].id)} [style=invis weight=0];')
    if mids and outputs:
        L(f'  {_dot_id(mids[-1].id)} -> {_dot_id(outputs[0].id)} [style=invis weight=0];')

    # ── 边 ──
    seen = set()
    for e in viz.edges:
        if e.kind in ("CLOCK", "RESET"): continue
        key = (e.src, e.dst)
        if key in seen: continue
        seen.add(key)
        L(f'  {_dot_id(e.src)} -> {_dot_id(e.dst)};')

    L('}')
    return "\n".join(lines)


# ══════════════════════════════════════════════
# 2. DATAFLOW 图
# ══════════════════════════════════════════════

def render_dataflow_v8(viz: VizData, config: dict | None = None):
    """
    数据流图 - 展示 "怎么算的？"
    信号节点 + OP 圆形节点。
    组合边（同 stage）虚线 / 时序边（跨 stage）实线。
    条件控制边用蓝色虚线标注。
    """
    cfg = config or {}
    title = cfg.get("title", "Dataflow")

    # Stage 分层
    stages = infer_stages_bfs(viz)  # {node_id: stage_int}
    all_sids = sorted(set(stages.values()))
    if not all_sids:
        all_sids = [0]

    lines = []
    L = lines.append

    L('digraph dataflow_v8 {')
    L(f'  label="{title}"; labelloc=t; fontsize=14; fontname="Helvetica";')
    L('  rankdir=LR; bgcolor=white;')
    L('  nodesep=0.3; ranksep=0.7;')
    L('  node [shape=box style=solid color=black fillcolor=white '
      'fontname="Courier" fontsize=9 penwidth=1];')
    L('  edge [color=black arrowhead=none penwidth=1];')
    L('')

    # ── OP 节点收集 ──
    op_registry: dict[str, str] = {}     # op_id → symbol
    op_edges: list[dict] = []              # [{src, op_id, dst}]
    seen_ops: set[tuple[str, str]] = set()

    for e in viz.edges:
        if not e.source_op: continue
        sym = _OP_SYM.get(e.source_op, e.source_op)
        key = (e.dst, e.source_op)
        if key not in seen_ops:
            seen_ops.add(key)
            oid = f"op_{e.source_op}_{_dot_id(e.dst)}"[:60]
            op_registry[oid] = sym
        else:
            oid = f"op_{e.source_op}_{_dot_id(e.dst)}"[:60]
        op_edges.append({"src": e.src, "op_id": oid, "dst": e.dst})

    # ── 按 stage 渲染 cluster ──
    for sid in all_sids:
        snodes = [nid for nid, s in stages.items() if s == sid]
        sops = []
        for oe in op_edges:
            if oe["dst"] in snodes and oe["op_id"] not in sops:
                sops.append(oe["op_id"])

        L(f'  subgraph cluster_stage_{sid} {{')
        L(f'    label="Stage {sid}"; fontsize=10; fontname="Helvetica";')
        L(f'    style=dashed; color="#2563eb"; bgcolor="#f8faff";')

        for n in viz.nodes:
            if n.id not in snodes: continue
            ws = _width_str(n)
            lbl = f"{_short(n.id)} {ws}" if ws else _short(n.id)
            L(f'    {_dot_id(n.id)} [label="{lbl}" fontname="Courier" fontcolor=black];')

        for oid in sops:
            sym = op_registry.get(oid, "?")
            L(f'    {_dot_id(oid)} [label="{sym}" shape=circle '
              f'width=0.3 height=0.3 style=solid color=black fillcolor=white '
              f'fontsize=11 fontname="Helvetica-Bold"];')
        L('  }')
        L('')

    # ── Rank 约束 ──
    for i in range(len(all_sids) - 1):
        s0, s1 = all_sids[i], all_sids[i + 1]
        n0 = [nid for nid, s in stages.items() if s == s0]
        n1 = [nid for nid, s in stages.items() if s == s1]
        if n0 and n1:
            L(f'  {_dot_id(n0[0])} -> {_dot_id(n1[0])} [style=invis weight=0];')

    # ── 数据边: src → OP → dst ──
    data_pairs = {(oe["src"], oe["dst"]) for oe in op_edges}
    for oe in op_edges:
        st_src = stages.get(oe["src"], -1)
        st_dst = stages.get(oe["dst"], -1)
        is_timed = (st_src >= 0 and st_dst >= 0 and st_dst > st_src)
        style = "solid" if is_timed else "dashed"  # 时序=实线, 组合=虚线
        L(f'  {_dot_id(oe["src"])} -> {_dot_id(oe["op_id"])} [style={style}];')
        L(f'  {_dot_id(oe["op_id"])} -> {_dot_id(oe["dst"])} [style={style}];')

    # ── 非 OP 边 ──
    for e in viz.edges:
        key = (e.src, e.dst)
        if key in data_pairs: continue
        if e.kind in ("CLOCK", "RESET"): continue

        chain = getattr(e, "condition_chain", None) or []
        if chain:
            cond = " && ".join(chain)
            if len(cond) > 30: cond = cond[:27] + "..."
            L(f'  {_dot_id(e.src)} -> {_dot_id(e.dst)} '
              f'[label="{cond}" fontsize=7 style=dashed color="#2563eb"];')
        else:
            st_src = stages.get(e.src, -1)
            st_dst = stages.get(e.dst, -1)
            is_timed = (st_src >= 0 and st_dst >= 0 and st_dst > st_src)
            style = "solid" if is_timed else "dashed"
            L(f'  {_dot_id(e.src)} -> {_dot_id(e.dst)} [style={style}];')

    L('}')
    return "\n".join(lines)


# ══════════════════════════════════════════════
# 3. CONTROL 图
# ══════════════════════════════════════════════

def render_control_v8(viz: VizData, config: dict | None = None):
    """
    控制流图 - 展示 "谁来控制数据分发？"
    Mux 菱形节点 + 信号矩形节点。
    蓝色虚线框按 target 分组。
    """
    from .control_tree import build_control_tree

    cfg = config or {}
    title = cfg.get("title", "Control Flow")

    lines = []
    L = lines.append

    L('digraph control_v8 {')
    L(f'  label="{title}"; labelloc=t; fontsize=14; fontname="Helvetica";')
    L('  rankdir=LR; bgcolor=white;')
    L('  nodesep=0.4; ranksep=0.6;')
    L('  node [shape=box style=solid color=black fillcolor=white '
      'fontname="Courier" fontsize=9 penwidth=1];')
    L('  edge [color=black arrowhead=none fontsize=7];')
    L('')

    # 收集条件边
    cond_edges: dict[str, list[VizEdge]] = defaultdict(list)
    for e in viz.edges:
        chain = getattr(e, "condition_chain", None) or []
        if chain:
            cond_edges[e.dst].append(e)

    for dst_id, edges in sorted(cond_edges.items()):
        dn = _short(dst_id)
        tree = build_control_tree(dst_id, edges)

        L(f'  subgraph cluster_{_dot_id(dst_id)} {{')
        L(f'    label="{dn}"; fontsize=10; fontname="Helvetica";')
        L(f'    style=dashed; color="#2563eb"; bgcolor="#f8faff";')

        # 目标节点
        ws = ""
        for n in viz.nodes:
            if n.id == dst_id:
                ws = _width_str(n)
                break
        tl = f"{dn} {ws}" if ws else dn
        L(f'    {_dot_id(dst_id)} [label="{tl}" fontname="Courier" fontcolor=black];')

        # Mux 节点 (菱形)
        for mux in tree.sorted_muxes():
            mid = _dot_id(mux.id)
            L(f'    {mid} [label="{mux.label}" shape=diamond '
              f'style=solid color="#2563eb" fillcolor="#e8f0fe" fontsize=9];')

            for b in mux.branches:
                if b.child is not None:
                    cid = _dot_id(b.child.id)
                    L(f'    {mid} -> {cid} [label="{b.condition}"];')
                else:
                    tid = _dot_id(b.target_node)
                    L(f'    {tid} [label="{b.source_signal}" fontname="Courier" '
                      f'shape=box style=solid color=black fillcolor=white];')
                    L(f'    {mid} -> {tid} [label="{b.condition}"];')

        # 简单条件 (无互斥)
        for sc in tree.simples:
            sid = _dot_id(sc.source)
            L(f'    {sid} [label="{sc.source_label}" fontname="Courier" '
              f'shape=box style=solid color=black fillcolor=white];')
            L(f'    {sid} -> {_dot_id(dst_id)} '
              f'[label="{sc.condition}" style=dashed color="#2563eb"];')

        L('  }')
        L('')

    L('}')
    return "\n".join(lines)
