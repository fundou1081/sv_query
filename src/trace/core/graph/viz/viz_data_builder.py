"""
viz_data_builder.py — SignalGraph → VizData 转换器 (V6.7)

原则:
- 纯数据转换，不做渲染
- 接受 options dict 控制要包含的字段
- 每个画图命令传入不同的 options
"""

from __future__ import annotations

import os
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

        # [V14 2026-08-13] 层级模块折叠: 填充 instance_path / module_type / cluster_id
        # TraceNode.module 取值有两种:
        #   1. PORT_IN/PORT_OUT 节点: 'golden_hier_top.u_scale' (包含 instance 路径)
        #   2. INSTANTIATED_MODULE 节点: 'level2_scale' (只有 module 类型名, inst_path 在 node.id 里)
        node_module = getattr(node, 'module', '') or ''
        target_mod = opts.target_module or ''
        node_id = getattr(node, 'id', '') or ''
        if vn.kind == 'INSTANTIATED_MODULE':
            # INSTANTIATED_MODULE 节点: inst_path 从 node.id 提取 (id 格式: "top.inst_name")
            if target_mod and node_id.startswith(target_mod + '.'):
                inst_path = node_id[len(target_mod) + 1:]
            else:
                inst_path = ''
            # module_type 就是 node.module (例如 'level2_scale')
            vn.instance_path = inst_path
            vn.module_type = node_module
            vn.cluster_id = inst_path
        elif target_mod and node_module.startswith(target_mod + '.'):
            # PORT/SIGNAL 节点: module 含 instance 路径
            inst_path = node_module[len(target_mod) + 1:]
            vn.instance_path = inst_path
            vn.cluster_id = inst_path
        else:
            # 顶层节点
            inst_path = ''
            vn.instance_path = ''
            vn.cluster_id = ''

        # [V16.10 2026-08-17] generate block 解析: 从 node.id 找 gen_blk[i] pattern
        # 范例: 'golden_hier_top.gen_stage1[2].x_temp' → gen_block='gen_stage1', gen_iter='i=2'
        # 范例: 'golden_hier_top.gen_stage2[0].y_reg' → gen_block='gen_stage2', gen_iter='i=0'
        # 顶层: 'golden_hier_top.data' → '', ''
        # 收集 (含子模块内嵌 generate): 'u_scale.gen_stage1[0].p' → gen_block='gen_stage1', gen_iter='i=0'
        import re as _re_v1610
        _gen_block = ''
        _gen_iter = ''
        # 検测 .gen_blk[数字] 模式 (不限顶层)
        _genblk_matches = _re_v1610.findall(r'(gen_[A-Za-z0-9_]+)\[(\d+)\]', node_id)
        if _genblk_matches:
            # 取最后一个 (inner-most generate block)
            _gb_name, _gb_idx = _genblk_matches[-1]
            _gen_block = _gb_name
            _gen_iter = f'i={_gb_idx}'
        vn.gen_block = _gen_block
        vn.gen_iter = _gen_iter

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

    # [V16 Plan Phase 3.2 2026-08-14] 从 expr_trees 提取 const 节点 emit 进 VizData
    # 之前 V16.1 让 const 进 ELK (via expr_trees_to_elk), 但 VizData.nodes 没有 const,
    #  导致 dump 的 viz.json 看不出 const 是否归位到正确 instance cluster.
    # 修复: 遍历 graph._expr_trees, 递归找 op='Const' 节点, 给每个 const 创建 VizNode
    # (kind='CONST', cluster_id=parent instance_path, instance_path=parent instance_path,
    #  module=parent module).
    target_mod = opts.target_module or ''
    expr_trees = getattr(graph, '_expr_trees', {}) or {}
    const_seen: set[tuple[str, str]] = set()  # (instance_path, label) 去重
    for tree_key, tree_dict in expr_trees.items():
        if not isinstance(tree_dict, dict):
            continue
        # tree_key 格式: "{module_name}.{lhs_name}" (e.g. "golden_hier_top.u_clamp.dout")
        # 解析 module 和 lhs
        parts = tree_key.rsplit('.', 1)
        if len(parts) != 2:
            continue
        parent_module_full, lhs_short = parts
        # 计算 instance_path (parent module 相对 target_mod 的路径)
        if target_mod and parent_module_full.startswith(target_mod + '.'):
            inst_path = parent_module_full[len(target_mod) + 1:]
        elif target_mod and parent_module_full == target_mod:
            inst_path = ''  # 顶层
        else:
            # target_mod 为空或 parent_module 不属于 target, 用完整路径
            inst_path = parent_module_full
        # 递归遍历 tree 找 Const 节点
        def _walk_collect_const(node, path):
            if not isinstance(node, dict):
                return
            op = node.get('op')
            lbl = node.get('label')
            if op == 'Const' and lbl:
                key = (inst_path, lbl)
                if key not in const_seen:
                    const_seen.add(key)
                    # [V16 Plan Phase 3.2 2026-08-14] const_id 加 parent instance_path 前缀防重复
                    # 多个 instance 可能有相同 lhs (如 .u_clamp.dout 和 .u_clamp_u.dout),
                    # 需在 const_id 里包含 inst_path 区分.
                    label_safe = lbl.replace(chr(39), '').replace('d', '_d').replace('b', '_b').replace('h', '_h')
                    inst_safe = inst_path.replace('.', '_') if inst_path else 'top'
                    const_id = f"const_n_{inst_safe}_{lhs_short}_{label_safe}"
                    cn = VizNode(
                        id=const_id,
                        label=lbl,
                        full_path=const_id,
                        module=parent_module_full,
                        kind='CONST',
                        cluster_id=inst_path,
                        instance_path=inst_path,
                    )
                    viz.nodes.append(cn)
            for c in node.get('children', []) or []:
                _walk_collect_const(c, path)
        _walk_collect_const(tree_dict, [])

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
                 if n.kind != "CONST"
                 or n.id in port_in_has_direct_edge
                 # [V16 Plan Phase 3.2 2026-08-14] 保留从 expr_trees 提取的 instance 内 const 节点
                 or n.cluster_id
                ]

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
    def _short(s: str) -> str:
        """模块前缀剥离"""
        return s.split(".")[-1] if "." in s else s
    
    dp = {
        "const_map": dict(graph._const_map) if hasattr(graph, "_const_map") else {},
        "func_nodes": [],
        "func_widths": {},
        "op_index": {},
    }

    # [REFACTOR 2026-08-07 A计划] 数据全部从 SignalGraph 获取（semantic AST 已解析）
    # 不再 open().read() + regex 扫源码 / 不再 SyntaxTree.fromText 重解析。
    # DriverExtractor 已填充 graph._expr_trees / _const_map / _func_info。

    # func_names_set + func_widths：从 graph._func_info 读取
    # func_info: {func_name → (msb,lsb)|None}
    func_names_set = set(getattr(graph, "_func_info", {}) or {})
    for fn_name, w in (getattr(graph, "_func_info", {}) or {}).items():
        if w is not None:
            dp["func_widths"][fn_name] = (w[0], w[1])

    # 2. 标记 function 节点
    for n in viz.nodes:
        sn = _short(n.id)
        if sn in func_names_set:
            n.is_function = True
            dp["func_nodes"].append(n.id)
            # 用语义位宽覆盖 pyslang 的不准确宽度
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

    # [REFACTOR 2026-08-07 A计划] expr_trees 从 SignalGraph 读取
    # DriverExtractor 已构建每 lhs 的表达式树（含多分支 max 合并）
    if hasattr(graph, "_expr_trees"):
        dp["expr_trees"] = dict(graph._expr_trees)
    else:
        dp["expr_trees"] = {}

    # [V16.11 2026-08-18] generate block real-label map (pyslang native API)
    # 替代 V16.10.3 启发式: graph._gen_block_map 在 GraphBuilder.build() 末尾已填充
    # key=signal short name (e.g. 'acc', 'buf1'), value=real label (e.g. 'gen_accum', 'gen_stage1')
    if hasattr(graph, "_gen_block_map"):
        dp["gen_block_map"] = dict(graph._gen_block_map)
    else:
        dp["gen_block_map"] = {}
    # [V16.14 F-N3 2026-08-19] 配套 iter map: {signal_short_name 或 'sig[K]' → entry_idx}.
    # 存在两种 key:
    #  - base 名 'acc': setdefault 第一个 entry_idx (case29/30/31 兼容, ElkBridge fallback 用)
    #  - per-element 'acc[1]', 'acc[2]': pyslang selector.constant 拿到的 elaborated index
    #    (case27 主路径, 区分 4 个不同 iter)
    if hasattr(graph, "_gen_iter_map"):
        dp["gen_iter_map"] = dict(graph._gen_iter_map)
    else:
        dp["gen_iter_map"] = {}


