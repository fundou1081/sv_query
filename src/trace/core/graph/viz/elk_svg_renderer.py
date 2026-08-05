"""elk_svg_renderer.py — ELK layout → SVG renderer (V100: Compound Graph)

Renders nested ELK compound graph. Compound nodes = scope boxes (bg + border + label).
Leaf nodes = port/signal/op rectangles. Z-order: scope bg → edges → nodes → scope labels.

Scope colors:
  case:   #f3e5f5 fill, #7b1fa2 solid border
  branch: #f1f8e9 fill, #1b5e20 dashed border
"""

from xml.etree import ElementTree as ET
from xml.dom import minidom

SCOPE_STYLES = {
    'case':   ('#f3e5f5', '#7b1fa2', 1.5, '6', False),
    'branch': ('#f1f8e9', '#1b5e20', 1.2, '4', True),
}

OX, OY = 40, 50

def render_svg(layout: dict, config: dict | None = None) -> str:
    cfg = config or {}
    title = cfg.get('title', '')

    all_leaves = []
    all_compounds = []
    _collect_nodes(layout, all_leaves, all_compounds, is_root=True)

    # Canvas size
    max_x = max_y = 0
    for l in all_leaves:
        max_x = max(max_x, l.get('ax', 0) + l.get('width', 0))
        max_y = max(max_y, l.get('ay', 0) + l.get('height', 0))
    for c in all_compounds:
        max_x = max(max_x, c['ax'] + c.get('width', 0))
        max_y = max(max_y, c['ay'] + c.get('height', 0))
    sw, sh = max(max_x, 200) + OX * 2, max(max_y, 100) + OY * 2

    svg = ET.Element('svg', {
        'xmlns': 'http://www.w3.org/2000/svg',
        'width': f'{sw:.0f}', 'height': f'{sh:.0f}',
        'viewBox': f'0 0 {sw:.0f} {sh:.0f}',
    })
    d = ET.SubElement(svg, 'defs')
    m = ET.SubElement(d, 'marker', {
        'id': 'arrow', 'viewBox': '0 0 10 10',
        'refX': '9', 'refY': '5', 'markerWidth': '6', 'markerHeight': '6',
        'orient': 'auto-start-reverse',
    })
    ET.SubElement(m, 'path', {'d': 'M 0 0 L 10 5 L 0 10 z', 'fill': '#555555'})

    ET.SubElement(svg, 'rect', {'width': '100%', 'height': '100%', 'fill': '#ffffff'})
    if title:
        ET.SubElement(svg, 'text', {
            'x': f'{OX}', 'y': '28', 'font-family': 'sans-serif',
            'font-size': '14', 'font-weight': 'bold', 'fill': '#2e7d32',
        }).text = title

    # Sort compounds: deepest first (inner scopes drawn before outer)
    compounds_sorted = sorted(all_compounds, key=lambda c: -c['depth'])

    # 1. Scope backgrounds + borders
    _draw_scope_bgs(svg, compounds_sorted)

    # 2. Edges
    _draw_edges(svg, layout)

    # 3. Leaf nodes
    _draw_leaves(svg, all_leaves)

    # 4. Scope labels (topmost)
    _draw_scope_labels(svg, compounds_sorted)

    # 5. Sel → case scope edge (SVG direct, not through ELK)
    _draw_sel_to_case_edge(svg, layout, all_leaves, compounds_sorted)

    raw = ET.tostring(svg, encoding='unicode')
    return minidom.parseString(raw).toprettyxml(indent='  ')


def _collect_nodes(node, leaves, compounds, is_root=False, parent_x=0, parent_y=0):
    """Recursively collect leaves and compound nodes with global coordinates."""
    nx = (node.get('x', 0) or 0) + parent_x
    ny = (node.get('y', 0) or 0) + parent_y
    children = node.get('children', [])
    if children:
        if not is_root:
            compounds.append({
                'id': node.get('id', ''), 'ax': nx, 'ay': ny,
                'width': node.get('width', 0), 'height': node.get('height', 0),
                'labels': node.get('labels', []), 'meta': node.get('_meta', {}),
                'depth': _calc_depth(node),
            })
        for c in children:
            _collect_nodes(c, leaves, compounds, parent_x=nx, parent_y=ny)
    else:
        leaves.append({
            'id': node.get('id', ''), 'ax': nx, 'ay': ny,
            'width': node.get('width', 0), 'height': node.get('height', 0),
            'labels': node.get('labels', []), 'meta': node.get('_meta', {}),
        })


def _calc_depth(node):
    children = node.get('children', [])
    if not children: return 0
    return 1 + max(_calc_depth(c) for c in children)


def _draw_scope_bgs(svg, compounds):
    for c in compounds:
        meta = c.get('meta', {})
        kind = 'case' if meta.get('kind') == 'case' else 'branch'
        fill, stroke, sw, rx, dashed = SCOPE_STYLES.get(kind, SCOPE_STYLES['branch'])
        x, y, w, h = c['ax'] + OX, c['ay'] + OY, c.get('width', 0), c.get('height', 0)
        if w <= 0 or h <= 0: continue
        # Background
        ET.SubElement(svg, 'rect', {
            'x': f'{x:.0f}', 'y': f'{y:.0f}',
            'width': f'{w:.0f}', 'height': f'{h:.0f}',
            'fill': fill, 'stroke': 'none', 'rx': rx,
        })
        # Border
        attrs = {'x': f'{x:.0f}', 'y': f'{y:.0f}',
                 'width': f'{w:.0f}', 'height': f'{h:.0f}',
                 'fill': 'none', 'stroke': stroke, 'stroke-width': str(sw), 'rx': rx}
        if dashed: attrs['stroke-dasharray'] = '5,3'
        ET.SubElement(svg, 'rect', attrs)


def _draw_scope_labels(svg, compounds):
    for c in compounds:
        meta = c.get('meta', {})
        kind = 'case' if meta.get('kind') == 'case' else 'branch'
        _, stroke, _, _, _ = SCOPE_STYLES.get(kind, SCOPE_STYLES['branch'])
        labels = c.get('labels', [])
        if not labels: continue
        text = labels[0].get('text', '')
        if not text: continue
        x, y = c['ax'] + OX + 6, c['ay'] + OY + 13
        fs = 10 if kind == 'case' else 8
        fw = 'bold' if kind == 'case' else 'normal'
        ET.SubElement(svg, 'text', {
            'x': f'{x:.0f}', 'y': f'{y:.0f}',
            'font-family': 'sans-serif', 'font-size': str(fs),
            'font-weight': fw, 'fill': stroke,
        }).text = text


def _draw_edges(svg, layout):
    """Draw all edges (collect recursively from all nodes)."""
    all_edges = []
    _collect_edges(layout, all_edges, 0, 0)
    for e in all_edges:
        for sec in e.get('sections', []):
            pts = []
            sp = sec.get('startPoint')
            if sp: pts.append((sp['x'] + OX, sp['y'] + OY))
            for bp in sec.get('bendPoints', []):
                pts.append((bp['x'] + OX, bp['y'] + OY))
            ep = sec.get('endPoint')
            if ep: pts.append((ep['x'] + OX, ep['y'] + OY))
            if len(pts) < 2: continue
            parts = [f'M {pts[0][0]:.1f} {pts[0][1]:.1f}']
            for p in pts[1:]: parts.append(f'L {p[0]:.1f} {p[1]:.1f}')
            ET.SubElement(svg, 'path', {
                'd': ' '.join(parts), 'fill': 'none',
                'stroke': '#555555', 'stroke-width': '1.5', 'marker-end': 'url(#arrow)',
            })


def _collect_edges(node, out, px, py):
    nx = (node.get('x', 0) or 0) + px
    ny = (node.get('y', 0) or 0) + py
    for e in node.get('edges', []):
        # Shift sections from PARENT coordinates to ROOT coordinates
        ec = dict(e)
        shifted_sections = []
        for sec in ec.get('sections', []):
            sc = dict(sec)
            for k in ('startPoint', 'endPoint'):
                if k in sc and sc[k]:
                    sc[k] = {'x': sc[k]['x'] + nx, 'y': sc[k]['y'] + ny}
            sc['bendPoints'] = [{'x': b['x'] + nx, 'y': b['y'] + ny} for b in sc.get('bendPoints', [])]
            shifted_sections.append(sc)
        ec['sections'] = shifted_sections
        out.append(ec)
    for c in node.get('children', []):
        _collect_edges(c, out, nx, ny)


def _draw_leaves(svg, leaves):
    for l in leaves:
        meta = l.get('meta', {})
        kind = meta.get('kind', 'signal')
        x, y = l['ax'] + OX, l['ay'] + OY
        w = l.get('width', 0) or 40
        h = l.get('height', 0) or 20
        labels = l.get('labels', [])
        text = labels[0].get('text', '') if labels else ''

        if kind in ('port_in', 'port_out'):
            ET.SubElement(svg, 'rect', {
                'x': f'{x:.0f}', 'y': f'{y:.0f}',
                'width': f'{w:.0f}', 'height': f'{h:.0f}',
                'fill': '#eeeeee', 'stroke': '#888888', 'stroke-width': '1', 'rx': '3',
            })
            if text:
                ET.SubElement(svg, 'text', {
                    'x': f'{x + w / 2:.0f}', 'y': f'{y + h / 2 + 4:.0f}',
                    'text-anchor': 'middle', 'font-family': 'Courier, monospace',
                    'font-size': '8', 'fill': '#555555',
                }).text = text
        elif kind == 'op':
            ET.SubElement(svg, 'rect', {
                'x': f'{x:.0f}', 'y': f'{y:.0f}',
                'width': f'{w:.0f}', 'height': f'{h:.0f}',
                'fill': '#f0f0f0', 'stroke': '#666666', 'stroke-width': '1', 'rx': '2',
            })
            if text:
                ET.SubElement(svg, 'text', {
                    'x': f'{x + w / 2:.0f}', 'y': f'{y + h / 2 + 4:.0f}',
                    'text-anchor': 'middle', 'font-family': 'Helvetica, Arial, sans-serif',
                    'font-size': '9', 'font-weight': 'bold', 'fill': '#333333',
                }).text = text
        else:
            ET.SubElement(svg, 'rect', {
                'x': f'{x:.0f}', 'y': f'{y:.0f}',
                'width': f'{w:.0f}', 'height': f'{h:.0f}',
                'fill': '#ffffff', 'stroke': '#333333', 'stroke-width': '1', 'rx': '3',
            })
            if text:
                ET.SubElement(svg, 'text', {
                    'x': f'{x + w / 2:.0f}', 'y': f'{y + h / 2 + 4:.0f}',
                    'text-anchor': 'middle', 'font-family': 'Courier, monospace',
                    'font-size': '9', 'fill': '#2e7d32',
                }).text = text


def _draw_sel_to_case_edge(svg, layout, leaves, compounds):
    """Draw sel→case scope stair-step edge directly in SVG (not through ELK).

    Finds port_sel and case scope, then draws:
      port_sel right edge → horizontal 30px → vertical down to case scope top edge.
    """
    # Find port_sel leaf
    port_sel = None
    for l in leaves:
        if l['id'] == 'port_sel':
            port_sel = l
            break
    if not port_sel:
        return

    # Find case scope (depth=2 means case scope in current nesting)
    case_c = None
    for c in compounds:
        if c['meta'].get('kind') == 'case':
            case_c = c
            break
    if not case_c:
        return

    # Port right edge (ROOT coords + SVG offset)
    sx = port_sel['ax'] + port_sel.get('width', 44) + OX
    sy = port_sel['ay'] + port_sel.get('height', 20) / 2 + OY

    # Case scope top edge
    ty = case_c['ay'] + OY
    step_x = sx + 30

    # Stair-step: → right to align with case left → ↓ to case top → → into case
    target_x = case_c['ax'] + OX + 6
    d = f'M {sx:.1f} {sy:.1f} L {target_x:.1f} {sy:.1f} L {target_x:.1f} {ty:.1f} L {target_x + 8:.1f} {ty:.1f}'
    ET.SubElement(svg, 'path', {
        'd': d, 'fill': 'none',
        'stroke': '#555555', 'stroke-width': '1.5',
        'marker-end': 'url(#arrow)',
    })
