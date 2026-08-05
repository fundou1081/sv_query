"""
viz_dataflow_scope_renderer.py v3 — 独立 scope 选择器渲染

设计目标:
- 每个 if/case/三目分支 = 独立子图 subgraph
- 分支内展现完整的数据流: 信号→OP→目标
- 逐层嵌套显示逻辑深度
- True框(绿虚线) / False框(红虚线)

与 viz_engine.render_dataflow() 互补:
  - render_dataflow: OP节点 小矩形风格
  - render_dataflow_scope: 嵌套 cluster 风格 (适合控制密集型)
"""

from __future__ import annotations
from collections import defaultdict
from .viz_data_models import VizData, VizEdge, VizNode
from .control_tree import build_control_tree

_OP_SYM = {
    "Add": "+", "Multiply": "\u00d7", "Subtract": "\u2212",
    "LogicalShiftRight": ">>", "LogicalShiftLeft": "<<",
    "ArithmeticShiftRight": ">>>", "BitwiseAnd": "&",
    "BitwiseOr": "|", "BitwiseXor": "^",
}

def _dot_id(s: str) -> str:
    buf = []
    for ch in s:
        if ch.isalnum() or ch == "_": buf.append(ch)
        else: buf.append(f"_{ord(ch):x}_")
    return "".join(buf)

def _short(s: str) -> str:
    return s.split(".")[-1] if "." in s else s


def render_dataflow_scope(viz: VizData, config: dict | None = None) -> str:
    cfg = config or {}
    title = cfg.get("title", "Dataflow Scope")

    out = [f"""digraph dataflow_scope {{
  label="{title}"; labeljust=l;
  rankdir=TB; splines=polyline;
  nodesep=0.3; ranksep=0.5;
  compound=true; newrank=true;
  node [fontname=Helvetica fontsize=9];
  edge [color=black penwidth=1];
"""]
    E = out.append

    # ── 分组: 有条件的边 vs 无条件边 ──
    cond_by_dst: dict[str, list] = defaultdict(list)
    for e in viz.edges:
        chain = getattr(e, "condition_chain", None) or []
        if chain and e.kind not in ("CLOCK", "RESET", "BIT_SELECT"):
            cond_by_dst[e.dst].append(e)
        elif e.kind in ("CLOCK", "RESET"):
            pass  # CLOCK/RESET 不进入 scope, 在全局图中标为虚线

    muxed_pairs: set[tuple[str, str]] = set()
    clk_rst_edges: list = []  # 收集 CLOCK/RESET 边单独渲染
    for e in viz.edges:
        if e.kind in ("CLOCK", "RESET"):
            clk_rst_edges.append(e)
    counter = [0]
    node_map = {n.id: n for n in viz.nodes}

    # ── 对每个 dst 渲染 scope ──
    for dst_id, cedges in sorted(cond_by_dst.items()):
        if len(cedges) < 2:
            continue

        tree = build_control_tree(dst_id, cedges)
        root_mux = tree.muxes.get(tuple()) if hasattr(tree, 'muxes') else None
        sel_sig = root_mux.signal if root_mux else "?"

        counter[0] += 1
        outer_id = f"cluster_sel_{counter[0]}"

        E(f'  subgraph {outer_id} {{')
        E(f'    label="选择: {sel_sig}"; labeljust=l; fontsize=10;')
        E(f'    fontname="Helvetica-Bold"; style=dashed; color="#888888"; penwidth=1.5;')
        E(f'    margin=20;')

        # 内层: 每个分支 = 独立 subgraph
        for mux in tree.sorted_muxes():
            _render_mux_branch_subgraphs(E, mux, cedges, node_map, counter, "", dst_id)

        E(f'  }}')

        for ce in cedges:
            muxed_pairs.add((ce.src, ce.dst))

    # ── 纯数据边 ──
    seen = set()
    for e in viz.edges:
        if e.kind in ("CLOCK", "RESET", "BIT_SELECT"):
            continue
        key = (e.src, e.dst)
        if key in muxed_pairs or key in seen:
            continue
        seen.add(key)
        E(f'  {_dot_id(e.src)} -> {_dot_id(e.dst)};')

    # ── 信号节点 ──
    for n in viz.nodes:
        sn, ws = _short(n.id), ""
        if n.width and n.width != (0, 0):
            msb, lsb = n.width
            ws = f"[{msb}]" if msb == lsb else f"[{msb}:{lsb}]"
        lbl = f"{sn}  {ws}" if ws else sn
        E(f'  {_dot_id(n.id)} [label="{lbl}" fontname="Courier" '
          f'fontcolor="#2e7d32" shape=box style=solid fillcolor=white];')

    E("}")
    return "\n".join(out)


def _render_mux_branch_subgraphs(E, mux, cedges, node_map, counter, indent, dst_id):
    """渲染 MUX 的分支: 每个分支独立子图, 内有完整数据流"""
    colors = [
        ("#1b5e20", "#f1f8e9"), ("#c62828", "#ffebee"),
        ("#1565c0", "#e3f2fd"), ("#6a1b9a", "#f3e5f5"),
        ("#e65100", "#fff3e0"), ("#00838f", "#e0f7fa"),
    ]

    for br in mux.branches:
        counter[0] += 1
        border, bg = colors[counter[0] % len(colors)]
        cid = f"cluster_br_{counter[0]}"

        cond_lbl = br.condition.replace("'b", "'").replace("  ", " ")
        if len(cond_lbl) > 25:
            cond_lbl = cond_lbl[:22] + "..."

        E(f'{indent}  subgraph {cid} {{')
        E(f'{indent}    label="{cond_lbl}"; fontsize=8; fontcolor="{border}";')
        E(f'{indent}    labeljust=l; style=dashed; color="{border}"; penwidth=1.2;')
        E(f'{indent}    bgcolor="{bg}";')

        if br.source_signal:
            src_short = _short(br.source_signal)
            # 找全路径
            src_full = ""
            for ce in cedges:
                if _short(ce.src) == src_short:
                    src_full = ce.src
                    break
            if not src_full:
                src_full = br.source_signal
            # 信号节点
            nid = _dot_id(f"br{counter[0]}_{src_short}")
            ws = ""
            if src_full in node_map:
                ws = _width_str(node_map[src_full])
            E(f'{indent}    {nid} [label="{src_short}  {ws}"' if ws else f'{indent}    {nid} [label="{src_short}"' +
              f' fontname="Courier" fontcolor="#2e7d32" shape=box style=solid '
              f'color="{border}" fillcolor=white fontsize=9];')

            # OP 节点 (如果有 source_op)
            for ce in cedges:
                if _short(ce.src) == src_short and ce.source_op:
                    sym = _OP_SYM.get(ce.source_op, ce.source_op)
                    op_id = f"op_{counter[0]}_{sym}_{src_short}"
                    E(f'{indent}    {op_id} [label="{sym}" shape=box '
                      f'width=0.25 height=0.25 style=solid color=black fillcolor=white '
                      f'fontsize=8 fontname="Helvetica-Bold" penwidth=1.2];')
                    # 边: src → op
                    E(f'{indent}    {nid} -> {op_id};')

            # 目标节点
            dst_short = _short(dst_id)
            tgt_id = f"tgt_{counter[0]}_{dst_short}"
            E(f'{indent}    {tgt_id} [label="{dst_short}" fontname="Courier" '
              f'fontcolor="{border}" shape=box style=solid color="{border}" '
              f'fillcolor=white fontsize=9];')

            # 边: src/op → 目标
            for ce in cedges:
                if _short(ce.src) == src_short:
                    if ce.source_op:
                        sym = _OP_SYM.get(ce.source_op, ce.source_op)
                        op_id = f"op_{counter[0]}_{sym}_{src_short}"
                        E(f'{indent}    {op_id} -> {tgt_id};')
                    else:
                        E(f'{indent}    {nid} -> {tgt_id};')
                    break

        if br.child:
            _render_mux_branch_subgraphs(E, br.child, cedges, node_map, counter, indent + "  ", dst_id)

        E(f'{indent}  }}')

def _width_str(n):
    if n and n.width and n.width != (0, 0):
        msb, lsb = n.width
        return f"{(msb)}" if msb == lsb else f"{(msb)}:{(lsb)}"
    return ""
