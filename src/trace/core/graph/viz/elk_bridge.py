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
import json, subprocess, os, sys
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
}

def _short(s): return s.split('.')[-1] if '.' in s else s

def _safe(s):
    r = s.replace("'", "_").replace(" ", "_").replace("$", "_").replace(".", "_dot_")
    r = ''.join(c if c.isalnum() or c in '_-' else '_' for c in r)
    if r and r[0].isdigit(): r = 'n_' + r
    return r or '_empty'


def viz_to_elk(viz: VizData) -> dict:
    """VizData → ELK compound graph JSON"""
    ctr = [0]
    def ne(): ctr[0] += 1; return f'e{ctr[0]}'

    # ── Phase 0: Classify edges ──
    cond_by_dst = defaultdict(list)
    regular = []
    for e in viz.edges:
        chain = getattr(e, 'condition_chain', None) or []
        ek = getattr(e, 'kind', '')
        if chain and ek not in ('CLOCK', 'RESET', 'BIT_SELECT'):
            cond_by_dst[e.dst].append(e)
        elif ek not in ('CLOCK', 'RESET', 'BIT_SELECT'):
            regular.append(e)

    input_names, output_name = [], ''
    for n in viz.nodes:
        side = getattr(n, 'port_side', '')
        if side == 'left': input_names.append(_short(n.id))
        elif side == 'right': output_name = _short(n.id)

    root_children = []
    root_edges = []

    # ── Phase 1: PORT_IN nodes (top-level, LEFT column) ──
    for name in input_names:
        root_children.append({
            'id': f'port_{name}', 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': name, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
            '_meta': {'kind': 'port_in'},
        })

    # ── Phase 2: PORT_OUT node (top-level, RIGHT column) ──
    if output_name:
        root_children.append({
            'id': f'port_{output_name}', 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': output_name, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'LAST'},
            '_meta': {'kind': 'port_out'},
        })

    # No conditional edges → simple flat layout
    if not cond_by_dst:
        for n in viz.nodes:
            root_children.append({
                'id': _safe(n.id), 'width': SIG_W, 'height': SIG_H,
                'labels': [{'text': _short(n.id), 'fontSize': 9, 'fontName': 'Courier'}],
                '_meta': {'kind': 'signal'},
            })
        for e in regular:
            root_edges.append({
                'id': ne(), 'sources': [_safe(e.src)], 'targets': [_safe(e.dst)],
                '_meta': {'kind': 'signal'},
            })
        return _make_graph(root_children, root_edges)

    # ── Phase 3: Build compound case/branch scopes ──
    case_children = []
    case_edges = []

    for dst_id, cedges in cond_by_dst.items():
        if len(cedges) < 2:
            for e in cedges:
                root_edges.append({'id': ne(), 'sources': [_safe(e.src)], 'targets': [_safe(e.dst)],
                                   '_meta': {'kind': 'signal'}})
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
                branch_children.append({
                    'id': sid, 'width': SIG_W, 'height': SIG_H,
                    'labels': [{'text': sn, 'fontSize': 9, 'fontName': 'Courier'}],
                    '_meta': {'kind': 'signal'},
                })

            # Branch internal edges (signal → op)
            if op_id:
                for ge in group:
                    sn = _short(ge.src)
                    sid = f'sig_{sn}_{sd}_{sc}'
                    branch_edges.append({
                        'id': ne(), 'sources': [sid], 'targets': [op_id],
                        '_meta': {'kind': 'signal'},
                    })

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
                    root_edges.append({
                        'id': ne(), 'sources': [f'port_{sn}'], 'targets': [sid],
                        '_meta': {'kind': 'signal', 'label': sn},
                    })

            if op_id:
                root_edges.append({
                    'id': ne(), 'sources': [op_id], 'targets': [f'port_{output_name}'] if output_name else [],
                    '_meta': {'kind': 'signal'},
                })
            for ge in group:
                sn = _short(ge.src)
                sid = f'sig_{sn}_{sd}_{sc}'
                if not getattr(ge, 'source_op', None):
                    root_edges.append({
                        'id': ne(), 'sources': [sid], 'targets': [f'port_{output_name}'] if output_name else [],
                        '_meta': {'kind': 'signal'},
                    })

        # sel → case scope (condition select edge)
        # Create a dummy anchor inside case scope so ELK can route the edge
        sel_anchor_id = f'cond_sel_{sd}'
        case_children.append({
            'id': sel_anchor_id, 'width': 120, 'height': 1,
            '_meta': {'kind': 'condition_anchor'},
        })
        for sig in sorted(sel_sigs):
            if sig in input_names:
                root_edges.append({
                    'id': ne(), 'sources': [f'port_{sig}'], 'targets': [sel_anchor_id],
                    '_meta': {'kind': 'condition_select'},
                })

    # ── Phase 4: Assemble case scope ──
    case_id = f'case_{sd}'
    case_node = {
        'id': case_id,
        'labels': [{'text': f'case ({sel_label})', 'fontSize': 10, 'fontName': 'sans-serif'}],
        'layoutOptions': {
            'elk.direction': 'DOWN',
            'elk.padding': '[top=14,left=10,right=10,bottom=8]',
            'elk.spacing.nodeNode': '10',
        },
        'children': case_children,
        'edges': case_edges,
        '_meta': {'kind': 'case', 'label': f'case ({sel_label})'},
    }
    root_children.append(case_node)

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
