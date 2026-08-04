"""elk_svg_renderer.py — ELK.js 布局结果 → SVG 渲染器 (V12)

渲染 ELK layout JSON 为 SVG，支持：
- Signal 节点（矩形，Courier，绿色字）
- OP 节点（小矩形，Bold）
- Scope 框（嵌套 compound nodes，实线）
- Stage cluster（虚线框，每层一个）
- 边样式区分：signal（实线黑）、cond（虚线蓝）、equiv（灰线无箭头）、clk/rst（红线）
- 等价连线标签

颜色方案：
  signal:  #333333
  cond:    #2563eb 虚线
  equiv:   #9e9e9e 无箭头
  clk/rst: #c62828
  op:      #f0f0f0 填充
  scope:   #444444 实线框
  stage:   #2563eb 虚线框
"""

from __future__ import annotations
from typing import Any
from xml.etree import ElementTree as ET
from xml.dom import minidom


# ─────────────────────────────────────────────────────────
# Color palette
# ─────────────────────────────────────────────────────────
C = {
    'bg': '#ffffff',
    'signal': '#333333',
    'cond': '#2563eb',
    'equiv': '#9e9e9e',
    'clk': '#c62828',
    'rst': '#c62828',
    'const': '#1565c0',
    'node_fill': '#ffffff',
    'node_stroke': '#333333',
    'op_fill': '#f0f0f0',
    'op_stroke': '#666666',
    'scope_fill': 'none',
    'scope_stroke': '#444444',
    'scope_label': '#555555',
    'stage_fill': '#f8faff',
    'stage_stroke': '#2563eb',
    'text': '#2e7d32',
    'op_text': '#333333',
    'arrow': '#333333',
    'cond_dasharray': '5,3',
    'equiv_dasharray': '2,4',
}

# Scope frame colors by depth
SCOPE_COLORS = [
    ('#444444', '#fafafa', 2.0),     # module: 实线深灰
    ('#1b5e20', '#f1f8e9', 1.5),     # condition scope: 绿色虚线
    ('#c62828', '#ffebee', 1.2),     # 子分支: 红色虚线
    ('#1565c0', '#e3f2fd', 1.0),     # 更深层
]


def _etree_to_svg(root: ET.Element) -> str:
    """ElementTree → 美化的 SVG 字符串"""
    rough = ET.tostring(root, encoding='unicode')
    return minidom.parseString(rough).toprettyxml(indent='  ')


# ─────────────────────────────────────────────────────────
# 主渲染函数
# ─────────────────────────────────────────────────────────

def render_svg(layout: dict, config: dict | None = None) -> str:
    """ELK 布局结果 → SVG 字符串

    Args:
        layout: ELK.layout() 返回的 JSON
        config: {title, show_stage, scope_map: {child_id: scope_info}, ...}

    Returns:
        格式化 SVG 字符串
    """
    cfg = config or {}
    title = cfg.get('title', 'Dataflow')
    scope_map = cfg.get('scope_map', {})
    stage_map = cfg.get('stage_map', {})
    
    # 计算 SVG 尺寸
    padding = 50
    max_x = max_y = 0
    for child in layout.get('children', []):
        max_x = max(max_x, child.get('x', 0) + child.get('width', 0))
        max_y = max(max_y, child.get('y', 0) + child.get('height', 0))
    svg_w = max(400, max_x + padding * 2)
    svg_h = max(200, max_y + padding * 2)
    
    # SVG root
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    svg = ET.Element('svg', {
        'xmlns': 'http://www.w3.org/2000/svg',
        'width': f'{svg_w}', 'height': f'{svg_h}',
        'viewBox': f'0 0 {svg_w} {svg_h}',
    })
    
    # Defs (arrow markers)
    defs = ET.SubElement(svg, 'defs')
    _add_marker(defs, 'arrow', C['arrow'])
    _add_marker(defs, 'arrow_cond', C['cond'])
    _add_marker(defs, 'arrow_clk', C['clk'])
    _add_marker(defs, 'arrow_equiv', C['equiv'])
    
    # Background
    ET.SubElement(svg, 'rect', {'width': '100%', 'height': '100%', 'fill': C['bg']})
    
    # Title
    t = ET.SubElement(svg, 'text', {
        'x': f'{padding}', 'y': '28',
        'font-family': 'Helvetica, Arial, sans-serif',
        'font-size': '14', 'font-weight': 'bold', 'fill': C['text'],
    })
    t.text = title
    
    # Build child map
    child_map: dict[str, dict] = {}
    for child in layout.get('children', []):
        child_map[child['id']] = child
    
    # 1. Scope 框（z-order: 最底层）
    _draw_scopes(svg, layout, scope_map)
    
    # 2. Stage cluster（z-order: scope 之上）
    _draw_stages(svg, layout, stage_map)
    
    # 3. Edges（z-order: 在节点之下）
    for edge in layout.get('edges', []):
        _draw_edge(svg, edge, child_map)
    
    # 4. Nodes（z-order: 最上层）
    for child in layout.get('children', []):
        _draw_node(svg, child)
    
    return _etree_to_svg(svg)


# ─────────────────────────────────────────────────────────
# Scope / Stage frames
# ─────────────────────────────────────────────────────────

def _draw_scopes(svg: ET.Element, layout: dict, scope_map: dict) -> None:
    """画 scope 框（module / condition scope）"""
    if not scope_map:
        return
    
    # Flatten all children into a bounding box per scope
    scope_children: dict[str, list[dict]] = {}
    for child in layout.get('children', []):
        for scope_id, scope_info in scope_map.items():
            # 检查这个 child 是否属于 scope
            if child['id'] in scope_info.get('member_ids', set()):
                scope_children.setdefault(scope_id, []).append(child)
    
    for scope_id, members in scope_children.items():
        info = scope_map.get(scope_id, {})
        depth = info.get('depth', 0)
        border_color, bg_color, stroke_w = SCOPE_COLORS[min(depth, len(SCOPE_COLORS) - 1)]
        
        if not members:
            continue
        
        # Bounding box
        margin = 12
        min_x = min(c.get('x', 0) for c in members) - margin
        min_y = min(c.get('y', 0) for c in members) - margin
        max_x = max(c.get('x', 0) + c.get('width', 0) for c in members) + margin
        max_y = max(c.get('y', 0) + c.get('height', 0) for c in members) + margin
        
        label = info.get('label', '')
        
        # Background
        if bg_color != 'none':
            ET.SubElement(svg, 'rect', {
                'x': f'{min_x}', 'y': f'{min_y}',
                'width': f'{max_x - min_x}', 'height': f'{max_y - min_y}',
                'fill': bg_color, 'stroke': 'none', 'rx': '6',
            })
        
        # Border (dashed for condition, solid for module)
        is_module = (depth == 0)
        attrs: dict[str, str] = {
            'x': f'{min_x}', 'y': f'{min_y}',
            'width': f'{max_x - min_x}', 'height': f'{max_y - min_y}',
            'fill': 'none', 'stroke': border_color,
            'stroke-width': f'{stroke_w}', 'rx': '6',
        }
        if not is_module:
            attrs['stroke-dasharray'] = '5,3'
        
        ET.SubElement(svg, 'rect', attrs)
        
        # Label
        if label:
            t = ET.SubElement(svg, 'text', {
                'x': f'{min_x + 8}', 'y': f'{min_y - 6}',
                'font-family': 'Helvetica, Arial, sans-serif',
                'font-size': '9' if depth > 0 else '11',
                'font-weight': 'bold' if depth == 0 else 'normal',
                'fill': border_color,
            })
            t.text = label


def _draw_stages(svg: ET.Element, layout: dict, stage_map: dict) -> None:
    """画 Stage cluster（虚线框）"""
    if not stage_map:
        return
    
    stage_children: dict[int, list[dict]] = {}
    for child in layout.get('children', []):
        sid = stage_map.get(child['id'], -1)
        if sid >= 0:
            stage_children.setdefault(sid, []).append(child)
    
    for sid, members in stage_children.items():
        if not members:
            continue
        margin = 16
        min_x = min(c.get('x', 0) for c in members) - margin
        min_y = min(c.get('y', 0) for c in members) - margin - 16  # room for label
        max_x = max(c.get('x', 0) + c.get('width', 0) for c in members) + margin
        max_y = max(c.get('y', 0) + c.get('height', 0) for c in members) + margin
        
        # Background
        ET.SubElement(svg, 'rect', {
            'x': f'{min_x}', 'y': f'{min_y}',
            'width': f'{max_x - min_x}', 'height': f'{max_y - min_y}',
            'fill': C['stage_fill'], 'stroke': 'none', 'rx': '4',
        })
        
        # Border
        ET.SubElement(svg, 'rect', {
            'x': f'{min_x}', 'y': f'{min_y}',
            'width': f'{max_x - min_x}', 'height': f'{max_y - min_y}',
            'fill': 'none', 'stroke': C['stage_stroke'],
            'stroke-width': '1.5', 'rx': '4',
            'stroke-dasharray': '8,4',
        })
        
        # Label
        t = ET.SubElement(svg, 'text', {
            'x': f'{min_x + 8}', 'y': f'{min_y - 6}',
            'font-family': 'Helvetica, Arial, sans-serif',
            'font-size': '10', 'font-weight': 'bold',
            'fill': C['stage_stroke'],
        })
        t.text = f'Stage {sid}'


# ─────────────────────────────────────────────────────────
# Edge drawing
# ─────────────────────────────────────────────────────────

def _draw_edge(svg: ET.Element, edge: dict, child_map: dict) -> None:
    """画一条边"""
    meta = edge.get('_meta', {})
    kind = meta.get('kind', 'signal')
    
    sections = edge.get('sections', [])
    if not sections:
        return
    
    dash = None
    marker_end = None
    
    if kind == 'driver':
        # 驱动边：带箭头实线
        stroke = C['signal']
        marker_end = 'arrow'
    elif kind == 'signal':
        # 信号/等价边：无箭头灰色实线
        stroke = C['equiv']
    elif kind == 'cond':
        dash = C['cond_dasharray']
        stroke = C['cond']
    elif kind == 'equiv':
        dash = C['equiv_dasharray']
        stroke = C['equiv']
    elif kind in ('clk', 'rst'):
        stroke = C.get(kind, C['clk'])
        marker_end = 'arrow_clk'
    
    # 获取源/目标节点（用于钳制端点坐标）
    src_node = child_map.get(edge.get('sources', [None])[0] if edge.get('sources') else None)
    dst_node = child_map.get(edge.get('targets', [None])[0] if edge.get('targets') else None)
    
    def _draw_path(points: list[dict]) -> None:
        if len(points) < 2:
            return
        
        d_parts = [f'M {points[0]["x"]:.1f} {points[0]["y"]:.1f}']
        for pt in points[1:]:
            d_parts.append(f'L {pt["x"]:.1f} {pt["y"]:.1f}')
        
        attrs: dict[str, str] = {
            'd': ' '.join(d_parts),
            'fill': 'none',
            'stroke': stroke,
            'stroke-width': '1.5',
        }
        if dash:
            attrs['stroke-dasharray'] = dash
        if marker_end:
            attrs['marker-end'] = f'url(#{marker_end})'
        
        ET.SubElement(svg, 'path', attrs)
    
    for sec in sections:
        sp = sec.get('startPoint', {})
        ep = sec.get('endPoint', {})
        bps = sec.get('bendPoints', [])
        points = [sp] + list(bps) + [ep]
        _draw_path(points)
    
    # Edge label（等价边标注信号名）
    label = meta.get('label', '')
    if label and sections:
        ep = sections[0].get('endPoint', {})
        t = ET.SubElement(svg, 'text', {
            'x': f'{ep.get("x", 0) - 4:.1f}',
            'y': f'{ep.get("y", 0) - 4:.1f}',
            'text-anchor': 'end',
            'font-family': 'Courier, monospace',
            'font-size': '8', 'fill': stroke,
        })
        t.text = label


# ─────────────────────────────────────────────────────────
# Node drawing
# ─────────────────────────────────────────────────────────

def _draw_node(svg: ET.Element, node: dict) -> None:
    """渲染单个节点"""
    meta = node.get('_meta', {})
    kind = meta.get('kind', 'signal')
    nid = node['id']
    x = node.get('x', 0)
    y = node.get('y', 0)
    w = node.get('width', 100)
    h = node.get('height', 36)
    
    label = ''
    if 'labels' in node and node['labels']:
        label = node['labels'][0].get('text', '')
    
    if kind == 'op':
        # OP 节点 — 小矩形
        ET.SubElement(svg, 'rect', {
            'x': f'{x:.1f}', 'y': f'{y:.1f}',
            'width': f'{w}', 'height': f'{h}',
            'fill': C['op_fill'], 'stroke': C['op_stroke'],
            'stroke-width': '1.2', 'rx': '2',
        })
        font_family = 'Helvetica, Arial, sans-serif'
        font_size = '9'
        font_weight = 'bold'
        fill = C['op_text']
    else:
        # Signal 节点
        ET.SubElement(svg, 'rect', {
            'x': f'{x:.1f}', 'y': f'{y:.1f}',
            'width': f'{w}', 'height': f'{h}',
            'fill': C['node_fill'], 'stroke': C['node_stroke'],
            'stroke-width': '1', 'rx': '3',
        })
        font_family = 'Courier, monospace'
        font_size = '9'
        font_weight = 'normal'
        fill = C['text']
    
    if label:
        t = ET.SubElement(svg, 'text', {
            'x': f'{x + w/2:.1f}',
            'y': f'{y + h/2 + 4:.1f}',
            'text-anchor': 'middle',
            'font-family': font_family,
            'font-size': font_size,
            'font-weight': font_weight,
            'fill': fill,
        })
        t.text = label


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _add_marker(defs: ET.Element, marker_id: str, color: str) -> None:
    """添加箭头 marker"""
    m = ET.SubElement(defs, 'marker', {
        'id': marker_id,
        'viewBox': '0 0 10 10',
        'refX': '9', 'refY': '5',
        'markerWidth': '6', 'markerHeight': '6',
        'orient': 'auto-start-reverse',
    })
    ET.SubElement(m, 'path', {
        'd': 'M 0 0 L 10 5 L 0 10 z',
        'fill': color,
    })
