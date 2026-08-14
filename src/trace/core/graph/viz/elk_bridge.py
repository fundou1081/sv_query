"""elk_bridge.py — ELK.js 布局引擎桥接 (V100: Compound Graph)

V100: 用 ELK 原生 compound graph (INCLUDE_CHILDREN) 实现 scope 嵌套。
ELK 自动计算 case/branch scope 框的尺寸和位置，不再 SVG 后补。

架构:
  root (INCLUDE_CHILDREN, RIGHT)
  ├── PORT_IN nodes (FIRST layer constraint, 左侧列)
  ├── PORT_OUT node (LAST layer constraint, 右侧)
  ├── case scope (compound, 无 w/h, ELK 自算, 紫色实线)
  │   └── branch scopes (compound, 绿色虚线, case 内 DOWN 方向竖排)
  │       ├── signal / op / dummy_out nodes
  │       └── branch 内 edges
  └── 跨层级 edges (PORT_IN→signal, signal/dummy→PORT_OUT)

Edge routing: ELK 原生 orthogonal, cross-hierarchy 自动处理

用法:
    from trace.core.graph.viz.elk_bridge import get_layout
    layout = get_layout(viz_data)
"""

from __future__ import annotations
import json, subprocess, os, sys, re
from collections import defaultdict
from .viz_data_models import VizData


ELK_OPTIONS = {
    'elk.algorithm': 'layered',
    'elk.direction': 'RIGHT',
    'elk.edgeRouting': 'ORTHOGONAL',
    'elk.padding': '[top=20,left=20,right=20,bottom=20]',
    'elk.spacing.nodeNode': '25',
    'org.eclipse.elk.hierarchyHandling': 'INCLUDE_CHILDREN',
}

PORT_W, PORT_H = 44, 20
SIG_W, SIG_H = 50, 24
OP_W, OP_H = 24, 24

_OP_SYM = {
    "Add": "+", "Subtract": "−", "Multiply": "×", "Divide": "÷",
    "BinaryAnd": "&", "BinaryOr": "|", "BinaryXor": "^",
    "GreaterThan": ">", "LessThan": "<", "GreaterThanEqual": "≥",
    "Equality": "=", "Inequality": "≠",
    "ArithmeticShiftRight": ">>>", "LogicalShiftRight": ">>",
    "ArithmeticShiftLeft": "<<<", "LogicalShiftLeft": "<<",
    "LogicalAnd": "&&", "LogicalOr": "||",
    "Ternary": "?:", "Mux": "MUX",
    "Concat": "{}",
}

def _short(s): return s.split('.')[-1] if '.' in s else s

def _safe(s):
    r = s.replace("'", "_").replace(" ", "_").replace("$", "_").replace(".", "_dot_")
    r = ''.join(c if c.isalnum() or c in '_-' else '_' for c in r)
    if r and r[0].isdigit(): r = 'n_' + r
    return r or '_empty'


def expr_trees_to_elk(expr_trees, input_names, output_names, viz=None) -> dict:
    """ExpressionTree dicts → 纯 ELK JSON
    
    把 ExpressionTree 嵌套树转换为 ELK 扁平节点+边。
    输入端口用 FIRST 层约束固定在左边，输出端口用 LAST 固定在右边。
    OP 节点由 ELK 自动分层。
    
    也兼容 viz (VizData) 传入——提取 CLOCK/RESET 端口信息用于过滤。
    """
    root_children = []
    root_edges = []
    input_set = set(input_names)
    output_set = set(output_names)
    ctr = [0]
    
    # ── CLOCK/RESET 端口过滤 (从 viz.edges 提取，路径 A 风格) ──
    clock_reset_srcs = set()
    if viz is not None:
        for e in viz.edges:
            ek = getattr(e, 'kind', '')
            if ek in ('CLOCK', 'RESET'):
                clock_reset_srcs.add(_short(e.src))
        # 也从 node kind 过滤
        for n in viz.nodes:
            if getattr(n, 'kind', '') in ('CLOCK', 'RESET'):
                clock_reset_srcs.add(_short(n.id))
    
    # ── [Plan D1 2026-08-10] 端口 full path 跟踪 ──
    # 背景: 多个端口可能有同名短名 (如 case26 u_scale.din / u_off.din / u_clamp_u.din / u_clamp.din
    # 都是 'din'). 旧逻辑用短名 index 导致 4 个 input port dedup 成 1 个, C4 dedup loss fail.
    # 修复: 从 viz.nodes 提取 full path, 用 full path 作 port ID (短名仅作 label).
    # 同一短名多实例时仍 emit 唯一 ID 端口, SignalRef 根据 parent_module 解析为正确 full path.
    input_paths = []  # full paths of input ports
    output_paths = []  # full paths of output ports
    # [FIX 2026-08-13] full_path → (file, line) 映射, 供 show_source 标注.
    node_source_map = {}  # full_path -> (file, line)
    if viz is not None:
        for _n in viz.nodes:
            _full = str(_n.id)
            _side = getattr(_n, 'port_side', '')
            if getattr(_n, 'file', '') or getattr(_n, 'line', 0):
                node_source_map[_full] = (getattr(_n, 'file', '') or '', getattr(_n, 'line', 0) or 0)
            if _side == 'left':
                input_paths.append(_full)
            elif _side == 'right':
                output_paths.append(_full)
    
    input_short_to_fulls = defaultdict(list)
    for _full in input_paths:
        _sn = _full.rsplit('.', 1)[-1] if '.' in _full else _full
        input_short_to_fulls[_sn].append(_full)
    output_short_to_fulls = defaultdict(list)
    for _full in output_paths:
        _sn = _full.rsplit('.', 1)[-1] if '.' in _full else _full
        output_short_to_fulls[_sn].append(_full)
    
    def _port_id_for_input(full_path):
        """根据 full path 生成端口 ID. 同一短名多实例时用 full path, 其他用短名."""
        _sn = full_path.rsplit('.', 1)[-1] if '.' in full_path else full_path
        if len(input_short_to_fulls[_sn]) > 1:
            return f'port_{_safe(full_path)}'
        return f"port_{_sn}"
    
    def _port_id_for_output(full_path):
        """同样规则: 输出端口 ID."""
        _sn = full_path.rsplit('.', 1)[-1] if '.' in full_path else full_path
        if len(output_short_to_fulls[_sn]) > 1:
            return f'port_{_safe(full_path)}'
        return f"port_{_sn}"
    
    def ne(): ctr[0] += 1; return f'e{ctr[0]}'
    
    def _emit_edge(eid, srcs, tgts, kind='dataflow'):
        return {'id': eid, 'sources': list(srcs), 'targets': list(tgts),
                '_meta': {'kind': kind}}
    
    # 收集 expr_trees 中所有被引用的信号名
    _expr_signal_refs = set()
    for v in expr_trees.values():
        def _collect_sigs(node):
            if node.get('op') == 'SignalRef':
                _expr_signal_refs.add(node['label'])
            for c in node.get('children', []):
                _collect_sigs(c)
        _collect_sigs(v)

    # [Plan D1] 收集 expr_trees 实际引用的 full paths. 只 emit 这些端口, 避免
    # “短名被引用但多 full path”情况下 emit 未连接端口 (orphan leaf).
    # 推导: parent_module = expr_tree key.rsplit('.', 1)[0], SignalRef label →
    # full = parent_module + '.' + label. 检查是否在 input_paths / output_paths 里.
    _referenced_input_fulls = set()
    _referenced_output_fulls = set()
    for _tree_key, _tree_data in expr_trees.items():
        _pm = _tree_key.rsplit('.', 1)[0] if '.' in _tree_key else ''
        def _walk_refs(node, pm=_pm):
            if node.get('op') == 'SignalRef':
                _lbl = node.get('label', '')
                _full = f'{pm}.{_lbl}'
                if _full in input_paths:
                    _referenced_input_fulls.add(_full)
                # 也试 bit slice 去括号后的 full
                _bi = _lbl.find('[')
                if _bi > 0:
                    _full2 = f'{pm}.{_lbl[:_bi]}'
                    if _full2 in input_paths:
                        _referenced_input_fulls.add(_full2)
            for _c in node.get('children', []):
                _walk_refs(_c, pm)
        _walk_refs(_tree_data)
    # outputs: expr_trees key 本身就是输出 full path
    for _tree_key in expr_trees.keys():
        if _tree_key in output_paths:
            _referenced_output_fulls.add(_tree_key)

    # [Plan E2.A 2026-08-10] 保守版 emit: 仅参考 DRIVER 边且两端都是端口的 viz.edges.
    # 背景: 原 E2 (激进版) 任何 viz.edge 引用的端口都 emit, 造成 orphan leaves:
    #   - case24 'b': DRIVER 'b → max2' (max2 不是端口)
    #   - case26 'gain': CONNECTION 'gain → u_scale.gain' (CONNECTION 不渲染)
    # E2.A 收窄: 只有 DRIVER 边两端都是端口才 emit, 避免 function 中间信号和 CONNECTION
    # 造成的 orphan. 真数据流边 (e.g. 'a → y' 或 'data_in → result') 两端都是端口
    # → emit, 不会 orphan.
    # [V15 2026-08-13 注] 跨 instance 的 CONNECTION 边 (u_scale.dout → scaled → u_off.din)
    # 走另外的 post-process 阶段, 在 expr_trees_to_elk 返回后额外补上 (见 _emit_cross_instance_edges).
    if viz is not None:
        _input_path_set = set(input_paths)
        _output_path_set = set(output_paths)
        _all_port_paths = _input_path_set | _output_path_set
        for _e in viz.edges:
            _kind_str = str(_e.kind) if not isinstance(_e.kind, str) else _e.kind
            if _kind_str != 'DRIVER':
                continue  # 只考虑真数据流 DRIVER 边
            _src_str = str(_e.src)
            _dst_str = str(_e.dst)
            # 两端都是端口才考虑 (避免 case24 'b' orphan - DRIVER 'b → mul2' 中 mul2 不是端口)
            if _src_str not in _all_port_paths or _dst_str not in _all_port_paths:
                continue
            if _src_str in _input_path_set:
                _referenced_input_fulls.add(_src_str)
            elif _src_str in _output_path_set:
                _referenced_output_fulls.add(_src_str)
            if _dst_str in _input_path_set:
                _referenced_input_fulls.add(_dst_str)
            elif _dst_str in _output_path_set:
                _referenced_output_fulls.add(_dst_str)

    # Port nodes: 只渲染在 expr_trees 中被引用的 port (排除 CLOCK/RESET)
    # 排除孤悬的 input port (threshold, mode, valid, en 等未在数据流表达式中出现的)
    # [Plan D1] 用 full path 作 ID (短名仅作 label), 避免 dedup loss.
    _emitted_port_ids = set()
    for _full in sorted(_referenced_input_fulls):
        _sn = _full.rsplit('.', 1)[-1] if '.' in _full else _full
        if _sn in clock_reset_srcs:
            continue
        _pid = _port_id_for_input(_full)
        if _pid in _emitted_port_ids:
            continue
        _fl = node_source_map.get(_full, ('', 0))
        root_children.append({
            'id': _pid, 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': _sn, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
            '_meta': {'kind': 'port_in', 'file': _fl[0], 'line': _fl[1]},
        })
        _emitted_port_ids.add(_pid)
    for _full in sorted(_referenced_output_fulls):
        _sn = _full.rsplit('.', 1)[-1] if '.' in _full else _full
        _pid = _port_id_for_output(_full)
        if _pid in _emitted_port_ids:
            continue
        _fl = node_source_map.get(_full, ('', 0))
        root_children.append({
            'id': _pid, 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': _sn, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'LAST'},
            '_meta': {'kind': 'port_out', 'file': _fl[0], 'line': _fl[1]},
        })
        _emitted_port_ids.add(_pid)
    
    def collect_signals(tree_node, into):
        """递归收集表达式树中所有 SignalRef labels"""
        if not tree_node:
            return
        if tree_node.get('op') == 'SignalRef':
            into.add(tree_node.get('label', ''))
        for c in tree_node.get('children', []):
            collect_signals(c, into)

    def render_ternary(node_id, children, prefix, nc, parent_module=''):
        """轻量三元渲染：?: OP 节点 + 条件虚线边

        children[0] = 条件信号 (SignalRef)
        children[1] = true 分支数据
        children[2] = false 分支数据

        效果: 条件信号 → ?: 节点 (灰色虚线, cond 标签)
              true/false 数据 → ?: (普通实线)
        节点 label: ?: (sel_name)

        [Plan D1 2026-08-10] parent_module: 上下文传递给 child render_tree.

        [V16 Plan Phase 1.3 2026-08-14] 修正: cond 是表达式树 (e.g. > (din, 11'd255)),
        之前 V15 只收集 cond_sigs 然后直接 emit 虚线边, 丢失 cond 内部的 op 和 const 节点
        (e.g. > op, 11'd255). 修复: 递归 render_tree 渲染 cond 子树, 双重 emit (虚线边 + 节点).
        """
        cond = children[0] if len(children) >= 1 else None
        true_child = children[1] if len(children) >= 2 else None
        false_child = children[2] if len(children) >= 3 else None

        # 收集条件信号名 (仅 SignalRef)
        cond_sigs = set()
        if cond:
            collect_signals(cond, cond_sigs)
        sel_label = ', '.join(sorted(cond_sigs)) if cond_sigs else '?'

        # ?: OP 节点
        op_w = max(OP_W, len(sel_label) * 8 + 20)
        root_children.append({
            'id': node_id, 'width': op_w, 'height': OP_H,
            'labels': [{'text': f'?: ({sel_label})', 'fontSize': 9, 'fontName': 'Helvetica-Bold'}],
            '_meta': {'kind': 'op'},
        })

        # 条件信号 → ?: 节点 (虚线 cond 边)
        for sig in sorted(cond_sigs):
            # [Plan D1] 尝试 full path 解析
            if parent_module and sig in input_short_to_fulls and len(input_short_to_fulls[sig]) > 1:
                full_path = f"{parent_module}.{sig}"
                if full_path in input_paths:
                    src_id = f'port_{_safe(full_path)}'
                else:
                    src_id = f'port_{sig}'
            elif sig in input_set:
                src_id = f'port_{sig}'
            else:
                sig_id = f'sig_{_safe(sig)}_{nc}'
                existing = any(c.get('id') == sig_id for c in root_children)
                if not existing:
                    root_children.append({
                        'id': sig_id, 'width': SIG_W, 'height': SIG_H,
                        'labels': [{'text': sig, 'fontSize': 8, 'fontName': 'Courier'}],
                        '_meta': {'kind': 'signal'},
                    })
                src_id = sig_id
            root_edges.append(_emit_edge(ne(), [src_id], [node_id], kind='condition_select'))

        # [V16 Plan Phase 1.3 2026-08-14] 递归渲染 cond 子树 (e.g. > (din, 11'd255))
        # 产生 > op 节点和 11'd255 const 节点, 这些之前丢失
        if cond and cond.get('op') not in ('SignalRef',):
            # cond 是表达式 (如 GreaterThan), 递归 render
            cond_op_id = render_tree(cond, f'{prefix}_cond', parent_module=parent_module)
            if cond_op_id:
                # 让 cond op 节点 → ?: 也连一条 dataflow 边 (不仅 cond_sigs 虚线)
                root_edges.append(_emit_edge(ne(), [cond_op_id], [node_id]))

        # true/false 分支数据 → ?: (普通 dataflow 边)
        for child in (true_child, false_child):
            if child:
                child_id = render_tree(child, f'{prefix}_btf', parent_module=parent_module)
                if child_id:
                    root_edges.append(_emit_edge(ne(), [child_id], [node_id]))

        return node_id

    # 已渲染的中间信号缓存: signal_short_name -> node_id
    _signal_cache = {}

    def render_tree(tree_node, prefix, parent_module=''):
        """递归渲染 ExpressionTree → ELK nodes + edges，返回 node_id

        [Plan D1 2026-08-10] parent_module: 从 expr_tree key 推导的父路径
        (如 'golden_hier_top.u_scale' for key 'golden_hier_top.u_scale.dout').
        用于 SignalRef 上下文感知 — 同名短名 'din' 在不同 parent_module 下
        指向不同 full path, 必须区分以避免 dedup loss.
        """
        label = tree_node.get('label', '?')
        op = tree_node.get('op', '?')
        children = tree_node.get('children', [])
        nc = len(root_children)
        node_id = f"op_{_safe(label)}_{prefix}_{nc}"

        if op == 'SignalRef':
            # [Plan D1] 优先用 parent_module + label 推导 full path.
            # 多个同短名 input port 时, 这个 full path 才能定位正确端口.
            if parent_module and label in input_short_to_fulls and len(input_short_to_fulls[label]) > 1:
                full_path = f"{parent_module}.{label}"
                if full_path in input_paths:
                    return f'port_{_safe(full_path)}'
            if parent_module and label in output_short_to_fulls and len(output_short_to_fulls[label]) > 1:
                full_path = f"{parent_module}.{label}"
                if full_path in output_paths:
                    return f'port_{_safe(full_path)}'
            # Fallback: 短名只在只有一个实例时使用
            if label in input_set:
                return f'port_{label}'
            elif label in output_set:
                return f'port_{label}'
            # 如果该信号有自己的表达式树（中间 wire），渲染表达式树后
            # 连接一个带信号名的标签节点（→ sum → 下游引用）
            # expr_trees keys 格式: module.signal → 需要短名匹配
            # 同时支持 prod[15:8] → 去 [...] 后缀匹配 prod 中间 wire
            _match_label = label
            _bracket_idx = label.find('[')
            if _bracket_idx > 0:
                _match_label = label[:_bracket_idx]
            # 先查缓存（带后缀匹配）
            if _match_label in _signal_cache:
                return _signal_cache[_match_label]
            if label in _signal_cache:
                return _signal_cache[label]
            matched_tree = None
            for ek, ev in expr_trees.items():
                ek_short = ek.rsplit('.', 1)[-1]
                if ek_short == label or ek_short == _match_label:
                    matched_tree = ev
                    break
            if matched_tree is not None:
                # 先查缓存
                if label in _signal_cache:
                    return _signal_cache[label]
                if _match_label in _signal_cache:
                    return _signal_cache[_match_label]
                # [Plan D1] matched_tree 递归: 新的 parent_module 是 matched_tree key 的父路径
                _matched_key = None
                for _ek, _ev in expr_trees.items():
                    _ek_short = _ek.rsplit('.', 1)[-1]
                    if _ev is matched_tree:
                        _matched_key = _ek
                        break
                _matched_parent = _matched_key.rsplit('.', 1)[0] if _matched_key else parent_module
                op_id = render_tree(matched_tree, f'{prefix}_wire', parent_module=_matched_parent)
                if op_id:
                    # 如果 op_id 就是 sig_id（可能是递归匹配的缓存结果），直接返回
                    if op_id.startswith('sig_'):
                        _signal_cache[_match_label] = op_id
                        _signal_cache[label] = op_id
                        return op_id
                    # 创建信号标签节点，OP 输出连到这里
                    sig_id = f'sig_{_safe(_match_label)}_expr'
                    existing = [c for c in root_children if c.get('id') == sig_id]
                    if existing:
                        _signal_cache[_match_label] = sig_id
                        _signal_cache[label] = sig_id
                        return sig_id
                    # [V16 Plan Phase 1.4 2026-08-14] sig 节点归位: cluster_id = parent_module (去 target_module 前缀)
                    _target_mod_sig = (viz.meta or {}).get('target_module', '') if viz is not None else ''
                    _sig_cluster_id = parent_module
                    if _target_mod_sig and _sig_cluster_id.startswith(_target_mod_sig + '.'):
                        _sig_cluster_id = _sig_cluster_id[len(_target_mod_sig) + 1:]
                    root_children.append({
                        'id': sig_id, 'width': SIG_W, 'height': SIG_H,
                        'labels': [{'text': _match_label, 'fontSize': 8, 'fontName': 'Courier'}],
                        '_meta': {'kind': 'signal', 'cluster_id': _sig_cluster_id or ''},
                    })
                    root_edges.append(_emit_edge(ne(), [op_id], [sig_id]))
                    _signal_cache[_match_label] = sig_id
                    _signal_cache[label] = sig_id
                    return sig_id
            sig_id = f'sig_{_safe(label)}_{nc}'
            existing = [c for c in root_children if c.get('id') == sig_id]
            if not existing:
                # [V16 Plan Phase 1.4 2026-08-14] sig 节点归位: cluster_id = parent_module (去 target_module 前缀)
                _target_mod_sig2 = (viz.meta or {}).get('target_module', '') if viz is not None else ''
                _sig_cluster_id2 = parent_module
                if _target_mod_sig2 and _sig_cluster_id2.startswith(_target_mod_sig2 + '.'):
                    _sig_cluster_id2 = _sig_cluster_id2[len(_target_mod_sig2) + 1:]
                root_children.append({
                    'id': sig_id, 'width': SIG_W, 'height': SIG_H,
                    'labels': [{'text': label, 'fontSize': 8, 'fontName': 'Courier'}],
                    '_meta': {'kind': 'signal', 'cluster_id': _sig_cluster_id2 or ''},
                })
            return sig_id
        
        if op == 'Const':
            const_id = f'const_{_safe(label)}_{nc}'
            # [V16 Plan Phase 1.1 2026-08-14] const 节点归位: cluster_id = parent_module
            # 例: level2_clamp.u_clamp.dout 的 expr 树里 11'd255 的 parent_module = 'golden_hier_top.u_clamp'
            # → const 归到 u_clamp cluster (短名), 而不是顶层 cluster_target_top
            # 注: viz.meta.target_module 是 'golden_hier_top', 需去掉前缀匹配 VizNode.cluster_id 短名规则
            _target_mod = (viz.meta or {}).get('target_module', '') if viz is not None else ''
            _cluster_id = parent_module
            if _target_mod and _cluster_id.startswith(_target_mod + '.'):
                _cluster_id = _cluster_id[len(_target_mod) + 1:]
            _meta = {'kind': 'const', 'cluster_id': _cluster_id or ''}
            root_children.append({
                'id': const_id, 'width': 40, 'height': SIG_H,
                'labels': [{'text': label, 'fontSize': 8, 'fontName': 'Courier'}],
                'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
                '_meta': _meta,
            })
            return const_id
        
        # ── Ternary: compound case/branch structure ──
        if op == 'Ternary':
            return render_ternary(node_id, children, prefix, nc, parent_module=parent_module)
        
        # Operator node
        op_w = OP_W
        if op == 'Call':
            op_w = max(OP_W + len(label) * 6, 50)
        op_h = OP_H + max(0, (len(children) - 2) * 8)
        
        root_children.append({
            'id': node_id, 'width': op_w, 'height': op_h,
            'labels': [{'text': label, 'fontSize': 9, 'fontName': 'Helvetica-Bold'}],
            '_meta': {'kind': 'op'},
        })
        
        for child in children:
            child_id = render_tree(child, f"{prefix}_c", parent_module=parent_module)
            if child_id:
                root_edges.append(_emit_edge(ne(), [child_id], [node_id]))
        
        return node_id
    
    for dst_name, tree_data in expr_trees.items():
        dst_short = _short(dst_name)
        # [Plan D1] 推导 parent_module: expr_tree key 的父路径
        # 如 'golden_hier_top.u_scale.dout' → parent_module = 'golden_hier_top.u_scale'
        _parent_module = dst_name.rsplit('.', 1)[0] if '.' in dst_name else ''
        # 中间 wire (非 input 非 output): 创建 sig 标签节点 + 渲染表达式树
        if dst_short not in output_set and dst_short not in input_set:
            sig_id = f'sig_{_safe(dst_short)}_wire'
            root_children.append({
                'id': sig_id, 'width': SIG_W, 'height': SIG_H,
                'labels': [{'text': dst_short, 'fontSize': 8, 'fontName': 'Courier'}],
                '_meta': {'kind': 'signal'},
            })
            _signal_cache[dst_short] = sig_id
            op_id = render_tree(tree_data, f'wire_{dst_short}', parent_module=_parent_module)
            if op_id:
                root_edges.append(_emit_edge(ne(), [op_id], [sig_id]))
            continue
        # Output port: 渲染树 + 连到 port
        top_op_id = render_tree(tree_data, dst_name, parent_module=_parent_module)
        if dst_short in output_set and top_op_id:
            # [Plan D1] 用 full path port ID
            _out_port_id = _port_id_for_output(dst_name)
            root_edges.append(_emit_edge(ne(), [top_op_id], [_out_port_id]))

    result = {
        'id': 'root',
        'properties': dict(ELK_OPTIONS),
        'children': root_children,
        'edges': root_edges,
    }
    # [V14 2026-08-13] 层级模块折叠 cluster 重组
    return _wrap_into_clusters(viz, result)


# ═══════════════════════════════════════════════════════════════════
# [V14 2026-08-13] 层级模块折叠 cluster 重组
# ═══════════════════════════════════════════════════════════════════
# 背景: case26 等层级设计需要把 4 个 instance 装进各自的 cluster 框
# (浅蓝边框), 顶层 target module 装进虚线框, CONNECTION 边走红线
# (D2 决策: 只给 CROSS_TOP 加红线).
# 重塑 root_children: 按 VizNode.cluster_id 重组为嵌套 cluster 结构.
# ═══════════════════════════════════════════════════════════════════

def _wrap_into_clusters(viz, elk_json):
    """按 VizNode.cluster_id 把 root_children 重组为嵌套 cluster 框.

    输入: 扁平 root_children (case26: 23 节点)
    输出: 嵌套 children 列表, 每个 instance 一个 cluster, 顶层 target 一个虚线框 cluster.

    重要: ELK compound graph 可以让子节点用自己原始的 id 引用, 不需要
    重写为 cluster id — ELK 会自动查找 hierarchy. 所以我们只重塑 children
    树结构, 不动 edge 端点.

    阶段 5 (CONNECTION 边红色): 只加 meta.stroke, 不重写 src/dst.
    """
    from collections import defaultdict
    root_children = elk_json.get('children', [])
    root_edges = elk_json.get('edges', [])

    if not viz or not viz.nodes:
        return elk_json

    # ── 1. 按 cluster_id 分组 ──
    # ELK 节点 id 可能是 'port_data_in' (顶层) 或 'port_golden_hier_top_dot_u_scale_dot_din' (子模块)
    # 从 ELK 节点 id 反推 VizNode 用 _safe 反向映射 (port_<safe_full_path>)
    clusters = defaultdict(list)
    # 构造 full_path → cluster_id 映射
    fp_to_cid = {}
    for n in viz.nodes:
        fp_to_cid[str(n.id)] = getattr(n, 'cluster_id', '') or ''

    def _child_cluster(child):
        cid = str(child.get('id', ''))
        # 'port_xxx' 形式 — 从 xxx 反推
        if cid.startswith('port_'):
            port_part = cid[5:]
            # 检查是否含 '_dot_' (子模块多短名) — 'golden_hier_top_dot_u_scale_dot_din'
            if '_dot_' in port_part:
                # 拼回 full path: 'golden_hier_top.u_scale.din'
                fp = port_part.replace('_dot_', '.')
                # 尝试匹配最长 VizNode.id
                for vp in sorted(fp_to_cid.keys(), key=len, reverse=True):
                    if fp.endswith(vp) or fp == vp:
                        return fp_to_cid[vp]
                return ''
            else:
                # 顶层 port, e.g. 'data_in' → 'golden_hier_top.data_in'
                for vp, vc in fp_to_cid.items():
                    if vp.endswith('.' + port_part):
                        return vc
                return ''
        # 'op___full_path' 形式 (e.g. 'op___golden_hier_top.u_scale.dout_15')
        if cid.startswith('op__'):
            # 提取 'golden_hier_top.u_scale.dout_15' (去掉末尾 _<n>)
            m = cid[4:]
            # 去末尾 _<数字> 尼竞作 id
            import re as _re
            m2 = _re.sub(r'_\d+$', '', m)
            # 变成 full path
            fp = m2.replace('_dot_', '.')
            for vp in sorted(fp_to_cid.keys(), key=len, reverse=True):
                if fp.endswith(vp) or fp == vp:
                    return fp_to_cid[vp]
            return ''
        # 'sig_<label>_<n>' 形式
        if cid.startswith('sig_'):
            label = cid[4:].rsplit('_', 1)[0]
            for vp, vc in fp_to_cid.items():
                if vp.endswith('.' + label.replace('_dot_', '.')):
                    return vc
            return ''
        # 'const_<label>_<n>' 形式
        # [V16 Plan Phase 1.2 2026-08-14] const 节点归位: 读 _meta.cluster_id (Phase 1.1 写入)
        # 之前硬编码 return '' 是错的: V15 假设 const 总是顶层, 但实际 const 属于
        # 父 expression tree 所在 instance (e.g. 11'd255 在 u_clamp 内部, 应该在 u_clamp cluster)
        if cid.startswith('const_'):
            # 在 root_children 里找到对应节点, 读 _meta.cluster_id
            for child in root_children:
                if str(child.get('id', '')) == cid:
                    return str(child.get('_meta', {}).get('cluster_id', ''))
            return ''  # fallback
        return ''  # 未知 → 顶层

    for child in root_children:
        matched_cid = _child_cluster(child)
        clusters[matched_cid].append(child)

    # ── 2. 构造每个 cluster 的 child wrapper ──
    new_children = []
    cluster_id_to_elk_id = {}

    # [V14 2026-08-13 回归修复] 只在 viz 真的包含子模块时 (有 cluster_id != '')
    # 才包 cluster_target_top 虚线框. 纯顶层 case (如 case1-25 多数)
    # 不包顶层 cluster, 避免给 checker compounds 期望数 +1 的 regression.
    has_submodules = any(cid for cid in clusters if cid)

    if clusters[''] and has_submodules:
        cluster_id_to_elk_id[''] = 'cluster_target_top'
        target_label = ''
        for n in viz.nodes:
            if getattr(n, 'cluster_id', '') == '':
                target_label = n.module or ''
                break
        if not target_label and viz.meta:
            target_label = viz.meta.get('target_module', 'target')
        new_children.append({
            'id': 'cluster_target_top',
            'labels': [{'text': target_label, 'fontSize': 10}],
            'borderStyle': 'dashed',
            '_meta': {'is_cluster': True, 'is_target': True, 'cluster_id': ''},
            'children': clusters[''],
            # [V15 2026-08-13 修复] 删硬编码 width/height — 让 ELK 自动算 cluster 尺寸.
            # 之前设 (200,150) / (180,130) 让多个 cluster 子节点 layout 到相同相对坐标,
            # 出现 sp/ep 重叠 → SVG 看起来"重复 path".
        })
    elif clusters['']:
        # 纯顶层 case: 保持扁平, 不加 wrapper
        for child in clusters['']:
            new_children.append(child)

    for cid in sorted(k for k in clusters if k):
        mod_type = ''
        for n in viz.nodes:
            if getattr(n, 'cluster_id', '') == cid and getattr(n, 'module_type', ''):
                mod_type = n.module_type
                break
        label_text = f'{mod_type}  {cid}' if mod_type else cid
        elk_cluster_id = f'cluster_{_safe(cid)}'
        cluster_id_to_elk_id[cid] = elk_cluster_id
        new_children.append({
            'id': elk_cluster_id,
            'labels': [{'text': label_text, 'fontSize': 10}],
            'borderStyle': 'solid',
            '_meta': {'is_cluster': True, 'is_target': False, 'cluster_id': cid,
                      'module_type': mod_type, 'instance_path': cid},
            'children': clusters[cid],
            # [V15 2026-08-13 修复] 删硬编码 width/height — 让 ELK 自动算 cluster 尺寸.
        })

    # ── 3. 不重写 edge 端点 (ELK compound 自动处理)
    # 只加 _meta.stroke = 'red' 给 CROSS_TOP 边 (D2 决策)
    # 检测方法: src 或 dst 在顶层 cluster, 且另边在子模块 cluster
    new_edges = []
    # 构造 eid → cluster_id 映射
    eid_to_cid = {}
    for cid, items in clusters.items():
        for child in items:
            eid_to_cid[str(child.get('id', ''))] = cid
    for e in root_edges:
        meta = dict(e.get('_meta', {}))
        # 阶段 5: CROSS_TOP 边检测 (不论什么 kind, 只要跨顶层/子模块)
        src_id = (e.get('sources', ['']) or [''])[0]
        dst_id = (e.get('targets', ['']) or [''])[0]
        src_cid = eid_to_cid.get(src_id, '')
        dst_cid = eid_to_cid.get(dst_id, '')
        is_cross_top = (src_cid == '' and dst_cid != '') or (dst_cid == '' and src_cid != '')
        if is_cross_top:
            meta['stroke'] = 'red'
            meta['cross_top'] = True
        new_e = dict(e)
        new_e['_meta'] = meta
        new_edges.append(new_e)

    elk_json = dict(elk_json)
    elk_json['children'] = new_children
    elk_json['edges'] = new_edges
    return elk_json


def viz_to_elk(viz: VizData) -> dict:
    """VizData → ELK compound graph JSON"""
    ctr = [0]
    def ne(): ctr[0] += 1; return f'e{ctr[0]}'

    # ── Phase 0: Classify edges (only for case/if compound graph) ──
    cond_by_dst = defaultdict(list)
    for e in viz.edges:
        chain = getattr(e, 'condition_chain', None) or []
        ek = getattr(e, 'kind', '')
        if chain and ek not in ('CLOCK', 'RESET', 'BIT_SELECT'):
            cond_by_dst[e.dst].append(e)

    input_names, output_names = [], []
    # Identify clock/reset ports to exclude from dataflow display
    _clock_reset_srcs = set()
    for e in viz.edges:
        ek = getattr(e, 'kind', '')
        if ek in ('CLOCK', 'RESET'):
            _clock_reset_srcs.add(_short(e.src))
    for n in viz.nodes:
        side = getattr(n, 'port_side', '')
        if side == 'left' and _short(n.id) not in _clock_reset_srcs:
            input_names.append(_short(n.id))
        elif side == 'right':
            output_names.append(_short(n.id))

    root_children = []
    root_edges = []

    # Local edge helper (Phase 3 compound graph uses this)
    def _emit_edge(eid, srcs, tgts, edge_obj=None, kind='signal'):
        meta = {'kind': kind}
        if edge_obj is not None:
            at = getattr(edge_obj, 'assign_type', '') or ''
            if at:
                meta['assign_type'] = at
        return {'id': eid, 'sources': list(srcs), 'targets': list(tgts), '_meta': meta}

    # ── Phase 1: PORT_IN nodes (top-level, LEFT column) ──
    for name in input_names:
        root_children.append({
            'id': f'port_{name}', 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': name, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
            '_meta': {'kind': 'port_in'},
        })

    # ── Phase 2: PORT_OUT nodes (top-level, RIGHT column) ──
    for name in output_names:
        root_children.append({
            'id': f'port_{name}', 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': name, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'LAST'},
            '_meta': {'kind': 'port_out'},
        })
    output_set = set(output_names)

    # ── No non-cond path: ExpressionTree handles dataflow via expr_trees_to_elk() ──
    # 如果没有任何条件边，返回一个空图（数据流由 expr_trees_to_elk 处理）
    if not cond_by_dst:
        return _wrap_into_clusters(viz, _make_graph(root_children, root_edges))

    # ── Phase 3: Build compound case/branch scopes ──
    # [FIX 2026-08-08] case_children / case_edges 必须在循环内重置,
    # 否则两个 case_node 共享同一个 list, 导致每个 case 框都包含全部
    # dst 的分支 (跨 case 的 sig 节点指向同一个 box, ELK 渲染出孤儿).
    case_edges = []

    for dst_id, cedges in cond_by_dst.items():
        case_children = []  # ← 每个 dst 独立 list
        dst_short = _short(dst_id)
        if len(cedges) < 2:
            for e in cedges:
                # [FIX 2026-08-09 方案1] ID 映射: port_in/port_out 使用
                # 'port_<short>' 格式 (与 Phase 1/2 emit 一致), 其他使用
                # _safe(<full_id>). 原代码无差别 _safe 总是产生 'if_case_function_dot_a',
                # 但 children 里只有 'port_a' → ELK 报 "Referenced shape does not exist".
                src_short = _short(e.src)
                dst_short_e = _short(e.dst)
                src_id = f'port_{src_short}' if src_short in input_names else _safe(e.src)
                tgt_id = f'port_{dst_short_e}' if dst_short_e in output_names else _safe(e.dst)
                # 注: 'endpoint 未在 root_children 中' 的防御性 filter 移到末尾统一处理,
                # 这里不逐个 filter (避免里应一致问题)
                root_edges.append(_emit_edge(ne(), [src_id], [tgt_id], e))
            continue

        sd = _safe(dst_id)
        sel_sigs = set()
        # [FIX 2026-08-08] 收集整个 condition_chain 中所有信号名
        # 原代码只取 chain[0], 丢掉了嵌套条件中的 sel_b 等
        # 例: chain=['sel_a', 'sel_b'] 只取 'sel_a' → 两个 case 框 label 重复
        sig_pat = re.compile(r'\b\w+\b')
        for e in cedges:
            chain = getattr(e, 'condition_chain', [])
            for c in chain:
                # 提取所有 ident (排除 'sel' 等关键字需要上下文, 这里仅提取 ident)
                for tok in sig_pat.findall(c):
                    # 排除常见 noise words
                    if tok not in ('and', 'or', 'not', 'select'):
                        sel_sigs.add(tok)
        sel_label = ', '.join(sorted(sel_sigs)) if sel_sigs else '?'

        by_cond = defaultdict(list)
        for e in cedges:
            chain = getattr(e, 'condition_chain', [])
            key = chain[-1] if chain else 'default'
            by_cond[key].append(e)

        sig_counter = [0]

        for cond_label, group in by_cond.items():
            sc = _safe(cond_label)
            bid = f'branch_{sd}_{sc}'
            branch_children = []
            branch_edges = []

            # OP node (if any in this group)
            op_id = None
            op_seen = set()
            for ge in group:
                op = getattr(ge, 'source_op', None)
                if op and op not in op_seen:
                    op_seen.add(op)
                    op_id = f'op_{_safe(op)}_{sd}_{sc}'
                    branch_children.append({
                        'id': op_id, 'width': OP_W, 'height': OP_H,
                        'labels': [{'text': _OP_SYM.get(op, op), 'fontSize': 9,
                                    'fontName': 'Helvetica-Bold'}],
                        '_meta': {'kind': 'op'},
                    })

            # Signal nodes (dedup within branch)
            seen_sigs = set()
            for ge in group:
                sn = _short(ge.src)
                sid = f'sig_{sn}_{sd}_{sc}'
                if sid in seen_sigs: continue
                seen_sigs.add(sid)
                # Check if signal name is a Verilog constant literal
                _is_const_val = bool(re.match(r"\d+'[bdh]\w+", sn))
                branch_children.append({
                    'id': sid, 'width': 40 if _is_const_val else SIG_W, 'height': SIG_H,
                    'labels': [{'text': sn, 'fontSize': 8 if _is_const_val else 9,
                                'fontName': 'Courier'}],
                    '_meta': {'kind': 'const' if _is_const_val else 'signal'},
                    'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'} if _is_const_val else {},
                })

            # Branch internal edges (signal → op)
            if op_id:
                for ge in group:
                    sn = _short(ge.src)
                    sid = f'sig_{sn}_{sd}_{sc}'
                    branch_edges.append(_emit_edge(ne(), [sid], [op_id], ge))

            case_children.append({
                'id': bid,
                'labels': [{'text': cond_label, 'fontSize': 8, 'fontName': 'sans-serif'}],
                'layoutOptions': {
                    'elk.direction': 'RIGHT',
                    'elk.padding': '[top=16,left=10,right=10,bottom=8]',
                    'elk.spacing.nodeNode': '12',
                },
                'children': branch_children,
                'edges': branch_edges,
                '_meta': {'kind': 'branch', 'label': cond_label},
            })

            # Root edges: PORT_IN → branch signal, signal/op → PORT_OUT
            for ge in group:
                sn = _short(ge.src)
                sid = f'sig_{sn}_{sd}_{sc}'
                # PORT_IN → signal
                if sn in input_names:
                    root_edges.append(_emit_edge(ne(), [f'port_{sn}'], [sid], ge))

            if op_id:
                root_edges.append(_emit_edge(ne(), [op_id], [f'port_{dst_short}'] if dst_short in output_set else []))
            for ge in group:
                sn = _short(ge.src)
                sid = f'sig_{sn}_{sd}_{sc}'
                if not getattr(ge, 'source_op', None):
                    root_edges.append(_emit_edge(ne(), [sid], [f'port_{dst_short}'] if dst_short in output_set else [], ge))

        # sel → case scope (condition select edge)
        sel_anchor_id = f'cond_sel_{sd}'
        case_children.insert(0, {
            'id': sel_anchor_id, 'width': 1, 'height': 1,
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
            '_meta': {'kind': 'condition_anchor'},
        })
        for sig in sorted(sel_sigs):
            if sig in input_names:
                root_edges.append(_emit_edge(ne(), [f'port_{sig}'], [sel_anchor_id], kind='condition_select'))

        # Phase 4: Assemble case scope
        case_node = {
            'id': f'case_{sd}',
            'labels': [{'text': f'case ({sel_label})', 'fontSize': 10, 'fontName': 'sans-serif'}],
            'layoutOptions': {
                'elk.direction': 'DOWN',
                'elk.padding': '[top=14,left=0,right=10,bottom=8]',
                'elk.spacing.nodeNode': '10',
            },
            'children': case_children,
            'edges': case_edges,
            '_meta': {'kind': 'case', 'label': f'case ({sel_label})'},
        }
        root_children.append(case_node)

    # Filter out edges with empty targets (ELK rejects them)
    # [FIX 2026-08-09 方案1 拓展] 也过滤掉 endpoints 不在任何已 emit 节点里的 root edge.
    # 背景: viz_to_elk 只 emit port_in/port_out 作为 root children, 但 viz.edges 可能引用
    # 中间信号 (case20 sum / case23 s2), 函数名 (case21 mul2/div2), 实例端口 (case26 din[7:0])
    # 等. 这些引用在 ELK JSON 里会报 "Referenced shape does not exist".
    # 防御性 filter: 递归收集所有已 emit 节点 ID (含 case compound 内部), 跳过不在其中的 src/tgt.
    # 关键: ELK 允许跨层级引用 (root edge 可以连到 case compound 内部节点), 所以收集必须递归.
    def _collect_all_emitted_ids(node, acc):
        """递归收集 ELK JSON 节点下所有已 emit 的 ID (含嵌套 children 和 ports)."""
        if isinstance(node, dict):
            if 'id' in node:
                acc.add(node['id'])
            for c in node.get('children', []) or []:
                _collect_all_emitted_ids(c, acc)
            for p in node.get('ports', []) or []:
                if 'id' in p:
                    acc.add(p['id'])
    all_emitted_ids = set()
    for c in root_children:
        _collect_all_emitted_ids(c, all_emitted_ids)

    for e in list(root_edges):
        if 'targets' in e and not e['targets']:
            root_edges.remove(e)
            print(f"[WARN] removed edge {e['id']}: empty target", file=sys.stderr)
            continue
        # 检查 src/tgt 是否在递归收集的已 emit ID 里 (允许跨层级引用)
        srcs = e.get('sources', [])
        tgts = e.get('targets', [])
        if any(s not in all_emitted_ids for s in srcs) or any(t not in all_emitted_ids for t in tgts):
            root_edges.remove(e)
            print(f"[WARN] removed edge {e['id']}: endpoint not in emitted nodes "
                  f"(src={srcs}, tgt={tgts})", file=sys.stderr)

    return _wrap_into_clusters(viz, _make_graph(root_children, root_edges))


def _make_graph(children, edges):
    ml = children[0].get('labels', [{}])[0].get('text', '') if children else ''
    return {
        'id': 'root',
        'layoutOptions': dict(ELK_OPTIONS),
        'children': children,
        'edges': edges,
        '_meta': {'title': '', 'target_module': ml},
    }


def _find_elk_js():
    for d in [os.path.dirname(__file__),
              os.path.join(os.path.dirname(__file__), '..', '..', 'viz'),
              os.path.join(os.path.dirname(__file__), '..', '..', '..', 'viz')]:
        p = os.path.join(d, 'elk_layout.js')
        if os.path.exists(p): return p
    raise FileNotFoundError("Cannot find elk_layout.js")


def run_elk_layout(graph):
    proc = subprocess.run(['node', _find_elk_js()],
        input=json.dumps(graph, ensure_ascii=False),
        text=True, capture_output=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"ELK layout failed: {proc.stderr[:500]}")
    return json.loads(proc.stdout)


def get_layout(viz):
    elk = viz_to_elk(viz)
    result = run_elk_layout(elk)
    if '_meta' not in result: result['_meta'] = elk.get('_meta', {})
    return result


# ═══════════════════════════════════════════════════
# [Plan B 2026-08-10] 统一 ELK 路由 helper
# ═══════════════════════════════════════════════════

def _compute_routing(viz):
    """跟 render_dataflow 同步的路由判断 — 返回 (path_name, has_uncond_op, has_call_edge, has_cond_edges, expr_trees).

    path_name ∈ {'expr_trees', 'viz_to_elk'}
    """
    raw_expr_trees = viz.meta.get('datapath', {}).get('expr_trees', {})
    expr_trees = dict(raw_expr_trees)

    has_uncond_op = any(
        getattr(e, 'source_op', None) and not (getattr(e, 'condition_chain', None) or [])
        and getattr(e, 'kind', '') not in ('CLOCK', 'RESET', 'BIT_SELECT')
        for e in viz.edges
    )
    has_call_edge = any(
        getattr(e, 'source_op', None) == 'Call'
        for e in viz.edges
    )
    has_cond_edges = any(
        (getattr(e, 'condition_chain', None) or []) or getattr(e, 'condition', None)
        for e in viz.edges
    )
    return raw_expr_trees, expr_trees, has_uncond_op, has_call_edge, has_cond_edges


def _compute_input_output_names(viz):
    """跟 render_dataflow 同步的 input/output names 提取."""
    input_names, output_names = [], []
    for n in viz.nodes:
        side = getattr(n, 'port_side', '')
        name = str(n.id).rsplit('.', 1)[-1] if '.' in str(n.id) else str(n.id)
        if side == 'left':
            input_names.append(name)
        elif side == 'right':
            output_names.append(name)
    return input_names, output_names


def _build_elk_for_viz(viz):
    """根据 viz.edges 路由, 构建 render_dataflow 将使用的 ELK JSON.

    跟 viz_engine.render_dataflow 完全同步 — checker/test 调这个函数取 layout,
    可以保证 SVG 和 layout 永远匹配 (不走跟 render 不同的 ELK 路径).

    Returns: dict (ELK JSON, 还未调 run_elk_layout)
    """
    raw_expr_trees, expr_trees, has_uncond_op, has_call_edge, has_cond_edges = _compute_routing(viz)

    # 路径 1: 数据运算边 / 函数调用 → expr_trees_to_elk
    if has_uncond_op or has_call_edge:
        if expr_trees:
            input_names, output_names = _compute_input_output_names(viz)
            elk = expr_trees_to_elk(expr_trees, input_names, output_names, viz=viz)
            # [V15 fix 6] 之前这里 return, 跳过 post-process. 改为赋值 + 走末尾统一 post-process
        else:
            # 没 expr_trees 但有 call edge — 退回 viz_to_elk
            elk = viz_to_elk(viz)
    # 路径 2: case/if 条件边 → viz_to_elk (case compound)
    elif has_cond_edges:
        elk = viz_to_elk(viz)
    # 路径 3: 纯 expr_trees (无 cond, 无 uncond op) → expr_trees_to_elk
    elif expr_trees:
        input_names, output_names = _compute_input_output_names(viz)
        elk = expr_trees_to_elk(expr_trees, input_names, output_names, viz=viz)
    # 路径 4: fallback — viz_to_elk (保证有输出)
    else:
        elk = viz_to_elk(viz)

    # [V15 2026-08-13 修复] 补全跨 instance CONNECTION 边 (适用于所有路径)
    # 原 expr_trees_to_elk 和 viz_to_elk 都不 emit 跨 module 的 CONNECTION 边:
    #   u_scale.dout → scaled → u_off.din 这样的 instance→instance 连线.
    # 原因: E2.A 规则不 emit CONNECTION 边, 但跨 instance 的 CONNECTION (instance port → wire
    # 或 wire → instance port) 是必要的. 这里 post-process 补上这些边.
    # [V15 fix 2] 移到所有路径之后, case26 (expr_trees=0) 也能触发.
    # [V15 fix 6] 路径 1 原本有 return, 跳过 post-process. 修复后统一走末尾.
    if viz is not None:
        elk = _emit_cross_instance_connection_edges(elk, viz)
    return elk


def _emit_cross_instance_connection_edges(elk_json: dict, viz) -> dict:
    """[V15 2026-08-13] 补全跨 instance 的 CONNECTION 边.

    背景: case26 源码有 u_scale.dout → scaled → u_off.din 这样的 instance→instance 连线,
    但 expr_trees_to_elk 只 emit expression tree 渲染的边, 漏了这些.

    [V15 fix 3] 策略调整: 不在 ELK emit 中间 wire 节点 (sig_scaled_wire), 因为
    _wrap_into_clusters 会把不属于任何 cluster 的 root_children 节点剥掉. 改为:
    - 跳 过中间 wire 节点 (scaled/offsetted/clamped_w/clamped)
    - 找 'X.dout → wire → Y.din' 这种两步 CONNECTION, 拼为 'X.dout → Y.din' 一步 emit
    - 这样 ELK 会画出 instance→instance 的直接连线 (一条黑线/红线)
    """
    from collections import defaultdict
    if not viz or not viz.edges:
        return elk_json

    # 1. 收集 input/output port 集合 (避免重复 emit)
    _input_paths = set()
    _output_paths = set()
    for n in viz.nodes:
        side = getattr(n, 'port_side', '')
        if side == 'left':
            _input_paths.add(n.id)
        elif side == 'right':
            _output_paths.add(n.id)
    _all_top_ports = _input_paths | _output_paths

    # 2. 收集 instance port 集合 (cluster_id != '' 且 port_side != '')
    _instance_ports = set()
    for n in viz.nodes:
        cid = getattr(n, 'cluster_id', '') or ''
        side = getattr(n, 'port_side', '') or ''
        if cid and side:
            _instance_ports.add(n.id)

    # 3. 收集 CONNECTION 边, 构建 instance_port → instance_port 映射
    # 思路: 'X.dout → wire → Y.din' 是两条边 (X.dout→wire, wire→Y.din)
    # 拼成 X.dout→Y.din
    # 步骤 3a: 收集 wire 节点 (顶层 port 不算)
    # [V15 fix 4] 关键: instance port (e.g. 'golden_hier_top.u_scale.dout') 同时在
    # _all_top_ports 里 (因为 port_side='right' 也算 output port). 需要扣除.
    _real_top_ports = _all_top_ports - _instance_ports  # 只含 target module 顶层 port
    _wire_to_dsts = defaultdict(list)  # wire → [Y.din]
    _srcs_to_wire = defaultdict(list)  # X.dout → [wire]
    for e in viz.edges:
        ek = str(e.kind) if not isinstance(e.kind, str) else e.kind
        if ek != 'CONNECTION':
            continue
        s, t = str(e.src), str(e.dst)
        s_is_inst = s in _instance_ports
        t_is_inst = t in _instance_ports
        s_is_top = s in _real_top_ports
        t_is_top = t in _real_top_ports
        if s_is_inst and not t_is_inst and not t_is_top:
            # 'X.dout → wire' (wire 不是 instance port 也不是真顶层 port)
            _srcs_to_wire[s].append(t)
        elif t_is_inst and not s_is_inst and not s_is_top:
            # 'wire → Y.din'
            _wire_to_dsts[s].append(t)

    # 3b. 拼接: X.dout → wire → Y.din → emit X.dout → Y.din
    root_edges = elk_json.get('edges', [])
    existing_edge_keys = set()
    for e in root_edges:
        for s in e.get('sources', []):
            for t in e.get('targets', []):
                existing_edge_keys.add((s, t))

    ctr = [int(root_edges[-1]['id'][1:]) if root_edges else 0]
    def _ne():
        ctr[0] += 1
        return f'e{ctr[0]}'

    added = 0
    for src_inst, wires in _srcs_to_wire.items():
        for wire in wires:
            for dst_inst in _wire_to_dsts.get(wire, []):
                # 拼接 X.dout → Y.din (跨 instance 一步)
                s_id = _map_to_elk_id(src_inst, _instance_ports, set(), _all_top_ports)
                t_id = _map_to_elk_id(dst_inst, _instance_ports, set(), _all_top_ports)
                if not s_id or not t_id:
                    continue
                if (s_id, t_id) in existing_edge_keys:
                    continue
                # 跨 instance CONNECTION 用紫色 (区分于 CROSS_TOP 红)
                root_edges.append({
                    'id': _ne(),
                    'sources': [s_id],
                    'targets': [t_id],
                    '_meta': {
                        'kind': 'connection',
                        'stroke': 'purple',  # [V15 阶段 6] 跨 instance 连线紫色
                        'v15_added': True,
                    },
                })
                existing_edge_keys.add((s_id, t_id))
                added += 1

    if added:
        elk_json['edges'] = root_edges
    return elk_json


def _map_to_elk_id(path, _instance_ports, _wire_nodes, _all_top_ports):
    """[V15 2026-08-13] 把 viz_data path 映射到 ELK 节点 id."""
    # [V15 fix 5] 顺序调整: 先查 instance port (e.g. 'golden_hier_top.u_scale.dout' 也在
    # _all_top_ports 里, 因为 port_side='right' 让它既是 instance port 又是 output port).
    # 必须先匹配 instance port 拿到 full-path id, 不然会走 'port_dout' 短名分支.
    if path in _instance_ports:
        return 'port_' + path.replace('.', '_dot_')
    if path in _all_top_ports:
        return f'port_{path.rsplit(".", 1)[-1]}' if '.' in path else f'port_{path}'
    if path in _wire_nodes:
        short = path.rsplit('.', 1)[-1] if '.' in path else path
        return f'sig_{short}_wire'
    return None
