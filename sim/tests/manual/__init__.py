"""Manual test tools package.

[Plan 2026-08-12] 集中放一次性 / ad-hoc 测试工具:
- extract_target.py: 用 semantic AST 提 SV fixture 顶层 module
- regress_golden_mini.py: 用 extract_target 跑 case1-28 regression
- README.md: 用法说明

区别于 sim/tests/unit (pytest) 和 sim/tests/integration (端到端),
manual 是开发期工具脚本, 可以独立运行也可以被 import.
"""

from .extract_target import extract_target

__all__ = ['extract_target']