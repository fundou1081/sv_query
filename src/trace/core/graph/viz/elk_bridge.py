"""elk_bridge.py — ELK.js 布局引擎桥接

Python 端从 VizData 产出**完整 ELK JSON**（含 scope 框、stage 分层、port 约束、边样式元数据）。
ELK.js 只做布局计算，不做任何额外处理。

架构原则：
- Python: 从 pyslang AST 提取所有数据 → 完整 ELK JSON
- Node.js: 纯布局计算 (elk.layout())，输出带坐标的 JSON
- Python: 坐标注入回 ELK JSON → SVG 渲染

用法:
    from trace.core.graph.viz.elk_bridge import get_layout
    layout = get_layout(viz_data)
"""

from __future__ import annotations
import json
import subprocess
import os
import sys
from typing import Any

from .viz_data_models import VizData, VizEdge, VizNode


# ═══════════════════════════════════════════════════════════════
# ELK Layout Options（数据流图专用）
# ═══════════════════════════════════════════════════════════════
ELK_OPTIONS = {
    'elk.algorithm': 'layered',
    'elk.direction': 'RIGHT',  # 左→右
    'elk.edgeRouting': 'ORTHOGONAL',  # 直角连线
    # Spacing
    'elk.layered.spacing.nodeNodeBetweenLayers': '80',
    'elk.layered.spacing.edgeNodeBetweenLayers': '20',
    'elk.spacing.nodeNode': '30',
    'elk.spacing.edgeEdge': '10',
    'elk.spacing.portPort': '8',
    # Layered strategy
    'elk.layered.considerModelOrder.strategy': 'PREFER_EDGES',
    'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
    'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
    # Compound graph — 支持嵌套 scope
    'elk.layered.mergeEdges': 'false',
    # Padding
    'elk.padding': '[top=40,left=40,bottom=40,right=40]',
}

# Node size defaults
NODE_SIZE = {'width': 100, 'height': 36}
OP_SIZE = {'width': 24, 'height': 24}

# Symbol mapping
_OP_SYM: dict[str, str] = {
    "Add": "+", "Subtract": "−", "Multiply": "×", "Divide": "÷",
    "BinaryAnd": "&", "BinaryOr": "|", "BinaryXor": "^",
    "GreaterThan": ">", "LessThan": "<", "GreaterThanEqual": "≥",
    "Equality": "=", "Inequality": "≠",
    "ArithmeticShiftRight": ">>>", "LogicalShiftRight": ">>",
    "ArithmeticShiftLeft": "<<<", "LogicalShiftLeft": "<<",
    "LogicalAnd": "&&", "LogicalOr": "||",
    "Ternary": "?:", "Mux": "MUX",
}


def _short(s: str) -> str:
    """提取信号短名"""
    return s.split('.')[-1] if '.' in s else s


def _elk_id(s: str) -> str:
    """生成 ELK 安全的 ID。
    
    ELK 要求 ID 不能以数字开头，不能包含 '.' '$' 等。
    """
    safe = s.replace("'", "_").replace(" ", "_").replace("$", "_").replace(".", "_dot_")
    safe = ''.join(c if c.isalnum() or c in '_-' else '_' for c in safe)
    if safe and safe[0].isdigit():
        safe = 'n_' + safe
    return safe or '_empty'


# ─────────────────────────────────────────────────────────
# 1. VizData → ELK JSON（Python 端产出所有元数据）
# ─────────────────────────────────────────────────────────

def viz_to_elk(viz: VizData) -> dict:
    """将 VizData 转换为完整 ELK graph JSON。
    
    产出结构包含 scope_map 和 stage_map 元数据，传给 SVG 渲染器。
    """
    children = []
    edges = []
    edge_counter = 0
    seen_ids: set[str] = set()
    
    # ── 元数据: scope 框 + stage 分层 ──
    scope_map: dict[str, dict] = {}  # {node_id: {depth, label, member_ids}}
    stage_map: dict[str, int] = {}   # {node_id: stage_number}
    
    def _reg_node(node_id: str, label: str, w: int, h: int,
                  kind: str = 'signal', **meta) -> str:
        """注册一个节点，返回 ELK ID"""
        eid = _elk_id(node_id)
        if eid in seen_ids:
            return eid
        seen_ids.add(eid)
        
        ports = [
            {'id': f'{eid}_in', 'properties': {'port.side': 'WEST'}},
            {'id': f'{eid}_out', 'properties': {'port.side': 'EAST'}},
        ]
        
        node = {
            'id': eid,
            'width': w, 'height': h,
            'labels': [{'text': label, 'fontSize': 10, 'fontName': 'Courier'}],
            'ports': ports,
            '_meta': {'kind': kind, **meta},
        }
        children.append(node)
        return eid
    
    # Phase 1: Signal nodes
    for n in viz.nodes:
        sn = _short(n.id)
        meta = {'kind': n.kind if hasattr(n, 'kind') else 'signal'}
        if n.is_function if hasattr(n, 'is_function') else False:
            meta['is_function'] = True
        _reg_node(n.id, sn, NODE_SIZE['width'], NODE_SIZE['height'], **meta)
    
    # Phase 2: Edges — 先为所有未注册的 src/dst 补建 PORT_IN 节点
    # 数据层可能不导出所有引用信号的节点（特别是 PORT_IN），这里自动补全
    for e in viz.edges:
        if getattr(e, 'kind', '') in ('CLOCK', 'RESET', 'BIT_SELECT'):
            continue
        for ref_id in (e.src, e.dst):
            if _elk_id(ref_id) not in seen_ids:
                _reg_node(ref_id, _short(ref_id), NODE_SIZE['width'], NODE_SIZE['height'])
    
    # Phase 3: Edges — 信号→(OP)→信号
    for e in viz.edges:
        if getattr(e, 'kind', '') in ('CLOCK', 'RESET', 'BIT_SELECT'):
            continue
        
        src_id = _elk_id(e.src)
        dst_id = _elk_id(e.dst)
        
        if getattr(e, 'source_op', None):
            op_kind = e.source_op
            sym = _OP_SYM.get(op_kind, op_kind)
            op_name = f"op_{op_kind}_{_short(e.dst)}"
            op_id = _elk_id(op_name)
            
            # 注册 OP 节点（多输入 port）
            if op_id not in seen_ids:
                seen_ids.add(op_id)
                children.append({
                    'id': op_id,
                    'width': OP_SIZE['width'], 'height': OP_SIZE['height'],
                    'labels': [{'text': sym, 'fontSize': 9, 'fontName': 'Helvetica-Bold'}],
                    'ports': [
                        {'id': f'{op_id}_in1', 'properties': {'port.side': 'WEST'}},
                        {'id': f'{op_id}_in2', 'properties': {'port.side': 'WEST'}},
                        {'id': f'{op_id}_out', 'properties': {'port.side': 'EAST'}},
                    ],
                    '_meta': {'kind': 'op', 'op_kind': op_kind},
                })
            
            # src → OP
            edge_counter += 1
            edges.append({
                'id': f'e{edge_counter}',
                'sources': [src_id], 'targets': [op_id],
                'sourcePort': f'{src_id}_out',
                'targetPort': f'{op_id}_in1',
                '_meta': {'kind': _edge_kind(e)},
            })
            # OP → dst
            edge_counter += 1
            edges.append({
                'id': f'e{edge_counter}',
                'sources': [op_id], 'targets': [dst_id],
                'sourcePort': f'{op_id}_out',
                'targetPort': f'{dst_id}_in',
                '_meta': {'kind': _edge_kind(e)},
            })
        else:
            # 直连边
            edge_counter += 1
            edges.append({
                'id': f'e{edge_counter}',
                'sources': [src_id], 'targets': [dst_id],
                'sourcePort': f'{src_id}_out',
                'targetPort': f'{dst_id}_in',
                '_meta': {'kind': _edge_kind(e)},
            })
    
    # Phase 3: 等价连线（同名信号跨 scope，灰线无箭头）
    if hasattr(viz, 'equiv_edges') and viz.equiv_edges:
        for eq in viz.equiv_edges:
            src_id = _elk_id(eq.src)
            dst_id = _elk_id(eq.dst)
            if src_id in seen_ids and dst_id in seen_ids and src_id != dst_id:
                edge_counter += 1
                edges.append({
                    'id': f'e{edge_counter}',
                    'sources': [src_id], 'targets': [dst_id],
                    'sourcePort': f'{src_id}_out',
                    'targetPort': f'{dst_id}_in',
                    '_meta': {'kind': 'equiv', 'label': _short(eq.src)},
                })
    
    graph = {
        'id': 'root',
        'layoutOptions': dict(ELK_OPTIONS),
        'children': children,
        'edges': edges,
        '_meta': {
            'title': '',
            'scope_map': _build_scope_map(viz),
            'stage_map': _build_stage_map(viz),
        }
    }
    
    return graph


def _edge_kind(e) -> str:
    """推断边类型"""
    ek = getattr(e, 'kind', '')
    if ek:
        return ek.lower()
    if getattr(e, 'is_conditional', False):
        return 'cond'
    return 'signal'


# ─────────────────────────────────────────────────────────
# 2. 调用 ELK.js 做布局计算
# ─────────────────────────────────────────────────────────

def _find_elk_js() -> str:
    """查找 elk_layout.js 脚本路径"""
    dirs = [
        os.path.dirname(__file__),
        os.path.join(os.path.dirname(__file__), '..', '..', 'viz'),
        os.path.join(os.path.dirname(__file__), '..', '..', '..', 'viz'),
    ]
    for d in dirs:
        p = os.path.join(d, 'elk_layout.js')
        if os.path.exists(p):
            return p
    raise FileNotFoundError("Cannot find elk_layout.js")


def _svg_to_png(svg_str: str, dpi: int = 150) -> bytes:
    """SVG 字符串 → PNG bytes。
    
    使用 cairosvg (需 cairo 库)，macOS 上需 DYLD_LIBRARY_PATH=/opt/homebrew/lib。
    自动注入环境变量。
    """
    import cairosvg
    env = os.environ.copy()
    if '/opt/homebrew/lib' not in env.get('DYLD_LIBRARY_PATH', ''):
        env['DYLD_LIBRARY_PATH'] = '/opt/homebrew/lib' + (
            ':' + env['DYLD_LIBRARY_PATH'] if env.get('DYLD_LIBRARY_PATH') else '')
    # cairosvg doesn't take env, use subprocess wrapper
    proc = subprocess.run(
        [sys.executable, '-c', '''
import sys, cairosvg
svg = sys.stdin.buffer.read()
cairosvg.svg2png(bytestring=svg, write_to=sys.stdout.buffer, dpi=''' + str(dpi) + ''')'''],
        input=svg_str.encode('utf-8'),
        capture_output=True,
        timeout=30,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cairosvg failed: {proc.stderr.decode()}")
    return proc.stdout


def run_elk_layout(graph: dict) -> dict:
    """运行 ELK.js 布局计算。
    
    输入: 完整 ELK JSON (无坐标)
    输出: ELK JSON + 坐标 (x, y, width, height, bendPoints)
    """
    script = _find_elk_js()
    input_json = json.dumps(graph, ensure_ascii=False)
    
    proc = subprocess.run(
        ['node', script],
        input=input_json,
        text=True,
        capture_output=True,
        timeout=30,
    )
    
    if proc.returncode != 0:
        raise RuntimeError(f"ELK.js layout failed: {proc.stderr}")
    
    return json.loads(proc.stdout)


# ─────────────────────────────────────────────────────────
# 3. 一站式
# ─────────────────────────────────────────────────────────

def get_layout(viz: VizData) -> dict:
    """VizData → ELK 布局结果（一站式）"""
    elk_graph = viz_to_elk(viz)
    result = run_elk_layout(elk_graph)
    # 保留 _meta 元数据给渲染器
    if '_meta' not in result:
        result['_meta'] = elk_graph.get('_meta', {})
    return result


# ─────────────────────────────────────────────────────────
# 4. 元数据构建 (scope_map / stage_map)
# ─────────────────────────────────────────────────────────

def _build_scope_map(viz: VizData) -> dict:
    """从 VizData 构建 scope 框映射
    
    返回: {scope_id: {depth, label, member_ids: set[str]}}
    member_ids 是 ELK ID 格式（已通过 _elk_id 转换）。
    """
    sm: dict[str, dict] = {}
    
    from collections import defaultdict
    cond_by_dst: dict[str, list] = defaultdict(list)
    for e in viz.edges:
        chain = getattr(e, 'condition_chain', None) or []
        if chain and getattr(e, 'kind', '') not in ('CLOCK', 'RESET', 'BIT_SELECT'):
            cond_by_dst[e.dst].append(e)
    
    scope_idx = 0
    for dst_id, cedges in cond_by_dst.items():
        if len(cedges) < 2:
            continue
        scope_idx += 1
        scope_id = f'scope_{scope_idx}'
        first_cond = getattr(cedges[0], 'condition_chain', [])
        sel_sig = first_cond[0] if first_cond else '?'
        label = f'mux: sel={sel_sig}'
        member_ids: set[str] = set()
        for e in cedges:
            member_ids.add(_elk_id(e.src))
            member_ids.add(_elk_id(e.dst))
        sm[scope_id] = {'depth': 1, 'label': label, 'member_ids': list(member_ids)}
    
    return sm


def _build_stage_map(viz: VizData) -> dict:
    """从 VizData 构建 stage 分层映射，返回 {node_elk_id: stage_number}"""
    try:
        from .viz_engine import infer_stages_bfs
        stages = infer_stages_bfs(viz)
        return {_elk_id(k): v for k, v in stages.items()}
    except ImportError:
        return {}
