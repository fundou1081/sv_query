"""
trace.core.graph.viz — 统一可视化层 (V12 ELK.js)

数据 → 渲染 完全解耦:
  SignalGraph → build_viz_data(options) → VizData → get_layout(viz) → render_svg(layout) → SVG

核心模块：
  viz_data_models: VizNode / VizEdge / VizData
  viz_data_builder: build_viz_data(graph, options)
  elk_bridge: viz_to_elk() → ELK.js 布局 → get_layout()
  viz_engine: render_svg(layout) → SVG 字符串

[iter_245] 旧 DOT 渲染器已归档出本包 → docs/archive/2026-10-19-src-archived/
"""

from .viz_data_builder import VizBuildOptions, build_viz_data
from .viz_data_models import VizData, VizEdge, VizNode

__all__ = [
    "VizData",
    "VizNode",
    "VizEdge",
    "VizBuildOptions",
    "build_viz_data",
]
