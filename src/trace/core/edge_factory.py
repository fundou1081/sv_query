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

from .graph.models import EdgeKind, SignalSource, TraceEdge


class TraceEdgeFactory:
    """统一创建 TraceEdge

    替代 8+ 个 ctx.get 模板和 7+ 个 sig_cond 模板。
    """

    def make_edge(
        self,
        src: str,
        dst: str,
        expression: str = "",
        kind: EdgeKind = EdgeKind.DRIVER,
        assign_type: str = "",
        bit_slice: str = "",
        ctx: dict | None = None,
        sig_cond: str = "",
        condition: str = "",  # [V4 fix] alias for sig_cond when ctx is None
        sig_cond_ast: Any | None = None,
        clock_domain: str = "",
        source: SignalSource | None = None,  # [V6.5 2026-07-28] [V6.6 renamed from driver_source]
    ) -> TraceEdge:
        """[V6.6] source 参数：结构化信号源 (driver/load 共享)。
        当 source 提供时, expression/bit_slice 自动从 source 填充
        (除非调用方显式传了非空值覆盖)。
        """
        # [V6.6] SignalSource 自动填充 expression/bit_slice
        if source is not None:
            if not expression:
                expression = source.full_expression
            if not bit_slice:
                bit_slice = source.bit_slice

        c = ctx or {}
        use_ctx = ctx is not None
        # clock_domain 显式参数优先, 否则从 ctx 读
        effective_clock = clock_domain if clock_domain else (c.get("clock", "") if use_ctx else "")
        # [V4 fix] condition 优先级: ctx > explicit condition > sig_cond (向后兼容)
        if use_ctx:
            effective_condition_field = c.get("condition", "")
        elif condition:
            effective_condition_field = condition
        else:
            effective_condition_field = sig_cond
        return TraceEdge(
            src=src,
            dst=dst,
            kind=kind,
            assign_type=assign_type,
            bit_slice=bit_slice,
            expression=expression,
            clock_domain=effective_clock,
            condition=effective_condition_field,
            effective_condition=c.get("effective_condition", "") if use_ctx else "",
            condition_ast=(
                c.get("condition_ast") if use_ctx else sig_cond_ast
            ),
            source=source,
        )
