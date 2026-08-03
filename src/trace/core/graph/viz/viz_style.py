"""
viz_style.py — 统一的视觉样式系统 (V8.0)

参考图风格 (MediaTek CRV5 信号图):
  - 左→右流水线布局
  - 黑白灰主色调 + 蓝/红点缀
  - 直角矩形无圆角
  - 虚线 cluster 边框
  - 花括号位宽标注

所有渲染器共享这个样式配置。
"""

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class VizStyle:
    """统一的视觉样式配置"""

    # ── 全局 ──
    layout_direction: str = "LR"        # 左→右 (参考图风格)
    bgcolor: str = "white"
    fontname: str = "Helvetica"
    fontsize: int = 10
    edge_fontsize: int = 8

    # ── 节点 ──
    node_shape: str = "box"             # 直角矩形 (参考图风格: 无圆角)
    node_fill: str = "white"
    node_border: str = "black"
    node_border_width: int = 1

    # Node kind → fill/border overrides
    kind_fills: ClassVar[dict[str, str]] = {
        "PORT_IN":  "white",
        "PORT_OUT": "white",
        "REG":      "#fafafa",
        "WIRE":     "white",
        "SIGNAL":   "white",
    }
    kind_borders: ClassVar[dict[str, str]] = {
        "REG":      "black",
        "CLOCK":    "#999999",
        "RESET":    "#999999",
    }

    # ── 边 ──
    edge_color: str = "black"           # 主边: 黑色
    edge_control_color: str = "#2563eb"  # 控制边: 蓝虚线 (参考图 cluster 风格)
    edge_clock_color: str = "#999999"    # 时钟边: 灰色

    # ── Cluster ──
    cluster_border: str = "#2563eb"      # 蓝色虚线 (参考图风格)
    cluster_fill: str = "#f8faff"
    cluster_style: str = "dashed"

    # ── OP 节点 ──
    op_shape: str = "circle"
    op_fill: str = "white"
    op_border: str = "black"

    # ── Mux/决策节点 ──
    mux_shape: str = "diamond"
    mux_fill: str = "#e8f0fe"
    mux_border: str = "#2563eb"


# 默认样式实例
DEFAULT_STYLE = VizStyle()
