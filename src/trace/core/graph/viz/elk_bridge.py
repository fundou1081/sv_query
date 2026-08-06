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
    
    def ne(): ctr[0] += 1; return f'e{ctr[0]}'
    
    def _emit_edge(eid, srcs, tgts, kind='dataflow'):
        return {'id': eid, 'sources': list(srcs), 'targets': list(tgts),
                '_meta': {'kind': kind}}
    
    # Port nodes (排除 CLOCK/RESET)
    for name in sorted(input_set):
        if name in clock_reset_srcs:
            continue
        root_children.append({
            'id': f'port_{name}', 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': name, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
            '_meta': {'kind': 'port_in'},
        })
    for name in sorted(output_set):
        root_children.append({
            'id': f'port_{name}', 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': name, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'LAST'},
            '_meta': {'kind': 'port_out'},
        })
    
    def collect_signals(tree_node, into):
        """递归收集表达式树中所有 SignalRef labels"""
        if not tree_node:
            return
        if tree_node.get('op') == 'SignalRef':
            into.add(tree_node.get('label', ''))
        for c in tree_node.get('children', []):
            collect_signals(c, into)

    def render_ternary(node_id, children, prefix, nc):
        """轻量三元渲染：?: OP 节点 + 条件虚线边

        children[0] = 条件信号 (SignalRef)
        children[1] = true 分支数据
        children[2] = false 分支数据

        效果: 条件信号 → ?: 节点 (灰色虚线, cond 标签)
              true/false 数据 → ?: (普通实线)
        节点 label: ?: (sel_name)
        """
        cond = children[0] if len(children) >= 1 else None
        true_child = children[1] if len(children) >= 2 else None
        false_child = children[2] if len(children) >= 3 else None

        # 收集条件信号名
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
            if sig in input_set:
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

        # true/false 分支数据 → ?: (普通 dataflow 边)
        for child in (true_child, false_child):
            if child:
                child_id = render_tree(child, f'{prefix}_btf')
                if child_id:
                    root_edges.append(_emit_edge(ne(), [child_id], [node_id]))

        return node_id

    def render_tree(tree_node, prefix):
        """递归渲染 ExpressionTree → ELK nodes + edges，返回 node_id"""
        label = tree_node.get('label', '?')
        op = tree_node.get('op', '?')
        children = tree_node.get('children', [])
        nc = len(root_children)
        node_id = f"op_{_safe(label)}_{prefix}_{nc}"
        
        if op == 'SignalRef':
            if label in input_set:
                return f'port_{label}'
            elif label in output_set:
                return f'port_{label}'
            sig_id = f'sig_{_safe(label)}_{nc}'
            existing = [c for c in root_children if c.get('id') == sig_id]
            if not existing:
                root_children.append({
                    'id': sig_id, 'width': SIG_W, 'height': SIG_H,
                    'labels': [{'text': label, 'fontSize': 8, 'fontName': 'Courier'}],
                    '_meta': {'kind': 'signal'},
                })
            return sig_id
        
        if op == 'Const':
            const_id = f'const_{_safe(label)}_{nc}'
            root_children.append({
                'id': const_id, 'width': 40, 'height': SIG_H,
                'labels': [{'text': label, 'fontSize': 8, 'fontName': 'Courier'}],
                'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
                '_meta': {'kind': 'const'},
            })
            return const_id
        
        # ── Ternary: compound case/branch structure ──
        if op == 'Ternary':
            return render_ternary(node_id, children, prefix, nc)
        
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
            child_id = render_tree(child, f"{prefix}_c")
            if child_id:
                root_edges.append(_emit_edge(ne(), [child_id], [node_id]))
        
        return node_id
    
    for dst_name, tree_data in expr_trees.items():
        top_op_id = render_tree(tree_data, dst_name)
        dst_short = _short(dst_name)
        if dst_short in output_set and top_op_id:
            root_edges.append(_emit_edge(ne(), [top_op_id], [f'port_{dst_short}']))
    
    return {
        'id': 'root',
        'properties': dict(ELK_OPTIONS),
        'children': root_children,
        'edges': root_edges,
    }


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
        return _make_graph(root_children, root_edges)

    # ── Phase 3: Build compound case/branch scopes ──
    case_children = []
    case_edges = []

    for dst_id, cedges in cond_by_dst.items():
        dst_short = _short(dst_id)
        if len(cedges) < 2:
            for e in cedges:
                root_edges.append(_emit_edge(ne(), [_safe(e.src)], [_safe(e.dst)], e))
            continue

        sd = _safe(dst_id)
        sel_sigs = set()
        for e in cedges:
            chain = getattr(e, 'condition_chain', [])
            if chain and chain[0].split(): sel_sigs.add(chain[0].split()[0])
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
    for e in list(root_edges):
        if 'targets' in e and not e['targets']:
            root_edges.remove(e)
            print(f"[WARN] removed edge {e['id']}: empty target", file=sys.stderr)

    return _make_graph(root_children, root_edges)


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
