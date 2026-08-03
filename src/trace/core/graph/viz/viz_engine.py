"""
viz_engine.py — V8.1 统一渲染引擎

对标三张参考图 (CRV5/Dataflow/Control 图的共同 DNA):
  布局: 左→右
  节点: 直角矩形 (白底黑框) + 小圆 OP 节点
  边:   黑实线, 无箭头 (数据流) or 箭头 (控制流)
  cluster: 蓝色虚线框, 标题在顶部
  颜色: 黑+白+蓝+红+绿 (克制五色)
  字体: Courier 等宽 (信号名) + Helvetica (标注)

三个独立渲染器共用底层样式规则:
  render_signal()   — 信号拓扑图
  render_dataflow() — 数据流/运算图
  render_control()  — 控制流/选择图
"""

from __future__ import annotations
from collections import defaultdict
from .viz_data_models import VizData, VizEdge, VizNode
from ..analyzer.stage_inferrer import infer_stages_bfs


# ═══════════════════════════════════════════════════
# 共享工具
# ═══════════════════════════════════════════════════

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
    return s.split(".")[-1] if "." in s else s


def _width_label(n: VizNode) -> str:
    """位宽花括号标注 {msb:lsb} or {msb}"""
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

# ── DOT 模板 ──
_DOT_HEADER = '''digraph {name} {{
  rankdir=LR; bgcolor=white;
  label="{title}"; labelloc=t; fontsize=14; fontname="Helvetica";
  nodesep=0.6; ranksep=1.2; splines=ortho;
  node [shape=box style=solid color=black fillcolor=white
        fontname="Courier" fontsize=9 penwidth=1];
  edge [color=black penwidth=1];\n'''

_DOT_FOOTER = "}\n"

_CLUSTER_HEAD = '''  subgraph cluster_{id} {{
    label="{label}"; fontsize=10; fontname="Helvetica";
    style=dashed; color="#2563eb"; bgcolor="#f8faff";\n'''
_CLUSTER_FOOT = "  }\n"


# ═══════════════════════════════════════════════════
# 1. SIGNAL 图
# ═══════════════════════════════════════════════════

def render_signal(viz: VizData, config: dict | None = None):
    """
    信号拓扑图 — "谁和谁有关系？"
    对标参考图风格: 左→右, 白底矩形, 蓝虚线 cluster, 绿色信号标注
    """
    cfg = config or {}
    title = cfg.get("title", "Signal Topology")

    out = [_DOT_HEADER.format(name="signal", title=title), ""]
    E = out.append

    # 分组
    inputs, outputs, mids, clkrst = [], [], [], []
    for n in viz.nodes:
        k = n.kind
        if k in ("PORT_IN", "CONST"): inputs.append(n)
        elif k in ("PORT_OUT", "PORT_INOUT"): outputs.append(n)
        elif k in ("CLOCK", "RESET"): clkrst.append(n)
        else: mids.append(n)

    for lst in (inputs, outputs, mids, clkrst):
        lst.sort(key=lambda n: _short(n.id))

    def _cluster(label, nodes, bg="#f8faff"):
        if not nodes: return
        E(_CLUSTER_HEAD.format(id=_dot_id(label), label=label))
        if bg != "#f8faff":
            E(f'    bgcolor="{bg}";')
        for n in nodes:
            ws = _width_label(n)
            lbl = f"{_short(n.id)}  {ws}" if ws else _short(n.id)
            # 信号名用绿色 (参考图风格)
            E(f'    {_dot_id(n.id)} [label="{lbl}" fontname="Courier" fontcolor="#2e7d32"];')
        E(_CLUSTER_FOOT)

    _cluster("Inputs", inputs)
    _cluster("Clock/Reset", clkrst, "#fafafa")
    _cluster("Internal Signals", mids)
    _cluster("Outputs", outputs)

    # Rank 约束: input→mid→output
    all_in = inputs + clkrst
    if all_in and mids:
        E(f'  {_dot_id(all_in[0].id)} -> {_dot_id(mids[0].id)} [style=invis weight=0];')
    if mids and outputs:
        E(f'  {_dot_id(mids[-1].id)} -> {_dot_id(outputs[0].id)} [style=invis weight=0];')

    # 边: 黑色细实线
    seen = set()
    for e in viz.edges:
        if e.kind in ("CLOCK", "RESET"): continue
        key = (e.src, e.dst)
        if key in seen: continue; seen.add(key)
        E(f'  {_dot_id(e.src)} -> {_dot_id(e.dst)};')

    E(_DOT_FOOTER)
    return "\n".join(out)


# ═══════════════════════════════════════════════════
# 2. DATAFLOW 图
# ═══════════════════════════════════════════════════

def render_dataflow(viz: VizData, config: dict | None = None):
    """
    数据流/运算图 — "怎么算的？"
    对标参考图: 信号节点+OP圆节点, stage cluster, 组合虚线/时序实线
    """
    cfg = config or {}
    title = cfg.get("title", "Dataflow")

    stages = infer_stages_bfs(viz)
    all_sids = sorted(set(stages.values()))
    if not all_sids: all_sids = [0]

    out = [_DOT_HEADER.format(name="dataflow", title=title), ""]
    E = out.append

    # ── 统一操作节点: OP + 切片/截断 + 常量 都归一化为小矩形 ──
    import re
    op_registry: dict[str, str] = {}   # node_id → label ("+", "×", "[7:0]", "16'd128", ...)
    op_edges: list[dict] = []           # [{src, op_id, dst}]
    seen_op_nodes: set[str] = set()

    # [V8.2] 从 viz.meta["datapath"] 读取已富化的数据 (不再解析SV源码)
    dp = viz.meta.get("datapath", {})
    const_map: dict[str, list[str]] = {k: list(v) for k, v in dp.get("const_map", {}).items()}
    concat_map: dict[str, str] = {}
    # func 信息已在 VizNode 上 (is_function, width)
    # 拼接信息暂时为空 (后续可加到 datapath 中)

    for e in viz.edges:
        if e.kind == "BIT_SELECT":
            continue  # BIT_SELECT 都是自环，跳过

        # 拼接/聚合: dst 有 concat 映射 (如 {8{a[7]}}, {a, b})
        dn_short = e.dst.split('.')[-1] if '.' in e.dst else e.dst
        if dn_short in concat_map and e.kind == "DRIVER" and not e.source_op:
            oid = f"op_concat_{_dot_id(e.dst)}"[:60]
            if oid not in seen_op_nodes:
                seen_op_nodes.add(oid)
                op_registry[oid] = concat_map[dn_short]
            op_edges.append({"src": e.src, "op_id": oid, "dst": e.dst})
            continue

        # 常量: 只在没有 condition_chain 的纯数据流边上 (不作为三元条件中的阈值)
        dn_short = e.dst.split('.')[-1] if '.' in e.dst else e.dst
        chain = getattr(e, "condition_chain", None) or []
        if dn_short in const_map and e.kind == "DRIVER" and not chain:
            for c in const_map[dn_short]:
                oid = f"op_const_{c}_{_dot_id(e.dst)}"[:60]
                if oid not in seen_op_nodes:
                    seen_op_nodes.add(oid)
                    op_registry[oid] = c
                # src=None 标记: 常量没有输入源
                op_edges.append({"src": None, "op_id": oid, "dst": e.dst})
            continue

        # 隐式切片: src 名字带 [...]  且  source_op 为空
        import re as _re2
        sn = e.src.split('.')[-1] if '.' in e.src else e.src
        dn = e.dst.split('.')[-1] if '.' in e.dst else e.dst
        has_slice = _re2.search(r'\[([^\]]+)\]', sn)
        if has_slice and not e.source_op:
            # 跳过自环位切片 (如 sum[7:0] → sum, a[15:8] → a)
            src_base = _re2.sub(r'\[[^\]]+\]', '', sn)
            if src_base == dn:
                continue
            label = f"[{has_slice.group(1)}]"
            oid = f"op_slice_{_dot_id(e.src)}"[:60]
            if oid not in seen_op_nodes:
                seen_op_nodes.add(oid)
                op_registry[oid] = label
            op_edges.append({"src": e.src, "op_id": oid, "dst": e.dst})
            continue

        if not e.source_op: continue
        sym = _OP_SYM.get(e.source_op, e.source_op)
        oid = f"op_{e.source_op}_{_dot_id(e.dst)}"[:60]
        if oid not in seen_op_nodes:
            seen_op_nodes.add(oid)
            op_registry[oid] = sym
        op_edges.append({"src": e.src, "op_id": oid, "dst": e.dst})
        
        # [V8.3] 常量操作数也连接到 OP 节点
        # 当 dst 有常量映射时，为每条 OP 边生成常量→OP 的额外边
        dn_short = e.dst.split('.')[-1] if '.' in e.dst else e.dst
        if dn_short in const_map:
            for c in const_map[dn_short]:
                cid = f"op_const_{c}_{_dot_id(e.dst)}"[:60]
                if cid not in seen_op_nodes:
                    seen_op_nodes.add(cid)
                    op_registry[cid] = c
                op_edges.append({"src": None, "op_id": oid, "dst": e.dst, "_const_src": cid})

    # ── Scope 融合: 条件边用嵌套 cluster 框表示选择器 ──
    from .control_tree import build_control_tree

    # 构建信号→OP+常量的完整索引
    # [V8.2] 从 datapath 读取 sig_op_index (不再遍历 viz.edges 构建)
    sig_op_index: dict[str, dict] = dp.get("op_index", {})

    # 收集已被 scope 吞并的 (src, dst) 对
    muxed_pairs: set[tuple[str, str]] = set()
    cond_by_dst: dict[str, list] = defaultdict(list)
    scope_counter = [0]
    _BRANCH_COLORS = [("#1b5e20","#f1f8e9"),("#c62828","#ffebee"),("#1565c0","#e3f2fd"),
                       ("#6a1b9a","#f3e5f5"),("#e65100","#fff3e0"),("#00838f","#e0f7fa")]

    for e in viz.edges:
        chain = getattr(e, "condition_chain", None) or []
        if chain and e.kind not in ("CLOCK", "RESET", "BIT_SELECT"):
            cond_by_dst[e.dst].append(e)

    for dst_id, cedges in cond_by_dst.items():
        if len(cedges) < 2:
            continue
        tree = build_control_tree(dst_id, cedges)
        root_mux = (sorted(tree.muxes.values(), key=lambda m: m.depth)[:1] or [None])[0]
        sel_sig = root_mux.signal if root_mux else "?"
        dst_sn = _short(dst_id)
        dst_consts = const_map.get(dst_sn, [])
        scope_counter[0] += 1
        scope_id = f"scope_{scope_counter[0]}"

        # 外层大框 — 双线实框
        E(f'  subgraph cluster_{scope_id} {{')
        E(f'    label="选择: {sel_sig}"; labeljust=l; fontsize=10; fontname="Helvetica-Bold";')
        E(f'    style=solid; color="#444444"; penwidth=2; margin=20;')

        branches = list(tree.sorted_muxes()[0].branches) if tree.sorted_muxes() else []
        # TRUE/FALSE 上下紧邻: 用 rank=same + invisible edge 强制同层
        prev_nid = None
        for bi, br in enumerate(branches):
            border, bg = _BRANCH_COLORS[bi % len(_BRANCH_COLORS)]
            scope_counter[0] += 1
            br_id = f"scope_{scope_counter[0]}"
            cond_lbl = br.condition.replace("'", "").replace(" ","")
            if len(cond_lbl) > 18: cond_lbl = cond_lbl[:15] + "..."
            # 分支标签加 TRUE/FALSE 注解
            branch_kind = "TRUE" if bi == 0 else "FALSE" if bi == 1 else f"BR{bi}"
            E(f'    subgraph cluster_{br_id} {{')
            E(f'      label="[{branch_kind}] {cond_lbl}"; fontsize=8; fontcolor="{border}";')
            E(f'      labeljust=l; style=dashed; color="{border}"; penwidth=1.2; bgcolor="{bg}";')
            E(f'      rank=same;')
            if br.source_signal:
                sn = _short(br.source_signal)
                nid = _dot_id(f"br{scope_counter[0]}_{sn}")
                sig_info = sig_op_index.get(sn, {})
                ops = sig_info.get('ops', [])
                consts = list(sig_info.get('consts', []))
                if ops and dst_consts:
                    consts = consts + dst_consts
                E(f'      {nid} [label="{sn}" fontname="Courier" fontcolor="#2e7d32" shape=box style=solid fillcolor=white fontsize=9];')
                if ops:
                    for op_i, sym in enumerate(ops):
                        oid = _dot_id(f"scop{scope_counter[0]}_{sym}_{op_i}")
                        E(f'      {oid} [label="{sym}" shape=box width=0.2 height=0.2 style=solid color=black fillcolor=white fontsize=7];')
                        if op_i == 0:
                            E(f'      {nid} -> {oid};')
                        for c in consts:
                            cid = _dot_id(f"scop{scope_counter[0]}_cnst_{c}")
                            E(f'      {cid} [label="{c}" shape=box width=0.2 height=0.2 style=solid color="#1565c0" fillcolor=white fontsize=7];')
                            E(f'      {cid} -> {oid} [color="#1565c0"];')
                        if op_i == len(ops) - 1:
                            E(f'      {oid} -> {_dot_id(dst_id)} [color="{border}"];')
                else:
                    E(f'      {nid} -> {_dot_id(dst_id)} [color="{border}"];')
            # invisible edge 强制 TRUE/FALSE 分支上下紧邻
            if prev_nid:
                E(f'      {prev_nid} -> {nid} [style=invis weight=100];')
            prev_nid = nid
            E(f'    }}')
        E(f'  }}')
        for ce in cedges:
            muxed_pairs.add((ce.src, ce.dst))
    for sid in all_sids:
        snodes = [nid for nid, s in stages.items() if s == sid]
        sops = [oe["op_id"] for oe in op_edges if oe["dst"] in snodes]
        sops = list(dict.fromkeys(sops))

        E(_CLUSTER_HEAD.format(id=f"stage_{sid}", label=f"Stage {sid}"))

        # [V8.2] 从 VizNode.is_function 读取 (已在 _enrich_datapath_info 中标记)
        for n in viz.nodes:
            if n.id not in snodes: continue
            sn = _short(n.id)
            ws = _width_label(n)
            lbl = f"{sn}  {ws}" if ws else sn
            shape = "hexagon" if n.is_function else "box"
            E(f'    {_dot_id(n.id)} [label="{lbl}" fontname="Courier" fontcolor="#2e7d32" shape={shape}];')

        # 统一操作节点: OP/切片用矩形, MUX 用菱形
        for oid in sops:
            sym = op_registry.get(oid, "?")
            if "op_mux_" in oid:
                # MUX 节点: 菱形, 红色边框
                E(f'    {_dot_id(oid)} [label="{sym}" shape=diamond '
                  f'style=solid color="#c62828" fillcolor=white '
                  f'fontsize=8 fontname="Helvetica-Bold" penwidth=1.5];')
            else:
                E(f'    {_dot_id(oid)} [label="{sym}" shape=box '
                  f'width=0.25 height=0.25 style=solid color=black fillcolor=white '
                  f'fontsize=8 fontname="Helvetica-Bold" penwidth=1.5];')

        E(_CLUSTER_FOOT)

    # Rank 约束
    for i in range(len(all_sids) - 1):
        s0, s1 = all_sids[i], all_sids[i + 1]
        n0 = [nid for nid, s in stages.items() if s == s0]
        n1 = [nid for nid, s in stages.items() if s == s1]
        if n0 and n1:
            E(f'  {_dot_id(n0[0])} -> {_dot_id(n1[0])} [style=invis weight=0];')

    # 统一操作边: src→OP→dst (去重, 常量无 src; MUX 特殊处理)
    data_pairs = {(oe["src"], oe["dst"]) for oe in op_edges if oe["src"] is not None}
    seen_src_op: set[tuple[str, str]] = set()
    seen_op_dst: set[tuple[str, str]] = set()
    for oe in op_edges:
        oid = oe["op_id"]
        is_mux = "op_mux_" in oid
        
        # [V8.3] _const_src 边: 常量节点 → OP 节点
        const_src = oe.get("_const_src")
        if const_src:
            csk = (const_src, oid)
            if csk not in seen_src_op:
                seen_src_op.add(csk)
                E(f'  {_dot_id(const_src)} -> {_dot_id(oid)} [style=solid color="#1565c0"];')
            continue
        
        if oe["src"] is not None:
            # 条件信号 → MUX 虚线 (cond/sel 输入)
            if oe.get("_cond_line"):
                sk = (oe["src"], oid)
                if sk not in seen_src_op:
                    seen_src_op.add(sk)
                    E(f'  {_dot_id(oe["src"])} -> {_dot_id(oid)} [style=dashed color="#c62828" arrowsize=0.6];')
                continue
            # MUX parent→child 内部边
            if oe.get("_mux_internal"):
                sk = (oe["src"], oid)
                if sk not in seen_src_op:
                    seen_src_op.add(sk)
                    E(f'  {_dot_id(oe["src"])} -> {_dot_id(oid)} [style=dotted color="#c62828"];')
                continue
            sst = stages.get(oe["src"], -1)
            dst = stages.get(oe["dst"], -1)
            is_timed = (sst >= 0 and dst >= 0 and dst > sst)
            style = "solid" if is_timed else "dashed"
            # 分支标签
            label = ""
            if oe.get("_branch_label"):
                lbl = oe["_branch_label"]
                if len(lbl) > 20: lbl = lbl[:17] + "..."
                label = f'label="{lbl}" fontsize=7'
            sk = (oe["src"], oid)
            if sk not in seen_src_op:
                seen_src_op.add(sk)
                E(f'  {_dot_id(oe["src"])} -> {_dot_id(oid)} [style={style} {label}];')
        # op → dst 边: 常量用蓝色, MUX 用红色
        op_style = "solid"
        op_color = ""
        if oe["src"] is None:
            if is_mux:
                op_color = 'color="#c62828"'  # MUX→dst 红色
            else:
                op_color = 'color="#1565c0"'  # 常量边蓝色
        dk = (oid, oe["dst"])
        if dk not in seen_op_dst:
            seen_op_dst.add(dk)
            E(f'  {_dot_id(oid)} -> {_dot_id(oe["dst"])} [style={op_style} {op_color}];')

    # 非 OP 边 (跳过被 MUX 吞并的边)
    for e in viz.edges:
        if e.kind == "BIT_SELECT": continue
        key = (e.src, e.dst)
        if key in data_pairs: continue
        if key in muxed_pairs: continue  # 被 MUX 吞并
        if e.kind in ("CLOCK", "RESET"): continue
        chain = getattr(e, "condition_chain", None) or []
        if chain:
            cond = " && ".join(chain)
            if len(cond) > 30: cond = cond[:27] + "..."
            E(f'  {_dot_id(e.src)} -> {_dot_id(e.dst)} '
              f'[label="{cond}" fontsize=7 style=dashed color="#2563eb"];')
        else:
            sst = stages.get(e.src, -1)
            dst = stages.get(e.dst, -1)
            is_timed = (sst >= 0 and dst >= 0 and dst > sst)
            E(f'  {_dot_id(e.src)} -> {_dot_id(e.dst)} [style={"solid" if is_timed else "dashed"}];')

    E(_DOT_FOOTER)
    return "\n".join(out)


# ═══════════════════════════════════════════════════
# 3. CONTROL 图
# ═══════════════════════════════════════════════════

def render_control(viz: VizData, config: dict | None = None):
    """
    控制流/选择图 — "谁来控制数据分发？"
    对标参考图: 直角矩形信号节点 + 圆OP节点, 蓝虚线 cluster, 红标注控制
    """
    from .control_tree import build_control_tree

    cfg = config or {}
    title = cfg.get("title", "Control Flow")

    out = [_DOT_HEADER.format(name="control", title=title), ""]
    E = out.append

    # 收集条件边
    cond_edges: dict[str, list[VizEdge]] = defaultdict(list)
    for e in viz.edges:
        chain = getattr(e, "condition_chain", None) or []
        if chain:
            cond_edges[e.dst].append(e)

    for dst_id, edges in sorted(cond_edges.items()):
        dn = _short(dst_id)
        tree = build_control_tree(dst_id, edges)

        E(_CLUSTER_HEAD.format(id=_dot_id(dst_id), label=dn))

        # 目标节点 (绿字)
        ws = ""
        for n in viz.nodes:
            if n.id == dst_id:
                ws = _width_label(n)
                break
        dst_lbl = f"{dn}  {ws}" if ws else dn
        E(f'    {_dot_id(dst_id)} [label="{dst_lbl}" fontname="Courier" fontcolor="#2e7d32"];')

        # Mux 节点 (红色边框菱形, 对标参考图红色标注)
        for mux in tree.sorted_muxes():
            mid = _dot_id(mux.id)
            E(f'    {mid} [label="{mux.label}" shape=diamond '
              f'style=solid color="#c62828" fillcolor=white fontsize=9 penwidth=1.5];')

            for b in mux.branches:
                if b.child is not None:
                    cid = _dot_id(b.child.id)
                    E(f'    {mid} -> {cid} [label="{b.condition}" fontsize=7 fontcolor="#c62828"];')
                else:
                    tid = _dot_id(b.target_node)
                    E(f'    {tid} [label="{b.source_signal}" fontname="Courier" '
                      f'shape=box style=solid color=black fillcolor=white];')
                    E(f'    {mid} -> {tid} [label="{b.condition}" fontsize=7 fontcolor="#c62828"];')

        # 简单条件
        for sc in tree.simples:
            sid = _dot_id(sc.source)
            E(f'    {sid} [label="{sc.source_label}" fontname="Courier"];')
            E(f'    {sid} -> {_dot_id(dst_id)} '
              f'[label="{sc.condition}" fontsize=7 style=dashed color="#2563eb"];')

        E(_CLUSTER_FOOT)

    E(_DOT_FOOTER)
    return "\n".join(out)
