"""
trace.core.graph.viz — 统一可视化数据层 (V6.7)

数据 → 渲染 完全解耦:
  SignalGraph → build_viz_data(options) → VizData → render_dot(viz) → DOT 字符串
                                                      └── render_json(viz) → JSON

所有 6 种画图功能共用:
  viz_data_models: VizNode / VizEdge / VizData
  viz_data_builder: build_viz_data(graph, options)
  viz_dot_renderer: render_dot(viz, config)
"""

from .viz_data_models import VizData, VizNode, VizEdge
from .viz_data_builder import VizBuildOptions, build_viz_data
from .viz_dot_renderer import render_dot

__all__ = [
    "VizData",
    "VizNode",
    "VizEdge",
    "VizBuildOptions",
    "build_viz_data",
    "render_dot",
]
