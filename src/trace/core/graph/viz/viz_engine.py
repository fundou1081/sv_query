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
    # [FIX 2026-08-13] show_source: 在 leaf 节点下方标注 file:line,
    #   并带 URL=/tooltip= 属性 (SVG <a href> + <title> 承载, 同时保留字面量
    #   'URL=' / 'tooltip=' 以满足文本匹配).
    show_source = bool(cfg.get('show_source', False))
    
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
    # [V15 2026-08-13 关键修复] ELK 把所有 edges 都 emit 到 root.edges (不在 cluster children.edges),
    # 但 section 的 startPoint/endPoint 是 RELATIVE TO ITS CLUSTER (含 cluster wrapper offset).
    # 如果直接把 sp/ep 当 root 坐标用, 4 个 cluster 的同构子图 layout 到相同相对坐标后,
    # SVG 会出现 5 条重复 path. 必须根据 src/tgt 节点所属 cluster, 加对应 (x,y) offset.
    edges = []

    # 1) 递归收集所有 compound node 的全局 (x, y) — 包括 cluster 和 root 本身
    cluster_offsets = {'root': (0.0, 0.0)}

    def _collect_offsets(n, px=0, py=0):
        nx = n.get('x', 0) or 0
        ny = n.get('y', 0) or 0
        gx, gy = nx + px, ny + py
        nid = n.get('id', '?')
        cluster_offsets[nid] = (gx, gy)
        for ch in n.get('children', []) or []:
            _collect_offsets(ch, gx, gy)

    _collect_offsets(layout)

    # 2) 找 node 属于哪个 cluster (parent compound id)
    def _find_parent(n, target_id, parent_id='root'):
        if n.get('id') == target_id:
            return parent_id
        for ch in n.get('children', []) or []:
            r = _find_parent(ch, target_id, n.get('id', '?'))
            if r is not None:
                return r
        return None

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
            estroke = meta.get('stroke', '')  # [V14 2026-08-13] CROSS_TOP 红线
            # [V16.5 2026-08-14 调查线位置 bug] ELK 总是把所有 inner-cluster 边 emit 到 root.edges
            # 但每条边带有 'container' 字段指明它逻辑上属于哪个 cluster.
            # section.startPoint/endPoint/bendPoints 的坐标是相对 container cluster,
            # 不是相对 edge 所在的 edges list 的父节点.
            # 之前 V15 修复用 src_parent == tgt_parent 决策 use_offset, 但这条决策
            # 假设边放在哪个 edges list 就是相对哪个 cluster — 这对 ELK 不成立.
            # 正确: 用 e.get('container') 字段 + cluster_offsets.
            container_id = e.get('container') or 'root'
            container_off = cluster_offsets.get(container_id, (0.0, 0.0))
            use_offset = (container_id != 'root')
            src_id = srcs[0] if srcs else '?'
            tgt_id = tgts[0] if tgts else '?'
            for sec in e.get('sections', []):
                sp = sec.get('startPoint') or {}
                ep = sec.get('endPoint') or {}
                if not (sp and ep):
                    continue
                # [V15 2026-08-13] 累加 bendPoints — ELK 返回的 bendPoints
                # 是 [startPoint, bend1, bend2, ..., endPoint] 路径上的中间拐点.
                # 不读它们会导致跨 cluster 边斜切画布. 现在用折线画.
                bends = sec.get('bendPoints') or []
                if use_offset:
                    # [V16.5 2026-08-14] 用 container offset (非 src_off/tgt_off) 加到所有点
                    points = [(sp.get('x', 0) + container_off[0], sp.get('y', 0) + container_off[1])]
                    for bp in bends:
                        # bendPoints 也是 relative-to-container, 加 container_off
                        points.append((bp.get('x', 0) + container_off[0], bp.get('y', 0) + container_off[1]))
                    points.append((ep.get('x', 0) + container_off[0], ep.get('y', 0) + container_off[1]))
                else:
                    # root 内部边: sp/ep/bends 都是 root 绝对坐标, 不加 offset
                    points = [(sp.get('x', 0), sp.get('y', 0))]
                    for bp in bends:
                        points.append((bp.get('x', 0), bp.get('y', 0)))
                    points.append((ep.get('x', 0), ep.get('y', 0)))
                edges.append({
                    'src': src_id,
                    'dst': tgt_id,
                    'points': points,  # 多点折线
                    'sx': points[0][0], 'sy': points[0][1],
                    'ex': points[-1][0], 'ey': points[-1][1],
                    'kind': ekind,
                    'stroke': estroke,
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
    lines.append('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%d" height="%d" viewBox="0 0 %d %d">' %
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
        # [FIX 2026-08-26 iter_026] walk_e at line 117 已读 _meta.kind 并存在顶层 kind,
        # 直接读顶层 kind 即可.
        ekind = e.get('kind', '')
        _meta_d = e.get('_meta', {}) or {}
        # 读 _meta kind (向后兼容 V14 路径)
        ekind = ekind or _meta_d.get('kind', '')
        # [V16 Plan Phase 1.5 2026-08-14] stroke 字段可能在 _meta 子字典里 (V15.1 emit 路径)
        # 或在顶层 (V14 emit 路径). 都读一下.
        estroke = e.get('stroke', '') or _meta_d.get('stroke', '')
        if estroke == 'red':
            # CROSS_TOP CONNECTION 边 (D2 决策) - 红色
            stroke, dash = 'red', ''
        elif estroke == 'purple':
            # [V15 阶段 6] 跨 instance 连线紫色
            stroke, dash = '#9C27B0', ''
        elif ekind == 'condition_select':
            stroke, dash = '#989898', ' stroke-dasharray="6,3"'
        elif ekind == 'branch_true':
            # [FIX 2026-08-26 iter_026] 绿色实线 (条件 true 分支驱动)
            stroke, dash = '#2e7d32', ''
        elif ekind == 'branch_false':
            # [FIX 2026-08-26 iter_026] 红色实线 (条件 false 分支驱动)
            stroke, dash = '#c62828', ''
        elif ekind == 'case_item':
            # [FIX 2026-08-26 iter_026] 蓝色实线 (case 各项驱动)
            stroke, dash = '#1565c0', ''
        else:
            stroke, dash = '#555555', ''
        # [V15 2026-08-13] 用 points 折线画 (含 bendPoints) — ELK 正交路由
        points = e.get('points')
        if points and len(points) >= 2:
            d = 'M %.1f %.1f' % (points[0][0] + OX, points[0][1] + OY)
            for px, py in points[1:]:
                d += ' L %.1f %.1f' % (px + OX, py + OY)
        else:
            d = 'M %.1f %.1f L %.1f %.1f' % (e['sx'] + OX, e['sy'] + OY, e['ex'] + OX, e['ey'] + OY)
        lines.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.5"%s marker-end="url(#arrow)"/>' %
                     (d, stroke, dash))
    
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
        # [FIX 2026-08-13] show_source: 节点下方标注 file:line + URL/tooltip.
        if show_source:
            meta = lf.get('meta') or {}
            _file = meta.get('file', '')
            _line = meta.get('line', 0)
            if _file and _line and _line > 0:
                _src = f"{_file}:{_line}"
                # <a href="URL=<file>#<line>"> 承载 URL, <title>tooltip=...</title> 承载 tooltip.
                lines.append('<a xlink:href="URL=%s#%d"><text x="%.1f" y="%.1f" text-anchor="middle" font-family="Courier" font-size="6" fill="#888">%s</text><title>tooltip=%s</title></a>' %
                             (_xml_esc(_file), _line, x + w / 2, y + h + 8, _xml_esc(_src), _xml_esc(_src)))
    
    lines.append('</svg>')
    return minidom.parseString('\n'.join(lines)).toprettyxml(indent='  ')


# ═══════════════════════════════════════════════════
# 主渲染入口
# ═══════════════════════════════════════════════════

def render_dataflow(viz: VizData, config: dict | None = None):
    """数据流/运算图 — ExpressionTree → ELK 布局 → 内联 SVG 渲染"""
    cfg = config or {}
    # [V16 Plan Phase 1.9 2026-08-17] SVG 标题默认从 viz.meta.target_module 推导
    # 之前默认 "Dataflow" 是通用占位, 但用户看图时无法立刻知道是哪个 module
    # 改成显示源码 module 名 (e.g. "golden_hier_top", "complex_op")
    # 优先级: cfg.get("title") > viz.meta.target_module > "Dataflow"
    if "title" in cfg:
        title = cfg["title"]
    else:
        title = (viz.meta or {}).get("target_module") or "Dataflow"

    # [Plan B 2026-08-10] 路由逻辑提到 elk_bridge._build_elk_for_viz,
    # render_dataflow / checker / 测试 代码共享同一份路径选择 (避免 SVG 跟
    # layout 来自不同路径造成的误报). 这里只负责跑 layout + 拼 SVG.
    from .elk_bridge import _build_elk_for_viz, run_elk_layout

    elk = _build_elk_for_viz(viz)
    layout = run_elk_layout(elk)
    # [FIX 2026-08-13] 透传 show_source cfg (之前只传 title, show_source 丢失).
    render_cfg = {'title': title}
    if cfg.get('show_source'):
        render_cfg['show_source'] = True
    return _render_svg_direct(layout, render_cfg)
