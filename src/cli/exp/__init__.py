"""[iter_232 P1b] exp 层 —— 降级区 (无 schema 承诺, 只修 bug 不加功能)。

目录结构 = 承诺等级 (见 docs/EXP_NAMESPACE.md):
  bus/    总线结构域: protocol / handshake / backpressure
  verif/  验证域:     sva / coverage / verify / risk / randomize
  struct/ 算法待定:   cdc / timing (附晋升门槛)

机械约束 (tools/check_cli_layers.py):
  - exp 不得被 core/view 依赖; exp 不得 import dev
  - exp 不出现在 capabilities 默认输出 (需 --include-exp)
  - 五条硬约束见 docs/EXP_NAMESPACE.md
"""
from cli._registry import LAYERS

LAYER = LAYERS["exp"]
