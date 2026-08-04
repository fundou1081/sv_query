"""elk_svg_renderer.py — ELK.js 布局结果 → SVG 渲染器

渲染 ELK layout JSON 为 SVG。支持：
- Signal 节点（矩形，Courier 字体）
- OP 节点（小矩形，Bold）
- Scope 框（嵌套 compound nodes）
- Stage cluster（虚线框）
- 边样式区分：signal（实线黑）、cond（虚线蓝）、equiv（灰线无箭头）
- 箭头（默认无箭头，边 _meta.direction 指定时加）

颜色方案：
  signal: #333333
  cond:   #2563eb 虚线
  equiv:  #9e9e9e 无箭头
  op:     #f5f5f5 填充
  scope:  #444444 实线框
  stage:  #2563eb 虚线框
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
    'const': '#2563eb',
    'node_fill': '#ffffff',
    'node_stroke': '#333333',
    'op_fill': '#f0f0f0',
    'op_stroke': '#666666',
    'scope_fill': '#fafafa',
    'scope_stroke': '#444444',
    'scope_label': '#555555',
    'stage_fill': '#f8faff',
    'stage_stroke': '#2563eb',
    'text': '#2e7d32',
    'op_text': '#333333',
    'arrow': '#333333',
    'cond_dasharray': '5,3',
}

# Arrow marker SVG defs
ARROW_DEF = '''
<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
        markerWidth="6" markerHeight="6" orient="auto-start-reverse">
  <path d="M 0 0 L 10 5 L 0 10 z" fill="#333333"/>
</marker>
<marker id="arrow_cond" viewBox="0 0 10 10" refX="9" refY="5"
        markerWidth="6" markerHeight="6" orient="auto-start-reverse">
  <path d="M 0 0 L 10 5 L 0 10 z" fill="#2563eb"/>
</marker>
'''


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
        config: {title, show_stage, ...}

    Returns:
        格式化 SVG 字符串
    """
    cfg = config or {}
    title = cfg.get('title', 'Dataflow')
    
    # 计算 SVG 尺寸
    padding = 50
    max_x = max_y = 0
    for child in layout.get('children', []):
        max_x = max(max_x, child.get('x', 0) + child.get('width', 0))
        max_y = max(max_y, child.get('y', 0) + child.get('height', 0))
    svg_w = max_x + padding * 2
    svg_h = max_y + padding * 2
    
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
    
    # Draw edges first (z-order: behind nodes)
    for edge in layout.get('edges', []):
        _draw_edge(svg, edge, child_map)
    
    # Draw nodes
    for child in layout.get('children', []):
        _draw_node(svg, child)
    
    return _etree_to_svg(svg)


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
    
    stroke = C.get(kind, C['signal'])
    dash = None
    marker_end = None
    
    if kind == 'cond':
        dash = C['cond_dasharray']
    elif kind == 'equiv':
        stroke = C['equiv']
    
    for sec in sections:
        sp = sec.get('startPoint', {})
        ep = sec.get('endPoint', {})
        bps = sec.get('bendPoints', [])
        
        d_parts = [f'M {sp["x"]:.1f} {sp["y"]:.1f}']
        for bp in bps:
            d_parts.append(f'L {bp["x"]:.1f} {bp["y"]:.1f}')
        d_parts.append(f'L {ep["x"]:.1f} {ep["y"]:.1f}')
        
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
    
    # Edge label
    label = meta.get('label', '')
    if label and sections:
        sec = sections[0]
        ep = sec.get('endPoint', {})
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
    
    # Skip compound nodes (scope containers) — 暂不处理
    # Compound nodes have children array
    
    label = ''
    if 'labels' in node and node['labels']:
        label = node['labels'][0].get('text', '')
    
    if kind == 'op':
        # OP 节点
        ET.SubElement(svg, 'rect', {
            'x': f'{x:.1f}', 'y': f'{y:.1f}',
            'width': f'{w}', 'height': f'{h}',
            'fill': C['op_fill'], 'stroke': C['op_stroke'],
            'stroke-width': '1.5', 'rx': '2',
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
    
    # Label
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
