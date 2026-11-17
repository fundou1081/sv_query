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

`Stage.run` 可以声明 0 或 1 个位置参数：0 个参数表示无参 pass；1 个参数（包括
可选参数或 `*args`）表示接收 `GraphPipeline.run(context=...)` 传入的 context。
判定在 `Stage` **构造期**通过 `inspect.signature` 完成，不在运行期用
`TypeError` 试探；非法形态（>1 位置参数 / 必填 keyword-only / 不可内省）在
构造期抛 `ValueError`。注意：1 个可选位置参数的默认值会被 context 覆盖。
"""
from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _accepts_context(name: str, run: Callable[..., None]) -> bool:
    """确定性判定 `run` 是否接收一个 `context` 位置参数。

    规则（只允许 0 或 1 个位置参数）：
    - 0 个位置参数且无 `*args` → 不传 context；
    - 1 个位置参数或 `*args` → 传 context；
    - 其它形态（>1 位置参数 / 必填 keyword-only 参数）→ 构造期显式报错。
    """
    try:
        signature = inspect.signature(run)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"GraphPipeline: stage {name!r} 的 run 无法内省签名: {exc}"
        ) from exc

    parameters = list(signature.parameters.values())
    positional = [
        p for p in parameters
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(p.kind is p.VAR_POSITIONAL for p in parameters)
    required_kwonly = [
        p for p in parameters
        if p.kind is p.KEYWORD_ONLY and p.default is p.empty
    ]

    if len(positional) > 1:
        raise ValueError(
            f"GraphPipeline: stage {name!r} 的 run 必须接收 0 或 1 个位置参数，"
            f"实际 {len(positional)} 个"
        )
    if required_kwonly:
        raise ValueError(
            f"GraphPipeline: stage {name!r} 的 run 有必填 keyword-only 参数: "
            + ", ".join(p.name for p in required_kwonly)
        )
    return has_varargs or len(positional) == 1


@dataclass(frozen=True)
class Stage:
    """一个后处理 pass（只做声明；执行由 GraphPipeline 负责）。"""

    name: str
    run: Callable[..., None] = field(repr=False)
    requires: frozenset[str] = frozenset()
    provides: frozenset[str] = frozenset()
    note: str = ""
    accepts_context: bool = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "requires", frozenset(self.requires))
        object.__setattr__(self, "provides", frozenset(self.provides))
        object.__setattr__(self, "accepts_context", _accepts_context(self.name, self.run))


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

    def run(self, context: object = None) -> list[str]:
        """按推导顺序执行；返回实际执行顺序（便于日志/测试断言）。

        `context` 只传给构造期判定为接收它的 stage；无参 stage 仍以 `run()`
        调用，保持既有 GraphBuilder pass 的行为不变。
        """
        executed = []
        for stage in self._order:
            logger.debug("graph pipeline: %s", stage.name)
            if stage.accepts_context:
                stage.run(context)
            else:
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
