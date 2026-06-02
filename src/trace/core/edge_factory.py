# ==============================================================================
# edge_factory.py - TraceEdge 工厂 (P1 cycle 1)
#
# 职责: 统一创建 TraceEdge, 消除 graph_builder.py 内 8+ ctx.get + 7+ sig_cond
#       创建模板的重复。
#
# 设计要点:
# - 支持两种入口:
#   1. ctx dict (V2.A.2 17b/17d 现状) - 读 condition/effective_condition/condition_ast/clock
#   2. sig_cond + sig_cond_ast (V2.A.2 17e+ 计划) - sig_cond-based 创建点
# - ctx 优先于 sig_cond (V2.A.2 17b/17d 的 ctx-based 点是当前主流)
# - 任何新条件字段 (如 V3 Z3 bin) 只在此处加一处
# ==============================================================================

from typing import Any

from .graph.models import EdgeKind, TraceEdge


class TraceEdgeFactory:
    """统一创建 TraceEdge

    替代 8+ 个 ctx.get 模板和 7+ 个 sig_cond 模板。
    """

    def make_edge(
        self,
        src: str,
        dst: str,
        expression: str,
        kind: EdgeKind = EdgeKind.DRIVER,
        assign_type: str = "",
        bit_slice: str = "",
        ctx: dict | None = None,
        sig_cond: str = "",
        sig_cond_ast: Any | None = None,
    ) -> TraceEdge:
        """从 ctx dict 或 sig_cond 字符串创建 TraceEdge

        Args:
            src, dst: 边端点 (必填)
            expression: 驱动表达式字符串
            kind: 边类型, 默认 DRIVER
            assign_type: 赋值类型 (continuous/nonblocking/blocking)
            bit_slice: 位选择 (如 "[7:0]")
            ctx: 上下文 dict (来自 StatementCollectorVisitor)
                 读 keys: clock, condition, effective_condition, condition_ast
            sig_cond: 局部条件字符串 (sig_cond-based 创建点用)
            sig_cond_ast: sig_cond 对应的 AST 节点

        Returns:
            TraceEdge 实例

        优先级: ctx 优先于 sig_cond (ctx 存在时 sig_cond 被忽略)
        """
        c = ctx or {}
        use_ctx = ctx is not None
        return TraceEdge(
            src=src,
            dst=dst,
            kind=kind,
            assign_type=assign_type,
            bit_slice=bit_slice,
            expression=expression,
            clock_domain=c.get("clock", "") if use_ctx else "",
            condition=c.get("condition", "") if use_ctx else sig_cond,
            effective_condition=c.get("effective_condition", "") if use_ctx else "",
            condition_ast=(
                c.get("condition_ast") if use_ctx else sig_cond_ast
            ),
        )
