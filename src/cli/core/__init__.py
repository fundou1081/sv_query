"""[iter_233 P1b-2] core 层 —— agent 一等公民 (只读 + JSON + 稳定 schema)。

分组:
  locate/   定位原语与统计 (search / stats / graph / capabilities)
  state/    状态: graph 快照与比较 (snapshot / diff)
  semantic/ 语义事实: 关系查询 (drivers / loads / impact / evidence / conditions / path)

契约由 tools/check_cli_layers.py 的 R1~R8 强制; 清单见 docs/CLI_SURFACE.md。
"""
from cli._registry import LAYERS

LAYER = LAYERS["core"]
