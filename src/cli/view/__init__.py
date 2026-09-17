"""[iter_233 P1b-2] view 层 —— 人眼面: 图与叙述 (默认含于 capabilities, 后续重点开发)。

迁移计划 (V1~V5) 见 docs/task_tree/tasks/L1_cli_layering.md:
  V1 迁完剩余旧渲染器 → VizData; V2 解冻 12 个 SVG 断言; V3 datapath 补测试。
"""
from cli._registry import LAYERS

LAYER = LAYERS["view"]
