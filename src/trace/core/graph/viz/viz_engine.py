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
        # 优先从 sig_op_index 查源信号的常量（三目分支内的信号）
        # 其次从 const_map 查 dst 的常量（直接 wire/assign）
        sn_short = e.src.split('.')[-1] if '.' in e.src else e.src
        dn_short = e.dst.split('.')[-1] if '.' in e.dst else e.dst
        extra_consts = []
        # 从 sig_op_index 查源信号的常量（如 sum_ab + 8'd10 → 8'd10 是 sum_ab 所在的表达式常量）
        if sn_short in dp.get("op_index", {}):
            extra_consts = list(dp["op_index"][sn_short].get('consts', []))
        # 也从 const_map 查 dst 常量
        if dn_short in const_map:
            for c in const_map[dn_short]:
                if c not in extra_consts:
                    extra_consts.append(c)
        for c in extra_consts:
            cid = f"op_const_{c}_{_dot_id(e.dst)}"[:60]
            if cid not in seen_op_nodes:
                seen_op_nodes.add(cid)
                op_registry[cid] = c
            op_edges.append({"src": None, "op_id": oid, "dst": e.dst, "_const_src": cid})
        
        # [V8.3] inner_ops 中的上游信号也连接到 OP 节点
        # 如 sum_ab→z op='Add' 的 inner_ops=['a','b'] — a, b 是原始操作数
        module_prefix = e.dst.rsplit('.', 1)[0] + '.' if '.' in e.dst else ''
        for ioname in getattr(e, "source_inner_ops", []) or []:
            # 跳过符号字符串 (+, -, etc — 这些是 _op_symbol 输出的)
            if len(ioname) <= 2 and not ioname[0].isalpha():
                continue
            inner_id = f"{module_prefix}{ioname}"
            op_edges.append({"src": inner_id, "op_id": oid, "dst": e.dst, "_inner_op": True})

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

    module_name = (config or {}).get("title", "").split()[0] if config else ""
    if module_name:
        E(f'  subgraph cluster_module {{')
        E(f'    label="module: {module_name}"; labeljust=l; fontsize=12; fontname="Helvetica-Bold";')
        E(f'    style=solid; color="#333"; penwidth=2; margin=20;')
        for n in viz.nodes:
            if n.kind in ("PORT_IN", "PORT_OUT"):
                dot_id = _dot_id(n.id)
                sn = _short(n.id)
                ws = _width_label(n)
                lbl = f"{sn}  {ws}" if ws else sn
                fill = "#e8f5e9" if n.kind == "PORT_IN" else "#fff3e0"
                E(f'    {dot_id} [label="{lbl}" fontname="Courier" fontcolor="#2e7d32" shape=box style=solid fillcolor="{fill}"];')
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
        # [V10] 收集本 scope 中出现的分支信号名 (用于后续等价边)
        scope_signals: set[str] = set()
        # [V9] 预计算同 dst 各分支的其他信号操作数 (用于补 scope 内 OP 入边)
        branch_sibling_signals: dict[str, list[str]] = defaultdict(list)
        for e2 in viz.edges:
            e2sn = e2.src.split('.')[-1] if '.' in e2.src else e2.src
            e2dn = e2.dst.split('.')[-1] if '.' in e2.dst else e2.dst
            if e2dn == dst_sn and e2.source_op:
                e2cc = getattr(e2, 'condition_chain', None) or []
                if e2cc:
                    key = chr(10).join(e2cc)  # condition 签名
                    branch_sibling_signals[key].append(e2sn)
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
                scope_signals.add(sn)  # [V10] 收集分支信号名
                nid = _dot_id(f"br{scope_counter[0]}_{sn}")
                # [V9] 匹配源信号+条件+ds中的 VizEdge source_op（区分同信号不同条件）
                edge_op = ''
                matched_cc = []
                br_cond_text = br.condition
                for ee in viz.edges:
                    esn = ee.src.split('.')[-1] if '.' in ee.src else ee.src
                    edn = ee.dst.split('.')[-1] if '.' in ee.dst else ee.dst
                    ee_cc = getattr(ee, 'condition_chain', None) or []
                    ee_cond = ' && '.join(ee_cc) if ee_cc else ''
                    if esn == sn and edn == dst_sn and ee.source_op:
                        if ee_cond == br_cond_text:
                            edge_op = ee.source_op
                            matched_cc = ee_cc
                            break
                ops = [_OP_SYM.get(edge_op, edge_op)] if edge_op else []
                dst_info = sig_op_index.get(dst_sn, {})
                consts = list(dst_info.get('consts', []))
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
                        # [V9] 同条件分支的其他信号作为另一操作数
                        sn_cc_str = chr(10).join(matched_cc) if matched_cc else ''
                        if sn_cc_str and sn_cc_str in branch_sibling_signals:
                            siblings = branch_sibling_signals[sn_cc_str]
                            for sib in siblings:
                                if sib != sn:
                                    sibid = _dot_id(f"scop{scope_counter[0]}_sib_{sib}")
                                    E(f'      {sibid} [label="{sib}" shape=box width=0.2 height=0.2 style=solid color="#2e7d32" fillcolor=white fontsize=7];')
                                    E(f'      {sibid} -> {oid} [style=solid color="#2e7d32"];')
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
        # [V10] 信号等价边: scope 内分支信号 Gbr* ↔ stage 层 G<module>_<sig> 灰线无箭头
        # 从 VizEdge 的 dst 推导 module prefix
        stage_prefix = dst_id.rsplit('.', 1)[0] + '.' if '.' in dst_id else ''
        for sig in scope_signals:
            stage_dot_id = _dot_id(f"{stage_prefix}{sig}")
            # 收集 scope 内该信号的所有分支节点
            scope_br_ids = set()
            for bi2, br2 in enumerate(branches):
                if br2.source_signal:
                    sn2 = _short(br2.source_signal)
                    if sn2 == sig:
                        scope_br_ids.add(_dot_id(f"br{scope_counter[0] - len(branches) + bi2 + 1}_{sn2}"))
            for br_id in scope_br_ids:
                E(f'  {br_id} -> {stage_dot_id} [style=solid color="#9e9e9e" dir=none penwidth=1.5];')
        scope_signals.clear()
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
        
        # [V8.3] _inner_op 边: 上游操作数信号 → OP 节点
        if oe.get("_inner_op"):
            sk = (oe["src"], oid)
            if sk not in seen_src_op:
                seen_src_op.add(sk)
                E(f'  {_dot_id(oe["src"])} -> {_dot_id(oid)} [style=solid color="#2e7d32"];')
            continue
        
        if oe["src"] is not None:
            # 条件信号 → MUX 虚线 (cond/sel 输入)
            if oe.get("_cond_line"):
                sk = (oe["src"], oid)
                if sk not in seen_src_op:
                    seen_src_op.add(sk)
                    E(f'  {_dot_id(oe["src"])} -> {_dot_id(oid)} [style=solid color="#2e7d32" arrowsize=0.6];')
                continue
            # MUX parent→child 内部边
            if oe.get("_mux_internal"):
                sk = (oe["src"], oid)
                if sk not in seen_src_op:
                    seen_src_op.add(sk)
                    E(f'  {_dot_id(oe["src"])} -> {_dot_id(oid)} [style=solid color="#2e7d32"];')
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

    # 非 OP 边 (条件边保留蓝色虚线，不跳过 muxed_pairs)
    for e in viz.edges:
        if e.kind == "BIT_SELECT": continue
        key = (e.src, e.dst)
        if key in data_pairs: continue
        if e.kind in ("CLOCK", "RESET"): continue
        chain = getattr(e, "condition_chain", None) or []
        if chain:
            # [V10] scope 已表达条件选择 — 跳过被 mux 吞并的条件边
            if key in muxed_pairs: continue
            cond = " && ".join(chain)
            if len(cond) > 30: cond = cond[:27] + "..."
            E(f'  {_dot_id(e.src)} -> {_dot_id(e.dst)} '
              f'[label="{cond}" fontsize=7 style=dashed color="#2563eb"];')
        else:
            if key in muxed_pairs: continue  # 无条件 mux 边跳过
            sst = stages.get(e.src, -1)
            dst = stages.get(e.dst, -1)
            is_timed = (sst >= 0 and dst >= 0 and dst > sst)
            E(f'  {_dot_id(e.src)} -> {_dot_id(e.dst)} [style={"solid" if is_timed else "dashed"}];')

    E(_DOT_FOOTER)
    
    # [V10] 闭合 module scope
    if module_name:
        E(f'  }}')  # close cluster_module
    
    dot = "\n".join(out)
    
    # [V8.3] DOT 层校验: 二元 OP 节点入边数必须 ≥ 2
    _validate_dot_binary_ops(dot)
    
    return dot


def _validate_dot_binary_ops(dot: str) -> None:
    """校验 DOT 中每个二元 OP 节点的入边数 ≥ 2，不够就抛 ValueError。"""
    import re
    from collections import defaultdict
    
    BINARY_LABELS = {'+', '−', '×', 'Add', 'Subtract', 'Multiply',
                     '&', '|', '^', '||', '&&', '/', '%'}
    
    # 统计 OP 节点
    op_labels = {}
    for m in re.finditer(r'(\w+)\s*\[label="([^"]+)"[^\]]*width=0\.[12]', dot):
        if m.group(2) in BINARY_LABELS:
            op_labels[m.group(1)] = m.group(2)
    
    # 统计入边
    in_deg: dict[str, list[str]] = defaultdict(list)
    edge_rgx = re.compile(r'(\w+)\s*->\s*(\w+)')
    for m in edge_rgx.finditer(dot):
        src, tgt = m.group(1), m.group(2)
        if tgt in op_labels:
            in_deg[tgt].append(src)
    
    # 检查
    bad = []
    for nid, in_list in in_deg.items():
        if len(in_list) < 2:
            lbl = op_labels[nid]
            srcs = [x.split('_')[-1][:12] for x in in_list]
            bad.append(f"{nid[-45:]} label={lbl} 入边={len(in_list)} from={srcs}")
    
    if bad:
        msg = f"DOT binary OP validation FAILED — {len(bad)} OP node(s) with <2 inputs:\n"
        for line in bad[:20]:
            msg += f"  {line}\n"
        raise ValueError(msg)


def _get_inner_op_signals_for_signal(viz, short_name: str) -> list[str]:
    """从 VizEdge 的入边查信号同级另一操作数信号名。
    
    查找 short_name 作为 dst 时所有带 source_op 的入边，
    把除了 current src 之外的其他入边的 src 信号名返回。
    如 short_name='sum_ab', 入边有 a→sum_ab, b→sum_ab → 返回 ['a','b']。"""
    inner_set = set()
    for edge in viz.edges:
        dst_sn = edge.dst.split('.')[-1] if '.' in edge.dst else edge.dst
        if dst_sn != short_name:
            continue
        if not edge.source_op:
            continue
        src_sn = edge.src.split('.')[-1] if '.' in edge.src else edge.src
        if src_sn not in inner_set:
            inner_set.add(src_sn)
    if inner_set:
        return sorted(inner_set)
    return []


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
