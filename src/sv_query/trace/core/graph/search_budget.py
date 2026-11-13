# ==============================================================================
# search_budget.py - 路径/遍历搜索的预算记账 (唯一实现)
# ==============================================================================
"""有界搜索的 work budget + wall-clock deadline。

[P158.2] 由 `PathResolver` 首次引入；[P158.11.2b] 抽到独立模块，供
`DataFlowGraph`（dataflow）等长查询共用 —— 不允许出现第二份预算逻辑
（铁律 I3 单一实现 / SEMANTIC_CONTRACTS §3）。

只做**记账**：谁耗尽了预算、为什么耗尽。截断必须显式可见，不允许静默 cap。
"""
from __future__ import annotations

import time

__all__ = ["SearchBudget"]


class SearchBudget:
    """路径枚举的 work budget + wall-clock deadline。

    原因优先级 (硬预算 > 软上限):
      1. `deadline_reached`       — wall-clock 超时 (搜索被中止)
      2. `max_expansions_reached` — work budget 耗尽 (搜索被中止)
      3. `max_paths_reached`      — 结果数收满, 但确认还有更多路径
      4. `max_depth_reached`      — 深度上限剪掉分支 (可能漏路径)

    用法: 每次考察一条出边 `expansions += 1`，并在循环顶端检查
    `exhausted`；结束后读 `reason` / `truncated` / `hard_truncated`。
    """

    #: 硬预算 (中止搜索) 优先于软上限 (剪枝/收满)
    _HARD = ("deadline_reached", "max_expansions_reached")
    _SOFT = ("max_paths_reached", "max_depth_reached")

    def __init__(self, max_expansions: int, deadline: float | None,
                 max_paths: int, max_depth: int):
        self.max_expansions = max_expansions
        self.deadline = deadline
        self.max_paths = max_paths
        self.max_depth = max_depth
        self.expansions = 0
        self._reasons: set[str] = set()
        self._start = time.monotonic()

    def note(self, reason: str) -> None:
        """记录截断原因 (可多个; 优先级见类 docstring)。"""
        self._reasons.add(reason)

    @property
    def reason(self) -> str:
        """返回优先级最高的截断原因 (空串 = 未截断)。"""
        for candidate in self._HARD + self._SOFT:
            if candidate in self._reasons:
                return candidate
        if self.deadline is not None and time.monotonic() > self.deadline:
            return "deadline_reached"
        return ""

    @property
    def exhausted(self) -> bool:
        """预算是否耗尽 (work budget 或 wall-clock deadline)。"""
        if self.expansions >= self.max_expansions:
            self.note("max_expansions_reached")
            return True
        if self.deadline is not None and time.monotonic() > self.deadline:
            self.note("deadline_reached")
            return True
        return False

    @property
    def truncated(self) -> bool:
        return bool(self.reason)

    @property
    def hard_truncated(self) -> bool:
        """是否被**硬预算**中止 —— 结果不完整且可能"看起来没有路径"。

        [P158.11.2b] 这种状态下 `found:false` 是错误结论，必须返回 unknown。
        """
        return self.reason in self._HARD

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self._start
