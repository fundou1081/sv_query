"""[iter_288 / PLAN P3.3] 设计审计分析（原 exp 10 条创意的重新实现）。

全部是**只读**分析：输入是已经建好的 SignalGraph / MIG / 源码，
输出是结构化 dict（供 CLI `audit` 命令消费）。

每条分析都显式标注证据等级：
  - `"confidence": "pattern"`    — 名称/结构模式匹配（确定但只是模式）
  - `"confidence": "measured"`   — 从 AST/图直接数出来的事实
  - `"confidence": "heuristic"`  — 结构推断，可能误报（输出用 "candidates" 措辞）
"""
from .audit import CHECKS, run_audit

__all__ = ["CHECKS", "run_audit"]
