# ==============================================================================
# query/load.py - Load 追溯 (SignalTracer 的薄适配层)
# ==============================================================================
"""
[功能]
- 追溯信号的后继（被哪些信号使用），返回 `LoadChain`
- 与 query/signal.py 的 driver 方向对称

[iter_241] 为什么是"适配层"而不是独立实现

此前 `LoadTracer` 继承 `GraphTraversal`, 自带一份**平行的**遍历逻辑 + 自己的 id
拼接规则, 与 `SignalTracer` (`svq loads` 实际走的路) 长期分叉, 导致三个缺陷:

  L1 `f"{module}.{signal}"` 在 `module=None` 时得到 `"None.sig"`
     → 结果恒空, 且 `LoadChain.root` 是一个**永不存在的 id** (静默错误答案)
  L2 没有 MIG → 跨模块 loads 永远丢失 (`trace_loads('sub_adder.sum')` → `[]`)
  L3 不支持 `depth`; `confidence` 词表也与 `SignalChain` 不一致

现在遍历只有一份 (`SignalTracer.trace_fanout`), 本类只做 **入参解析 + 结果打包**,
因此不可能再与 CLI 行为分叉。基类 `GraphTraversal` 随之成为死代码并已删除。

[与 Driver 对称]
- Driver: 谁驱动我 (`SignalTracer.trace_fanin`)
- Load:   我驱动谁 (`SignalTracer.trace_fanout`)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from trace.core.graph.models import SignalGraph
from trace.core.query.signal import SignalTracer


@dataclass
class LoadChain:
    """Load 追溯结果

    与 SignalChain 对称的结构
    """

    root: str  # 信号 ID
    loads: list[any]  # 后继节点（被这个信号驱动的）
    confidence: str = "high"  # 置信度
    # 保留字段: 当前无消费者, 不填值 (历史遗留; 删除会破坏外部构造 LoadChain 的代码)
    path: list[str] = field(default_factory=list)


def _dedupe(nodes: list) -> list:
    """按 id 去重并保持出现顺序。"""
    seen: set[str] = set()
    unique = []
    for node in nodes:
        if node.id not in seen:
            seen.add(node.id)
            unique.append(node)
    return unique


class LoadTracer:
    """
    Load 追溯器 (SignalTracer.trace_fanout 的薄适配层)

    [与 Driver 方向对称]
    - Driver 方向: `SignalTracer.trace_fanin`
    - Load 方向:   `SignalTracer.trace_fanout` (本类)

    [契约]
    - 返回的 `loads` 与 `SignalTracer.trace_fanout` **逐节点相同** (由测试锁定);
      本类不再有自己的遍历, 因此不存在"两份实现给出不同答案"的可能。
    """

    def __init__(self, graph: SignalGraph, mig: object | None = None):
        """初始化。

        Args:
            graph: SignalGraph
            mig: ModuleInstanceGraph (可选) — 跨模块端口映射; 透传给 SignalTracer
            [iter_272] MIG fallback 已删除 (图恒为实例级)。
        """
        self.graph = graph
        self._signal_tracer = SignalTracer(graph, mig=mig)

    def trace(self, signal_name: str, module_name: str = None, depth: int | None = None) -> LoadChain:
        """追溯信号的所有后继。

        Args:
            signal_name: 信号名; `module_name=None` 时按**完整 id** 解析
                (例: `'inst_demo.in_a'`)
            module_name: 模块名 (可选)。给定时为**限定查询** — 与 CLI 一致,
                不跨模块边界; 不给时为**全局查询**, 跨模块。
            depth: 1=只看直接后继, N=递归 N 层, None=递归到底

        Returns:
            LoadChain: 包含所有后继; 节点不存在时 `confidence="unknown"`
        """
        signal_id = self._signal_tracer.make_id(signal_name, module_name)

        if signal_id not in self.graph.nodes():
            return LoadChain(root=signal_id, loads=[], confidence="unknown")

        # 唯一真相源: 遍历在 SignalTracer.trace_fanout (含 MIG 跨模块 + 作用域规则)
        nodes = self._signal_tracer.trace_fanout(signal_name, module_name, depth=depth)
        unique_loads = _dedupe(nodes)
        confidence = self._evaluate_confidence(unique_loads)

        return LoadChain(root=signal_id, loads=unique_loads, confidence=confidence)

    def get_loads(self, signal_id: str) -> list[str]:
        """获取 signal_id 的所有后继节点 ID

        Args:
            signal_id: **完整节点 id** (例: `'top.d'`); 不做 module 拼接

        Returns:
            节点 ID 列表 (去重, 保持遍历顺序)
        """
        return [node.id for node in _dedupe(self._signal_tracer.trace_fanout(signal_id))]

    @staticmethod
    def _evaluate_confidence(loads: list) -> str:
        """评估置信度

        [规则]
        - 0 个后继: "no_load"（无负载）
        - 1 个后继: "high"
        - 多个后继: "medium"
        """
        if not loads:
            return "no_load"
        if len(loads) == 1:
            return "high"
        return "medium"
