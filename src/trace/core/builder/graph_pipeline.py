"""[iter_282 / PLAN P0.3] GraphBuilder 后处理 pass 的声明式 pipeline。

问题
----
`GraphBuilder.build()` 里 12 个 pass 靠**隐式顺序**串起来（例如"位节点必须在
upgrade_regs 之前"、"位桥必须在 filter_by_target 之后"），这些约束只存在于
注释里；新增 pass 时没有明确的插入点。

方案
----
每个 pass 声明：
  - `provides`: 它产出什么（token）
  - `requires`: 它依赖哪些 token
执行顺序由**依赖拓扑排序**推导（同层按声明顺序稳定排序）；声明缺失依赖 /
循环依赖 → 立即 `ValueError`，不静默继续。

使用
----
    pipeline = GraphPipeline([
        Stage("extract_nodes", self._extract_all_nodes, provides={"nodes"}),
        Stage("extract_edges", self._extract_all_edges,
              requires={"nodes"}, provides={"edges"}),
        ...
    ])
    pipeline.run()
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Stage:
    """一个后处理 pass（只做声明；执行由 GraphPipeline 负责）。"""

    name: str
    run: Callable[[], None] = field(repr=False)
    requires: frozenset[str] = frozenset()
    provides: frozenset[str] = frozenset()
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "requires", frozenset(self.requires))
        object.__setattr__(self, "provides", frozenset(self.provides))


class GraphPipeline:
    """按 `requires/provides` 拓扑排序并执行 pass。"""

    def __init__(self, stages: Iterable[Stage]):
        self._stages: list[Stage] = list(stages)
        self._index = {s.name: i for i, s in enumerate(self._stages)}
        if len(self._index) != len(self._stages):
            raise ValueError("GraphPipeline: stage 名字重复")
        self._order: list[Stage] = self._resolve_order()

    # ------------------------------------------------------------------ 对外
    @property
    def order(self) -> list[str]:
        return [s.name for s in self._order]

    def run(self) -> list[str]:
        """按推导顺序执行；返回实际执行顺序（便于日志/测试断言）。"""
        executed = []
        for stage in self._order:
            logger.debug("graph pipeline: %s", stage.name)
            stage.run()
            executed.append(stage.name)
        return executed

    # ------------------------------------------------------------------ 内部
    def _resolve_order(self) -> list[Stage]:
        provided: set[str] = set()
        # 先做静态校验：requires 必须被某个 stage 提供（允许自提供）
        all_provides: set[str] = set()
        for s in self._stages:
            all_provides |= s.provides
        for s in self._stages:
            missing = s.requires - all_provides
            if missing:
                raise ValueError(
                    f"GraphPipeline: stage {s.name!r} 依赖未声明产出的 token: {sorted(missing)}"
                )

        remaining = list(self._stages)
        order: list[Stage] = []
        while remaining:
            ready = [s for s in remaining if s.requires <= provided]
            if not ready:
                raise ValueError(
                    "GraphPipeline: 存在循环依赖或缺少起点: "
                    + ", ".join(s.name for s in remaining)
                )
            # 同层按声明顺序（稳定）
            ready.sort(key=lambda s: self._index[s.name])
            stage = ready[0]
            order.append(stage)
            provided |= stage.provides
            remaining.remove(stage)
        return order
