"""
viz_data_builder.py — SignalGraph → VizData 转换器 (V6.7)

原则:
- 纯数据转换，不做渲染
- 接受 options dict 控制要包含的字段
- 每个画图命令传入不同的 options
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import SignalGraph
from .viz_data_models import VizData, VizEdge, VizNode


@dataclass
class VizBuildOptions:
    """控制 VizData 构建的选项"""

    # 过滤
    target_module: str = ""  # 目标模块
    max_nodes: int = 0  # 0=不限
    max_edges: int = 0

    # 节点信息
    include_node_class: bool = False  # class_ / classification
    include_node_risk: bool = False  # risk_level / risk_score
    include_node_cover: bool = False  # cover_status
    include_node_stage: bool = False  # stage_id / cycle

    # 边信息
    include_edge_expression: bool = True  # expression / bit_slice / source
    include_edge_condition: bool = True  # condition / clock / reset
    include_edge_cycle: bool = False  # edge_cycle_delta

    # 实例信息 (module/arch 用)
    include_instances: bool = False  # def_name / depth

    # chain 追踪
    input_signals: list[str] = field(default_factory=list)
    output_signals: list[str] = field(default_factory=list)
    critical_path: set[str] = field(default_factory=set)

    # 分类 (从外部注入, 避免循环依赖)
    classification: Any | None = None
    pipeline_stages: Any | None = None


def build_viz_data(
    graph: SignalGraph,
    options: VizBuildOptions | None = None,
) -> VizData:
    """从 SignalGraph 构建统一可视化数据

    Args:
        graph: SignalGraph 实例
        options: 构建选项

    Returns:
        VizData 包
    """
    opts = options or VizBuildOptions()
    viz = VizData(
        meta={
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "target_module": opts.target_module,
        }
    )

    # ── 构建节点 ──
    node_map: dict[str, VizNode] = {}
    for node_id in list(graph.nodes())[:opts.max_nodes] if opts.max_nodes else graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue

        vn = VizNode.from_trace_node(node)

        # 分类 (可选)
        if opts.include_node_class and opts.classification:
            cn = opts.classification.nodes.get(node_id)
            if cn:
                vn.class_ = cn.signal_class.name if cn.signal_class else ""
                vn.class_confidence = cn.confidence if hasattr(cn, "confidence") else 1.0

        # 风险 (可选)
        if opts.include_node_risk:
            _fill_risk(vn, node, graph)

        # coverage (可选)
        if opts.include_node_cover:
            _fill_cover(vn, node_id, graph)

        # pipeline stage (可选)
        if opts.include_node_stage and opts.pipeline_stages:
            # pipeline_stages: {stage_id: [node_ids]}
            for sid, nids in (opts.pipeline_stages or {}).items():
                if node_id in nids:
                    vn.stage_id = sid
                    break

        # chain 标记
        if node_id in opts.input_signals:
            vn.is_input = True
        if node_id in opts.output_signals:
            vn.is_output = True
        if node_id in opts.critical_path:
            vn.is_critical = True

        node_map[node_id] = vn

    viz.nodes = list(node_map.values())

    # ── 构建边 ──
    edge_count = 0
    for src, dst in list(graph.edges()):
        if opts.max_edges and edge_count >= opts.max_edges:
            break

        for edge in graph.get_edges(src, dst):
            if opts.max_edges and edge_count >= opts.max_edges:
                break

            ve = VizEdge.from_trace_edge(edge)

            # 边分类 (从 classification)
            if opts.include_node_class and opts.classification:
                ce = opts.classification.edges.get((src, dst))
                if ce and ce.edge_class:
                    ve.class_ = ce.edge_class.name
                    ve.is_control_edge = (ce.edge_class.name == "CONTROL")

            if not opts.include_edge_expression:
                ve.expression = ""
                ve.bit_slice = ""
                ve.source_signal = ""

            if not opts.include_edge_condition:
                ve.condition = ""
                ve.effective_condition = ""
                ve.clock_domain = ""

            viz.edges.append(ve)
            edge_count += 1

    # [V6.9 datapath] OP passthrough — 中间 wire 的上游 OP 透传到下游边
    _passthrough_op_chain(viz, node_map)
    
    # [V8.2] 数据富化: function标记 + const_map + op_index (为渲染器准备, 不修改原始数据)
    _enrich_datapath_info(viz, graph, opts)

    viz.meta["filtered_node_count"] = viz.node_count
    viz.meta["filtered_edge_count"] = viz.edge_count
    return viz


# ── helpers ──

def _fill_risk(vn: VizNode, node, graph: SignalGraph) -> None:
    """简化的风险评分"""
    fanin = len(list(graph.predecessors(node.id)))
    fanout = len(list(graph.successors(node.id)))
    if fanin >= 5 or fanout >= 5:
        vn.risk_level = "HIGH"
        vn.risk_score = 0.7
    elif fanin >= 3 or fanout >= 3:
        vn.risk_level = "MEDIUM"
        vn.risk_score = 0.4
    else:
        vn.risk_level = "LOW"
        vn.risk_score = 0.1


def _fill_cover(vn: VizNode, node_id: str, graph: SignalGraph) -> None:
    """检查覆盖率标记"""
    node = graph.get_node(node_id)
    if node and node.extra:
        has_sva = bool(node.extra.get("sva"))
        has_cov = bool(node.extra.get("cov"))
        if has_sva and has_cov:
            vn.cover_status = "BOTH"
        elif has_sva:
            vn.cover_status = "SVA"
        elif has_cov:
            vn.cover_status = "COV"


def _passthrough_op_chain(viz: VizData, node_map: dict[str, VizNode]) -> None:
    """[V6.9] 用网络拓扑推导中间 wire 的 OP 信息

    算法: 下游推上游
    1. 对于每个中间 wire W (非 PORT_IN/PORT_OUT/REG):
       a. 收集 W 的入边 (incoming) 和出边 (outgoing)
       b. 如果入边 ≥2 条且都无 source_op:
          - 如果入边=2 → 推导为二元操作 (具体 OP 名无从得知, 标为 "binop")
          - 如果 W 的出边有 source_op → 把该 OP 写入入边的 inner_ops
       c. 入边的 source_op 和 casts 从同行入边补全
    2. 透传到更下游: 对于有 source_op 的出边, 把 src 的入边 OP 作为 inner_ops

    例:
      a → sum_ac [], c → sum_ac []  (2 入边, 无 OP)
      sum_ac → y_round [>>>, inner=[]]  (出边, 有 OP)
      → a → sum_ac [inner=[+]](推导), c → sum_ac [inner=[+]](推导)
      → sum_ac → y_round [>>>, inner=[+]] (透传)
    """
    # Build src → incoming edges index
    incoming: dict[str, list[VizEdge]] = {}
    for e in viz.edges:
        incoming.setdefault(e.dst, []).append(e)

    # ── Phase A: 同位边补全 ──
    # 同一 dst 的多条入边如果来自同一条 assign (如 a+b)，
    # 其中某条边有 op 但另一条没有 → 补全
    for dst_id, in_edges in incoming.items():
        # 收集这个 dst 的所有已知 op
        known_ops: dict[str, str] = {}  # operand_side → op_name
        for ie in in_edges:
            if ie.source_op and ie.source_operand_side:
                known_ops[ie.source_operand_side] = ie.source_op
            elif ie.source_op:
                # Has op but no operand_side — try to infer
                for other_ie in in_edges:
                    if other_ie.source_op and other_ie.source_operand_side:
                        known_ops.setdefault("unknown", ie.source_op)

        if known_ops:
            # Determine the shared op (use majority)
            op_values = list(known_ops.values())
            shared_op = max(set(op_values), key=op_values.count) if op_values else ""
            for ie in in_edges:
                if not ie.source_op:
                    # [V9 FIX] 不扩散 source_op 给无 op 的边
                    # 只共享 casts
                    for other_ie in in_edges:
                        if other_ie.source_casts:
                            if not ie.source_casts:
                                ie.source_casts = list(other_ie.source_casts)
                            break

    # ── Phase B: 下游透传 ──
    # 策略改变: 不仅检查 source_op, 还检查 dst 的所有入边是否构成
    # 某个已知的二元操作数集合。两条边指向同一个中间 wire,
    # ── Phase B: 继承上游 casts，不再透传 source_op ──
    # source_op 只在信号的出生点有意义（如 a→+→sum_ab），
    # 下游边不需要继承——scope 渲染直接从 sig_op_index 查。
    for edge in viz.edges:
        if edge.kind in ("CLOCK", "RESET", "CONNECTION"):
            continue

        src_id = edge.src
        src_node = node_map.get(src_id)
        if src_node is None:
            continue
        if src_node.kind in ("PORT_IN", "PORT_OUT", "REG"):
            continue

        upstream_edges = incoming.get(src_id, [])
        if not upstream_edges:
            continue

        for ue in upstream_edges:
            if not ue.source_op:
                continue
            # 透传 casts
            if not edge.source_casts and ue.source_casts:
                edge.source_casts = list(ue.source_casts)


def _op_symbol(op_name: str) -> str:
    """运算符名 → 可读符号"""
    _MAP = {
        "Add": "+", "Subtract": "-", "Multiply": "*", "Divide": "/",
        "BinaryAnd": "&", "BinaryOr": "|", "BinaryXor": "^",
        "GreaterThan": ">", "LessThan": "<", "GreaterThanEqual": ">=",
        "Equality": "==", "Inequality": "!=",
        "ArithmeticShiftRight": ">>>", "LogicalShiftRight": ">>",
        "ArithmeticShiftLeft": "<<<", "LogicalShiftLeft": "<<",
    }
    return _MAP.get(op_name, op_name)


# ── [V8.3] 二元 OP 输入校验 ──

BINARY_OPS = {"Add", "Subtract", "Multiply", "Divide",
              "BinaryAnd", "BinaryOr", "BinaryXor",
              "GreaterThan", "LessThan", "GreaterThanEqual", "LessThanEqual",
              "Equality", "Inequality",
              "LogicalAnd", "LogicalOr",
              "ArithmeticShiftRight", "ArithmeticShiftLeft",
              "LogicalShiftRight", "LogicalShiftLeft"}


def _validate_binary_op_inputs(viz: VizData) -> list[tuple[str, str, str, set[str]]]:
    """校验每条有 source_op 的 DRIVER 边的操作数 ≥ 2。
    
    返回不符合的边列表 [(src, dst, op, operands), ...]。
    """
    from collections import defaultdict
    
    dp = viz.meta.get("datapath", {})
    op_idx = dp.get("op_index", {})
    const_map = dp.get("const_map", {})
    
    bad: list[tuple[str, str, str, set[str]]] = []
    
    for edge in viz.edges:
        if not edge.source_op or edge.kind != "DRIVER":
            continue
        if edge.source_op not in BINARY_OPS:
            continue
        
        sn = edge.src.split('.')[-1] if '.' in edge.src else edge.src
        dn = edge.dst.split('.')[-1] if '.' in edge.dst else edge.dst
        
        # 收集操作数: 信号 + 常量 + 兄弟信号
        operands = {sn}
        
        si = op_idx.get(sn, {})
        operands.update(si.get('consts', []))
        operands.update(const_map.get(dn, []))
        
        for other in viz.edges:
            if other is edge:
                continue
            s2 = other.src.split('.')[-1] if '.' in other.src else other.src
            if s2 != sn and other.dst == edge.dst and other.kind == "DRIVER":
                operands.add(s2)
        
        if len(operands) < 2:
            bad.append((sn, dn, edge.source_op, operands))
    
    return bad


# ═══════════════════════════════════════════════════════
# [V8.2] 数据富化: function标记 + const_map + op_index
# 从 VizEdge/VizNode 推导, 不修改原始数据字段
# ═══════════════════════════════════════════════════════

def _enrich_datapath_info(viz, graph, opts):
    """在 VizData.meta 中注入渲染需要的富化数据。
    
    存储位置: viz.meta["datapath"] = {
        "const_map": {dst → [const_str, ...]},
        "func_nodes": [node_id, ...],
        "func_widths": {func_name → (msb,lsb)},
        "op_index": {signal_name → {ops, consts}},
    }
    渲染器只读 viz.meta["datapath"], 不解析SV源码, 不修改viz.nodes/edges。
    """
    import re, os as _os
    from collections import defaultdict
    from .viz_engine import _short
    
    dp = {
        "const_map": defaultdict(list),
        "func_nodes": [],
        "func_widths": {},
        "op_index": {},
    }
    
    # 1. 从 SV 源码提取常量 + function 声明 (一次性, 不重复开文件)
    import os as _os_path
    import glob as _glob
    src_files = getattr(opts, 'source_files', None) or []
    if not src_files:
        # 从 VizNode 的 file 属性反查 SV 源码路径
        seen_names = set(n.file for n in viz.nodes if n.file)
        for fname in seen_names:
            # 递归搜索项目目录找匹配的 SV 文件
            for root_prefix in [_os_path.getcwd(), _os_path.path.expanduser('~')]:
                for root, dirs, files in _os_path.walk(root_prefix):
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules','__pycache__','.git')]
                    if fname in files:
                        src_files.append(_os_path.path.join(root, fname))
                        break
                if src_files:
                    break
            if src_files:
                break
    
    func_names_set = set()
    for sp in src_files:
        try:
            with open(sp) as f:
                src_text = f.read()
            # function 声明: function [7:0] add_sat(input ...);
            for m in re.finditer(r'function\s+(?:\[(\d+):(\d+)\]\s+)?(\w+)\s*\(', src_text):
                msb, lsb, fn_name = m.group(1), m.group(2), m.group(3)
                func_names_set.add(fn_name)
                if msb and lsb:
                    dp["func_widths"][fn_name] = (int(msb), int(lsb))
            # 常量: wire/assign 中的 Verilog 字面量
            for line in src_text.split('\n'):
                ls = line.strip()
                wm = re.match(r'(?:wire|logic)\s.*?(\w+)\s*=\s*(.+);', ls)
                if wm:
                    dst, rhs = wm.group(1), wm.group(2)
                    consts = re.findall(r"\d+'[bdh]\w+\b", rhs)
                    if consts: dp["const_map"][dst].extend(consts)
                am = re.match(r'assign\s+(\w+)\s*=\s*(.+);', ls)
                if am:
                    dst, rhs = am.group(1), am.group(2)
                    consts = re.findall(r"\d+'[bdh]\w+\b", rhs)
                    if consts: dp["const_map"][dst].extend(consts)
        except Exception:
            pass
    
    dp["const_map"] = dict(dp["const_map"])
    
    # 2. 标记 function 节点
    for n in viz.nodes:
        sn = _short(n.id)
        if sn in func_names_set:
            n.is_function = True
            dp["func_nodes"].append(n.id)
            # 用源码位宽覆盖 pyslang 的不准确宽度
            if sn in dp["func_widths"]:
                w = dp["func_widths"][sn]
                n.width = (w[0], w[1])
    
    # 3. 构建信号→OP索引 (sig_op_index)
    op_index = dp["op_index"]
    for dst_sig in set(e.dst for e in viz.edges):
        dn_s = dst_sig.split('.')[-1]
        ops_seen = set()
        op_list = []
        for e2 in viz.edges:
            if e2.dst == dst_sig and e2.source_op and e2.source_op not in ops_seen:
                ops_seen.add(e2.source_op)
                op_list.append(e2.source_op)
        consts = dp["const_map"].get(dn_s, [])
        if op_list or consts:
            op_index[dn_s] = {'ops': op_list, 'consts': consts}
    
    viz.meta["datapath"] = dp
