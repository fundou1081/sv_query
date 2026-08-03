"""
viz_dataflow_new.py — Dataflow 图 (V8.0)

对标参考图: 左→右, 信号矩形 + OP 小圆, 蓝色虚线 cluster, 组合虚线/时序实线
回答: "怎么算的？"
"""

from __future__ import annotations
from collections import defaultdict
from ..analyzer.stage_inferrer import infer_stages_bfs
from .viz_data_models import VizData

_OP_SYM: dict[str, str] = {
    "Add": "+", "Subtract": "−", "Multiply": "×", "Divide": "÷",
    "BinaryAnd": "&", "BinaryOr": "|", "BinaryXor": "^",
    "LogicalShiftLeft": "<<", "LogicalShiftRight": ">>",
    "ArithmeticShiftLeft": "<<<", "ArithmeticShiftRight": ">>>",
    "Equality": "==", "GreaterThan": ">", "LessThan": "<",
}

def _mid(s: str) -> str:
    r = []
    for ch in s:
        if ch.isalnum() or ch == "_": r.append(ch)
        else: r.append("_")
    return "D" + "".join(r)[:50]

def _short(s: str) -> str: return s.split(".")[-1]


def render_dataflow(viz: VizData, config: dict | None = None):
    cfg = config or {}
    title = cfg.get("title", "Dataflow")

    # BFS stage 分层 (非 REG 无 stage, 手动按连接关系分组)
    stages_raw = infer_stages_bfs(viz)
    # stages_raw: {str_node_id: int_stage, ...}
    
    out = []
    E = out.append
    E("digraph dataflow {")
    E(f'  rankdir=TB; bgcolor=white; label="{title}"; labelloc=t; fontsize=14; fontname="Helvetica";')
    E('  nodesep=0.4; ranksep=0.8;')
    E('  node [shape=box style=solid color=black fillcolor=white fontname="Courier" fontsize=9 penwidth=1];')
    E('  edge [color=black arrowhead=none penwidth=1];')
    E("")

    # OP 节点收集
    op_nodes: dict[str, str] = {}
    op_edges: list[dict] = []
    seen_ops: set[tuple[str, str]] = set()
    for e in viz.edges:
        if not e.source_op: continue
        sym = _OP_SYM.get(e.source_op, e.source_op)
        key = (e.dst, e.source_op)
        if key not in seen_ops:
            seen_ops.add(key)
            op_id = f"op_{e.source_op}_{_short(e.dst)}"
            op_nodes[op_id] = sym
        else:
            op_id = f"op_{e.source_op}_{_short(e.dst)}"
        op_edges.append({"src": e.src, "op_id": op_id, "dst": e.dst})

    # 按 stage 分组 signal 节点
    stage_sigs: dict[int, list[str]] = defaultdict(list)
    for nid, sid in stages_raw.items():
        stage_sigs[sid].append(nid)
    all_sids = sorted(stage_sigs.keys())

    # 按 stage 画 cluster
    for sid in all_sids:
        snodes = stage_sigs[sid]
        # 收集这个 stage 里的 OP 节点
        sop_ids: list[str] = []
        for oe in op_edges:
            if oe["dst"] in snodes:
                if oe["op_id"] not in sop_ids:
                    sop_ids.append(oe["op_id"])

        E(f'  subgraph cluster_s{sid} {{')
        E(f'    label="Stage {sid}"; fontsize=10; fontname="Helvetica";')
        E(f'    style=dashed; color="#2563eb"; bgcolor="#f8faff";')

        for n in viz.nodes:
            if n.id not in snodes: continue
            nm = _short(n.id)
            if n.width and n.width != (0, 0):
                msb, lsb = n.width
                w = f"[{msb}]" if msb == lsb else f"[{msb}:{lsb}]"
                nm = f"{nm} ({w})"
            E(f'    {_mid(n.id)} [label="{nm}" fontname="Courier" fontcolor=black];')

        for op_id in sop_ids:
            sym = op_nodes.get(op_id, "?")
            E(f'    {_mid(op_id)} [label="{sym}" shape=circle width=0.3 height=0.3 '
              f'style=solid color=black fillcolor=white fontsize=11 fontname="Helvetica-Bold"];')

        E("  }")
        E("")

    # 不可见 rank 边: 强制 stage 顺序
    for i in range(len(all_sids) - 1):
        n0, n1 = stage_sigs[all_sids[i]], stage_sigs[all_sids[i + 1]]
        if n0 and n1:
            E(f'  {_mid(n0[0])} -> {_mid(n1[0])} [style=invis weight=0];')

    # 数据边: src → OP → dst (实线黑)
    # cycle delta: 同 stage = 组合边 (虚线), 跨 stage = 时序边 (实线)
    data_pairs = {(oe["src"], oe["dst"]) for oe in op_edges}
    for oe in op_edges:
        src_stage = stages_raw.get(oe["src"], -1)
        dst_stage = stages_raw.get(oe["dst"], -1)
        is_comb = (src_stage == dst_stage and src_stage >= 0)
        style = "dashed" if is_comb else "solid"
        E(f'  {_mid(oe["src"])} -> {_mid(oe["op_id"])} [style={style}];')
        E(f'  {_mid(oe["op_id"])} -> {_mid(oe["dst"])} [style={style}];')

    # 非 OP 边: 条件边 → 蓝色虚线, 普通边 → 黑色实线/虚线
    for e in viz.edges:
        key = (e.src, e.dst)
        if key in data_pairs: continue
        if e.kind in ("CLOCK", "RESET"): continue

        chain = getattr(e, "condition_chain", None) or []
        if chain:
            cond = " && ".join(chain)
            if len(cond) > 28: cond = cond[:25] + "..."
            E(f'  {_mid(e.src)} -> {_mid(e.dst)} '
              f'[label="{cond}" fontsize=7 style=dashed color="#2563eb"];')
        else:
            src_stage = stages_raw.get(e.src, -1)
            dst_stage = stages_raw.get(e.dst, -1)
            is_comb = (src_stage == dst_stage and src_stage >= 0)
            style = "dashed" if is_comb else "solid"
            E(f'  {_mid(e.src)} -> {_mid(e.dst)} [style={style}];')

    E("}")
    return "\n".join(out)
