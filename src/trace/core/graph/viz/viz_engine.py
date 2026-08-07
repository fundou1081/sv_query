"""
viz_engine.py — V14 渲染引擎 (ELK.js + ExpressionTree)

布局引擎: ELK.js 0.12+ (Sugiyama layered)
渲染后端: 内联 SVG 渲染器 (替代有 bug 的 elk_svg_renderer)
输出格式: SVG / PNG

主入口:
  render_dataflow() — 数据流/运算图 (ELK.js 主路径)
"""

from __future__ import annotations
from xml.dom import minidom
from .viz_data_models import VizData

OX, OY = 40, 50  # SVG canvas offset


def _render_svg_direct(layout: dict, config: dict) -> str:
    """从 ELK layout 结果直接生成 SVG。
    
    ELK layout root container (id='root', x=0, y=0):
    - children = leaf nodes (port/op/signal), coordinates = global absolute
    - edges = all edges, section coordinates = global absolute
    
    Nested compounds: accumulate parent offsets when walking.
    """
    cfg = config or {}
    title = cfg.get('title', '')
    
    # ── Collect leaf nodes (global coords) ──
    leaves = []
    compounds = []
    
    def walk_n(n, px=0, py=0):
        nid = n.get('id', '?')
        nx = (n.get('x', 0) or 0)
        ny = (n.get('y', 0) or 0)
        gx = nx + px
        gy = ny + py
        children = n.get('children', [])
        
        if children:
            labels = n.get('labels') or []
            label = (labels[0] or {}).get('text', '') if labels else ''
            if nid not in ('root', '__expr_root__'):
                compounds.append({
                    'id': nid, 'gx': gx, 'gy': gy,
                    'w': n.get('width', 0) or 0,
                    'h': n.get('height', 0) or 0,
                    'label': label, 'meta': n.get('_meta', {}),
                })
            for c in children:
                walk_n(c, gx, gy)
        else:
            labels = n.get('labels') or []
            label = (labels[0] or {}).get('text', nid) if labels else nid
            leaves.append({
                'id': nid, 'gx': gx, 'gy': gy,
                'w': n.get('width', 0) or 44,
                'h': n.get('height', 0) or 20,
                'label': label,
                'meta': n.get('_meta', {}),
                'kind': n.get('_meta', {}).get('kind', ''),
            })
    
    walk_n(layout)
    
    # ── Collect edges (global coords) ──
    # ELK returns section coordinates relative to the containing node.
    # Root container edge sections: absolute (root.x == 0).
    # Child container edge sections: relative to child.x (so we add gx,gy).
    # Flat (no containers): root contains all edges → section coords are already global.
    edges = []
    
    def walk_e(n, px=0, py=0):
        nx = (n.get('x', 0) or 0)
        ny = (n.get('y', 0) or 0)
        gx = nx + px
        gy = ny + py
        for e in n.get('edges', []):
            srcs = e.get('sources', [])
            tgts = e.get('targets', [])
            meta = e.get('_meta', {})
            ekind = meta.get('kind', '')
            for sec in e.get('sections', []):
                sp = sec.get('startPoint') or {}
                ep = sec.get('endPoint') or {}
                if sp and ep:
                    edges.append({
                        'src': srcs[0] if srcs else '?',
                        'dst': tgts[0] if tgts else '?',
                        'sx': sp.get('x', 0) + gx,
                        'sy': sp.get('y', 0) + gy,
                        'ex': ep.get('x', 0) + gx,
                        'ey': ep.get('y', 0) + gy,
                        'kind': ekind,
                    })
        for c in n.get('children', []):
            walk_e(c, gx, gy)
    
    walk_e(layout)
    
    # ── Canvas size ──
    max_x = max((lf['gx'] + (lf['w'] or 0) for lf in leaves), default=0)
    max_y = max((lf['gy'] + (lf['h'] or 0) for lf in leaves), default=0)
    for cp in compounds:
        max_x = max(max_x, cp['gx'] + (cp['w'] or 0))
        max_y = max(max_y, cp['gy'] + (cp['h'] or 0))
    canvas_w = int(max_x + OX + 20)
    canvas_h = int(max_y + OY + 30)
    
    def _xml_esc(s):
        """Escape text for XML content (& < >)."""
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # ── Build SVG ──
    lines = []
    lines.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' %
                 (canvas_w, canvas_h, canvas_w, canvas_h))
    lines.append('  <defs>')
    lines.append('    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">')
    lines.append('      <path d="M 0 0 L 10 5 L 0 10 z" fill="#555555"/>')
    lines.append('    </marker>')
    lines.append('  </defs>')
    lines.append('  <rect width="100%" height="100%" fill="#ffffff"/>')
    
    if title:
        lines.append('<text x="%d" y="%d" font-family="sans-serif" font-size="14" font-weight="bold" fill="#2e7d32">%s</text>' %
                     (OX, 28, _xml_esc(title)))
    
    # Compound scope backgrounds
    for cp in compounds:
        sx, sy = cp['gx'] + OX, cp['gy'] + OY
        lines.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#bbb" stroke-dasharray="4,2" rx="4"/>' %
                     (sx, sy, cp['w'] or 0, cp['h'] or 0))
        if cp.get('label'):
            lines.append('<text x="%.1f" y="%.1f" font-family="Courier" font-size="8" fill="#888">%s</text>' %
                         (sx + 2, sy + 10, _xml_esc(cp['label'])))
    
    # Edges
    for e in edges:
        ekind = e.get('kind', '')
        if ekind == 'condition_select':
            stroke, dash = '#989898', ' stroke-dasharray="6,3"'
        else:
            stroke, dash = '#555555', ''
        lines.append('<path d="M %.1f %.1f L %.1f %.1f" fill="none" stroke="%s" stroke-width="1.5"%s marker-end="url(#arrow)"/>' %
                     (e['sx'] + OX, e['sy'] + OY, e['ex'] + OX, e['ey'] + OY, stroke, dash))
    
    # Leaves
    for lf in leaves:
        x, y = lf['gx'] + OX, lf['gy'] + OY
        w, h = lf['w'], lf['h']
        kind = lf.get('kind', '')
        
        if 'port_in' in kind:
            fill, stroke, rx, fs, ff, fw = '#e8e8e8', '#999', 4, 9, 'Courier', ''
        elif 'port_out' in kind:
            fill, stroke, rx, fs, ff, fw = '#e8e8e8', '#666', 4, 9, 'Courier', ''
        elif kind == 'op':
            fill, stroke, rx, fs, ff, fw = '#fff3e0', '#e65100', 1, 9, 'Helvetica, Arial, sans-serif', 'font-weight="bold"'
        elif kind == 'signal':
            fill, stroke, rx, fs, ff, fw = '#fff9c4', '#f9a825', 3, 8, 'Courier', ''
        elif kind == 'const':
            fill, stroke, rx, fs, ff, fw = '#e0f2f1', '#00695c', 2, 8, 'Courier', ''
        elif kind == 'condition_anchor':
            # 1×1 anchor dot — skip label
            continue
        else:
            fill, stroke, rx, fs, ff, fw = '#f0f0f0', '#aaa', 3, 9, 'Courier', ''
        
        lines.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" stroke="%s" rx="%d"/>' %
                     (x, y, w, h, fill, stroke, rx))
        if lf['label']:
            lines.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="%s" font-size="%d" %s fill="#333333">%s</text>' %
                         (x + w / 2, y + h / 2 + 4, ff, fs, fw, _xml_esc(lf['label'])))
    
    lines.append('</svg>')
    return minidom.parseString('\n'.join(lines)).toprettyxml(indent='  ')


# ═══════════════════════════════════════════════════
# 主渲染入口
# ═══════════════════════════════════════════════════

def render_dataflow(viz: VizData, config: dict | None = None):
    """数据流/运算图 — ExpressionTree → ELK 布局 → 内联 SVG 渲染"""
    cfg = config or {}
    title = cfg.get("title", "Dataflow")
    
    from .elk_bridge import expr_trees_to_elk, run_elk_layout, get_layout
    
    # [FIX 2026-08-07] 路径选择: 有 case/if 条件边(condition_chain) 的信号走 get_layout
    # (compound graph → 渲染 case/branch 框, true/false 条件区分).
    # 之前用 `if expr_trees:` 判断, 导致 case9 这类 case 多分支被 _store_expr_tree
    # 合并成单个表达式树后误走 expr_trees_to_elk, 丢失 case/if 分支框.
    # 有条件边的 dest → 走 get_layout; 否则 → expr_trees_to_elk (纯表达式树).
    raw_expr_trees = viz.meta.get('datapath', {}).get('expr_trees', {})
    expr_trees = {}
    for k, v in raw_expr_trees.items():
        short_key = k.rsplit('.', 1)[-1] if '.' in k else k
        if short_key not in expr_trees:
            expr_trees[short_key] = v
    
    # 检测是否有 case/if 条件边 (condition_chain 非空 或 condition 非空)
    has_cond_edges = any(
        (getattr(e, 'condition_chain', None) or []) or getattr(e, 'condition', None)
        for e in viz.edges
    )
    
    # 检测是否有分支框信号 (有条件边汇聚到同一 dst)
    if has_cond_edges:
        # compound graph 路径: 渲染 case/if 分支框
        layout = get_layout(viz)
        return _render_svg_direct(layout, {'title': title})
    
    if expr_trees:
        input_names = []
        output_names = []
        for n in viz.nodes:
            side = getattr(n, 'port_side', '')
            name = str(n.id).rsplit('.', 1)[-1] if '.' in str(n.id) else str(n.id)
            if side == 'left':
                input_names.append(name)
            elif side == 'right':
                output_names.append(name)
        
        elk = expr_trees_to_elk(expr_trees, input_names, output_names, viz=viz)
        layout = run_elk_layout(elk)
        return _render_svg_direct(layout, {'title': title})
    
    # Fallback: compound graph for case/if branches (no expr_trees, but condition edges)
    layout = get_layout(viz)
    return _render_svg_direct(layout, {'title': title})
