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

    # [V8.2] 数据富化: function标记 + const_map + op_index (从源码读取，不修改边数据)
    _enrich_datapath_info(viz, graph, opts)

    # [V13] Port 节点生成: PORT_IN/PORT_OUT 转为显式 port 节点
    # PORT_IN: 标记 is_port=True, port_side='left', 保留在图中
    # PORT_OUT: 标记 is_port=True, port_side='right', 保留在图中
    # CONST 节点: 如果所有出边都是条件边则过滤 (纯控制信号)
    port_in_has_direct_edge: set[str] = set()
    for e in viz.edges:
        cc = getattr(e, 'condition_chain', None) or []
        if not cc:
            port_in_has_direct_edge.add(e.src)
    for n in viz.nodes:
        if n.kind == "PORT_IN":
            n.is_port = True
            n.port_side = 'left'
        elif n.kind in ("PORT_OUT", "REG"):
            n.is_port = True
            n.port_side = 'right'
    viz.nodes = [n for n in viz.nodes
                 if n.kind != "CONST" or n.id in port_in_has_direct_edge]

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
    
    def _short(s: str) -> str:
        """模块前缀剥离"""
        return s.split(".")[-1] if "." in s else s
    
    dp = {
        "const_map": defaultdict(list),
        "func_nodes": [],
        "func_widths": {},
        "op_index": {},
    }
    
    # 1. 从 SV 源码提取常量 + function 声明 (一次性, 不重复开文件)
    import os as _os_path
    src_files = getattr(opts, 'source_files', None) or []
    if not src_files:
        # 从 VizNode 的 file 属性反查 SV 源码路径
        search_roots = [
            _os_path.getcwd(),
            _os_path.path.join(_os_path.getcwd(), 'sim', 'tests', 'fixtures'),
        ]
        seen_names = set(n.file for n in viz.nodes if n.file)
        for fname in seen_names:
            for root in search_roots:
                for dirpath, dirs, files in _os_path.walk(root):
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules','__pycache__','.git','.venv')]
                    if fname in files:
                        src_files.append(_os_path.path.join(dirpath, fname))
                        break
                if src_files:
                    break
            if src_files:
                break
    
    # 常量提取: 用 VizEdge.expression 中的 assign/wire 行逐行提取常量
    # expression 可能是整个源文件，按行扫描 assign/wire dst=rhs 行，精确匹配每个 dst
    _verilog_const = re.compile(r"\d+'[bdh]\w+")
    _bare_num = re.compile(r'(?<![\[\w])\d+(?![:\w\]])')
    for e in viz.edges:
        expr = getattr(e, 'expression', '') or ''
        if not expr or len(expr) > 10000:
            continue
        dn_s = e.dst.split('.')[-1]
        for line in expr.split('\n'):
            ls = line.strip()
            if ls.startswith('//') or ls.startswith('module') or ls.startswith('input') or ls.startswith('output'):
                continue
            m = re.match(r'(?:assign|wire)\s+(?:\S+\s+)?(\w+)\s*=\s*(.+);', ls)
            if not m:
                continue
            rhs_dst, rhs = m.group(1), m.group(2)
            if rhs_dst != dn_s:
                continue  # only collect consts for this edge's dst
            # Verilog 字面量 (8'd128)
            vc = _verilog_const.findall(rhs)
            for c in vc:
                if c not in dp["const_map"][dn_s]:
                    dp["const_map"][dn_s].append(c)
            # 从 rhs 移除 Verilog 字面量后, 提取纯数字 (2)
            cleaned = _verilog_const.sub('', rhs)
            for c in _bare_num.findall(cleaned):
                if c not in dp["const_map"][dn_s]:
                    dp["const_map"][dn_s].append(c)
    
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
                    consts = CONST_PAT.findall(rhs)
                    if consts: dp["const_map"][dst].extend(consts)
                am = re.match(r'assign\s+(\w+)\s*=\s*(.+);', ls)
                if am:
                    dst, rhs = am.group(1), am.group(2)
                    consts = CONST_PAT.findall(rhs)
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
