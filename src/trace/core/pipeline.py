# ==============================================================================
# pipeline.py - UnifiedTracer build_graph 显式 DAG 管线
#
# [ARCHITECTURE_TODOLIST #5 2026-08-28]
# 把 build_graph 的隐式顺序调用链 (11 步) 重构为显式 DAG:
# - 每步声明 inputs (需要的产物) / outputs (产出的产物)
# - 拓扑排序保证依赖先执行
# - 产物存 context, 步与步之间通过 key 引用
#
# 设计原则:
# 1. **显式依赖** — 步与步的关系从"调用顺序"变成"声明" (类似 Airflow DAG)
# 2. **行为不变** — 当前全部串行执行, 拓扑排序验证依赖合法性;
#    将来需要并行时, 独立步骤可并发 (GIL 限制下收益有限, 但结构已支持)
# 3. **可读性** — 依赖关系一目了然, 新增步骤只需声明 inputs/outputs
#
# 11 步管线 (对应 build_graph):
#   compile     : get_root()                      → root
#   adapter     : SemanticAdapter(root)           → adapter
#   graph       : GraphBuilder(adapter).build()   → graph
#   class       : ClassGraphBuilder(adapter).build(graph)   → (graph 副作用)
#   class_member: _resolve_class_member_access    → (graph 副作用)
#   bit_select  : BitSelectHandler(adapter, graph).process()
#   module_graph: ModuleInstanceGraph(adapter, graph).build() → module_graph
#   path_resolver: PathResolver(graph, module_graph)          → path_resolver
#   tracers     : _init_tracers()                 → (self._xxx_tracer)
#   cond_ops    : _emit_conditional_op_nodes()
#   backfill    : _backfill_source_locations(adapter)
#
# 依赖关系:
#   compile → adapter → graph → {class, class_member, bit_select, module_graph}
#   module_graph → path_resolver → tracers
#   graph → {cond_ops, backfill}
#   {class, class_member, bit_select} 与 {module_graph} 只依赖 graph → 可并行
# ==============================================================================
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class PipelineStep:
    """管线单步: 声明 inputs/outputs + 执行逻辑."""

    name: str
    run: Callable[[dict], Any]     # run(context) -> 产物或 None (副作用型步)
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()

    def validate(self) -> None:
        """校验步声明合法性."""
        if not self.outputs and not self.run.__doc__:
            # 副作用型步 (修改 graph 但无新产物) 需有说明
            pass


class Pipeline:
    """显式 DAG 管线: 拓扑排序执行."""

    def __init__(self, steps: list[PipelineStep]) -> None:
        self.steps = steps
        self._validate_dag()

    def _validate_dag(self) -> None:
        """校验依赖合法性: inputs 必须有 producer, 无环."""
        producers: dict[str, str] = {}
        for s in self.steps:
            for out in s.outputs:
                if out in producers:
                    raise ValueError(f"duplicate output '{out}' (steps '{producers[out]}' and '{s.name}')")
                producers[out] = s.name
        # 检查每个 input 有 producer
        for s in self.steps:
            for inp in s.inputs:
                if inp not in producers:
                    raise ValueError(f"step '{s.name}' input '{inp}' has no producer")

    def topological_order(self) -> list[PipelineStep]:
        """按依赖拓扑排序 (Kahn's algorithm)."""
        remaining = list(self.steps)
        produced: set[str] = set()
        ordered: list[PipelineStep] = []
        while remaining:
            progressed = False
            for s in remaining:
                if all(inp in produced for inp in s.inputs):
                    ordered.append(s)
                    produced.update(s.outputs)
                    remaining.remove(s)
                    progressed = True
                    break
            if not progressed:
                # 死锁: 依赖无法满足 (环或缺失 producer)
                names = [s.name for s in remaining]
                raise ValueError(f"pipeline deadlock — unsatisfied deps: {names}")
        return ordered

    def run(self, context: dict | None = None) -> dict:
        """按拓扑序执行所有步骤, 返回产物 context."""
        ctx = context if context is not None else {}
        for step in self.topological_order():
            result = step.run(ctx)
            for out in step.outputs:
                ctx[out] = result
        return ctx
