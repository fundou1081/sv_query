"""
viz_engine.py — V12 渲染引擎 (ELK.js)

布局引擎: ELK.js 0.12+ (Sugiyama layered)
渲染后端: Python SVG (cairosvg via elk_svg_renderer)
输出格式: SVG / PNG

主入口:
  render_dataflow() — 数据流/运算图 (ELK.js 主路径)

旧 DOT 渲染器已归档到 _archived_dot/
"""

from __future__ import annotations
from .viz_data_models import VizData


# ═══════════════════════════════════════════════════
# 主渲染入口
# ═══════════════════════════════════════════════════

def render_dataflow(viz: VizData, config: dict | None = None):
    """
    数据流/运算图 — "怎么算的？"
    
    使用 ELK.js 做布局，精确控制连线端口方向。
    """
    cfg = config or {}
    title = cfg.get("title", "Dataflow")
    
    from .elk_bridge import get_layout
    from .elk_svg_renderer import render_svg
    
    layout = get_layout(viz)
    meta = layout.get('_meta', {})
    return render_svg(layout, {
        'title': title,
        'scope_map': meta.get('scope_map', {}),
        'stage_map': meta.get('stage_map', {}),
    })
