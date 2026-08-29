import logging

# ==============================================================================
# extractors/always_extractor.py - always 块 driver/clock/reset 边提取
#
# [ARCHITECTURE_TODOLIST #1 Step 6 2026-08-28]
# 从 driver_extractor.py 拆出 always 相关 9 个方法 (~790 行):
#   - _extract_clock_from_always / _extract_clock_from_event_ctrl (50 行)
#     时钟提取链 (被 _collect_stmts_with_context 调用)
#   - _create_always_edges            (453 行) 主入口 — always_ff/comb/latch
#   - _add_condition_drivers          ( 81 行) [Phase 7.6] 已 disabled
#   - _collect_signals_from_ast       ( 48 行) AST 遍历提取 cond signals
#   - _is_valid_signal_name           ( 15 行) SV 标识符检查
#   - _collect_stmts_with_context     ( 62 行) statement + ctx 收集
#   - _extract_reset_from_always      ( 41 行) reset 提取
#   - _get_always_body_items          ( 24 行) always body 展平入口
#
# ── 保留在 driver_extractor 的共享 helper (通过 AlwaysHelpers 注入) ────────
# _is_compile_time_symbol / _is_sv_literal_token 被 always 块**外**的
# _expr_is_compile_time / _filter_signal_conditions_by_module 调用,
# 是 assign/always/function 共享的基础设施, 不能随 always 块搬走。
#
# ── 依赖设计 ──────────────────────────────────────────────────────────────────
# AlwaysHelpers dataclass 注入 (沿用 Step 4 AssignHelpers 模式):
#   10 个共享 helper + signal_visitor/edge_factory/adapter/cond_ast_by_str。
#
# ── 行为契约 ──────────────────────────────────────────────────────────────────
# - _create_always_edges 453 行**本次只搬不拆** (行为重构独立 commit, 便于归因)。
# - 副作用仅通过 (1) append result.nodes/result.edges (2) 写 cond_ast_by_str。
# - 内部互调 _xxx(...) 带 h=h 自动转发。
# ==============================================================================
from dataclasses import dataclass
from typing import Any, Callable

from pyslang.pyslang.ast import StatementKind  # [V6.9] semantic AST only

from ..ast_utils import kind_matches, unwrap
from ..graph.models import EdgeKind, NodeKind, TraceNode

logger = logging.getLogger(__name__)


@dataclass
class AlwaysHelpers:
    """[Step 6 2026-08-28] driver_extractor 共享 helper 注入包.

    与 AssignHelpers 同构, 字段名去下划线前缀 (self._get_signal → h.get_signal)。
    """

    adapter: Any
    get_signal: Callable
    get_all_real_signals: Callable
    parse_assign: Callable
    store_expr_tree: Callable
    handle_invocation: Callable
    build_signal_source: Callable
    expr_is_compile_time: Callable
    filter_signal_conditions_by_module: Callable
    flatten_semantic: Callable
    is_sv_literal_token: Callable
    signal_visitor: Any = None
    edge_factory: Any = None
    cond_ast_by_str: dict = None


_EXCLUDED_SYMBOL_KINDS = {
    "Parameter",        # parameter [2:0] cpu_state_trap = 3'd0;
    "EnumValue",       # enum value (same as Parameter effectively)
    "TypeParameter",    # type parameter
    "Specparam",        # specparam
    "Genvar",           # generate variable (compile-time)
}


def _extract_clock_from_always(n, *, h: 'AlwaysHelpers') -> str:
    """从 always_ff @(posedge clk) 提取时钟信号名"""
    s = getattr(n, "statement", None) or getattr(n, "body", None)
    if not s:
        return ""
    # [FIX] pyslang TimedStatement uses .timing, not .timingControl
    tc = getattr(s, "timing", None) or getattr(s, "timingControl", None)
    if tc:
        return _extract_clock_from_event_ctrl(tc, h=h)
    return ""




def _extract_clock_from_event_ctrl(n, *, h: 'AlwaysHelpers') -> str:
    """从 TimingControl 提取时钟,处理 or 连接的多个事件"""
    # [FIX] EventList has events, not expr
    if hasattr(n, "events"):
        for evt in n.events:
            clock = _extract_clock_from_event_ctrl(evt, h=h)
            if clock:
                return clock
        return ""

    e = getattr(n, "expr", None)
    if not e:
        return ""
    i = getattr(e, "expr", None) or e

    def find_clock(expr: object) -> str:
        if expr is None:
            return ""
        # [FIX] NamedValueExpression with symbol - extract name directly
        if hasattr(expr, "symbol"):
            sym = getattr(expr, "symbol", None)
            if sym and hasattr(sym, "name"):
                return str(sym.name).strip()
        if hasattr(expr, "left") and hasattr(expr, "right"):
            left_res = find_clock(expr.left)
            return left_res if left_res else find_clock(expr.right)
        edge_str = str(getattr(expr, "edge", ""))
        # [FIX] EdgeKind.PosEdge -> 'PosEdge', check both lowercase and the enum name
        if "posedge" in edge_str.lower() or "PosEdge" in edge_str or "NegEdge" in edge_str:
            ce = getattr(expr, "expr", None)
            if ce and hasattr(ce, "symbol"):
                sym = getattr(ce, "symbol", None)
                if sym and hasattr(sym, "name"):
                    return str(sym.name).strip()
            return str(ce).strip() if ce else ""
        return ""

    return find_clock(i)




def _create_always_edges(module, result, module_name, genvar_ctx: dict | None = None, *, h: 'AlwaysHelpers'):
    """[REFACTOR 2026-06-26] 处理 always 块 (含 always_ff/always_comb/always_latch).

    遍历 always 块的语句, 处理:
    - INVOCATION: 调 _handle_invocation
    - Assignment + InvocationExpression RHS: 调 _handle_invocation
    - 普通 Assignment: 解析 lhs/rhs, 创建 DRIVER edge + CLOCK/RESET edge
    """
    # [#8 2026-08-28] 顶层 always + generate-for 内展开的 always 一起处理.
    # get_always_blocks 只遍历 module.body 顶层; generate-for 内的 always 块
    # (e.g. `for(i...) begin: gen always_ff @(posedge clk) acc[i] <= data_in; end`)
    # 在 GenerateBlockArray.entries 里, 需要 get_generate_always_blocks 补上,
    # 否则 generate 内所有 procedural 赋值没有 DRIVER 边。
    all_always = list(h.adapter.get_always_blocks(module))
    for ga in h.adapter.get_generate_always_blocks(module):
        all_always.append((ga["always"], ga["genvar_ctx"]))

    for item_ga in all_always:
        always = item_ga[0] if isinstance(item_ga, tuple) else item_ga
        ga_ctx = item_ga[1] if isinstance(item_ga, tuple) else None
        # [铁律29] 使用 _collect_stmts_with_context 包装方法
        # 内部使用 StatementCollectorVisitor
        stmts_ctx = _collect_stmts_with_context(always, h=h, genvar_ctx=ga_ctx)
        for item in stmts_ctx:
            # [铁律29] StatementCollectorVisitor 返回 (node, ctx, ItemType)
            stmt, ctx, item_type = item
            # [#8 2026-08-28] 把 genvar_ctx 塞进 adapter._genvar_context (id-keyed),
            # 保证 _parse_assign → adapter.get_genvar_context(stmt) 命中并 substitute.
            # _collect_stmts_with_context 返回的 stmt 与 get_assignments 遍历到的
            # 可能不是同一对象 (id 不可靠), 这里用当前 stmt 的真实 id 重新登记。
            gv = ctx.get("_genvar")
            if gv:
                try:
                    h.adapter._genvar_context[id(stmt)] = dict(gv)
                except Exception as e:
                    logger.debug("genvar 登记失败: %s", e)
                    pass

            # 如果是 invocation,暂不处理赋值
            if False:  # [V6.9] ItemType removed
                # [NEW] 处理 task/function 调用
                h.handle_invocation(stmt, ctx, module, module_name, result)
                continue

            # [FIX] 检测 RHS 是否为函数调用InvocationExpression
            rhs_kind = str(getattr(stmt, "kind", None)) if stmt else ""
            if "Assignment" in rhs_kind:
                raw_rhs = getattr(stmt, "right", None) or getattr(stmt, "left", None)
                rhs_kind = str(getattr(raw_rhs, "kind", None)) if raw_rhs else ""
                if "Invocation" in rhs_kind or "Call" in rhs_kind:
                    # 函数调用 RHS: 提取 lhs 并调用 _handle_invocation
                    raw_lhs = getattr(stmt, "left", None)
                    lhs_name = h.get_signal(raw_lhs) if raw_lhs else None
                    h.handle_invocation(raw_rhs, ctx, module, module_name, result, lhs_name)
                    continue

            lhs, rhs, rhs_expr = h.parse_assign(stmt)
            if lhs and (rhs or rhs_expr):
                # [FIX] 检测 RHS 是否为函数调用
                rhs_kind = str(getattr(rhs, "kind", None)) if rhs else ""
                if "Invocation" in rhs_kind or "Call" in rhs_kind:
                    # 函数调用: 调用 _handle_invocation 处理
                    h.handle_invocation(rhs, ctx, module, module_name, result, lhs)
                    continue

            if not lhs:
                # [V6.9 fix] _parse_assign 对 InvocationExpression/CallExpression 返回 (None,None,None)
                #          检查 stmt.expr 是否为 Invocation/Call（always_comb/initial 直接调用）
                raw_expr = getattr(stmt, "expr", None)
                if raw_expr:
                    ek = str(getattr(raw_expr, "kind", ""))
                    if "Invocation" in ek or "Call" in ek:
                        h.handle_invocation(raw_expr, ctx, module, module_name, result)
                        continue

            if lhs and (rhs or rhs_expr):
                # Only upgrade to REG if there's a clock context (always_ff)
                is_always_ff = bool(ctx.get("clock"))
                dst_node_id = f"{module_name}.{lhs}"
                existing = next((n for n in result.nodes if n.id == dst_node_id), None)
                if existing:
                    if is_always_ff:
                        if existing.kind == NodeKind.SIGNAL:
                            existing.kind = NodeKind.REG
                        elif existing.kind in (NodeKind.PORT_OUT, NodeKind.PORT_IN):
                            was_port = existing.is_port
                            existing.kind = NodeKind.REG
                            existing.is_port = was_port
                else:
                    kind = NodeKind.REG if is_always_ff else NodeKind.SIGNAL
                    result.nodes.append(
                        TraceNode(id=dst_node_id, name=lhs, module=module_name, kind=kind, width=(1, 0))
                    )

                # [V6.9] 如果 ctx["leaf_name"] 存在, 说明 ternary 已在 _flatten_assignments
                # 中展开。直接使用 leaf_name + ctx["condition"] 创建 edge.                    # [V6.9] 如果 ctx["leaf_name"] 存在, 说明 ternary 已在 _flatten_assignments
                # 中展开。直接使用 leaf_name + ctx["condition"] 创建 edge.
                leaf_from_ctx = ctx.get("leaf_name", "")
                if leaf_from_ctx:
                    sig_cond = ctx.get("condition", "")
                    src_node_id = f"{module_name}.{leaf_from_ctx}"
                    if src_node_id not in [n.id for n in result.nodes]:
                        result.nodes.append(
                            TraceNode(
                                id=src_node_id, name=leaf_from_ctx,
                                module=module_name, kind=NodeKind.SIGNAL, width=(1, 0)
                            )
                        )
                    bit_slice = ""
                    if "[" in leaf_from_ctx and "]" in leaf_from_ctx:
                        start = leaf_from_ctx.index("[")
                        bit_slice = leaf_from_ctx[start:]
                    result.edges.append(
                        h.edge_factory.make_edge(
                            src=src_node_id, dst=dst_node_id,
                            kind=EdgeKind.DRIVER,
                            assign_type="nonblocking",
                            expression=leaf_from_ctx,
                            bit_slice=bit_slice,
                            clock_domain=ctx.get("clock", ""),
                            sig_cond=sig_cond,
                            condition_chain=ctx.get("condition_chain"),
                        )
                    )
                    # [V6.9] 继续走 clock/reset edge 创建逻辑
                    # leaf edge 已创建, 下面是 clock/reset edges
                    # Create clock edge (mirrors line ~1799)
                    if is_always_ff and ctx.get("clock"):
                        clk_name = ctx["clock"]
                        clk_node_id = f"{module_name}.{clk_name}"
                        if clk_node_id not in [n.id for n in result.nodes]:
                            result.nodes.append(
                                TraceNode(
                                    id=clk_node_id, name=clk_name,
                                    module=module_name, kind=NodeKind.SIGNAL, width=(1, 0)
                                )
                            )
                        result.edges.append(
                            h.edge_factory.make_edge(
                                src=clk_node_id, dst=dst_node_id,
                                expression="",
                                kind=EdgeKind.CLOCK,
                                assign_type="nonblocking",
                                clock_domain=clk_name,
                                ctx=ctx,
                            )
                        )
                    # Create reset edge if present
                    if ctx.get("reset"):
                        rst_name = ctx["reset"]
                        rst_node_id = f"{module_name}.{rst_name}"
                        if rst_node_id not in [n.id for n in result.nodes]:
                            result.nodes.append(
                                TraceNode(
                                    id=rst_node_id, name=rst_name,
                                    module=module_name, kind=NodeKind.SIGNAL, width=(1, 0)
                                )
                            )
                        result.edges.append(
                            h.edge_factory.make_edge(
                                src=rst_node_id, dst=dst_node_id,
                                expression="",
                                kind=EdgeKind.RESET,
                                assign_type="nonblocking",
                                clock_domain=rst_name,
                                ctx=ctx,
                            )
                        )
                    continue  # 跳过后续的 ternary 复杂逻辑和 rhs_signals 提取

                # [REFACTOR 2026-08-07 A计划] 从 procedural assignment 构建表达式树
                # always_comb/always_ff 中 case/if 每个分支的 rhs 是独立 semantic 节点，
                # _store_expr_tree 内部对同一 lhs 多分支做 max 合并（取最复杂代表）
                if lhs and rhs_expr is not None:
                    h.store_expr_tree(lhs, rhs_expr, module_name, result, genvar_ctx=genvar_ctx)

                # [NEW] 使用 rhs_expr (来自 _parse_assign) 提取所有驱动源
                # [FIX 2026-7-15] Pass module for Syntax AST resolution
                rhs_signals = h.get_all_real_signals(rhs_expr, module=module, genvar_ctx=genvar_ctx) if rhs_expr else [rhs]
                if not rhs_signals:
                    # [Phase 8 / Fix F 2026-7-14] Skip if compile-time symbol
                    # [FIX 2026-7-15] Pass module for Syntax AST resolution
                    if rhs_expr is not None and h.expr_is_compile_time(rhs_expr, module=module):
                        rhs_signals = []
                    else:
                        rhs_signals = [rhs]
                # [P0-2] 计算完整表达式字符串
                if rhs_expr:
                    try:
                        expr_str = h.signal_visitor.get_source_text(rhs_expr) or str(rhs_expr) or h.signal_visitor.get_source_text(rhs_expr) or str(rhs_expr)
                    except (UnicodeDecodeError, TypeError):
                        expr_str = "<expr:non-utf8>"
                else:
                    expr_str = rhs or ""

                # [BUG-FIX] 嵌套三元: 为每个信号提取对应条件
                # [V6.3+3 2026-07-27] Refactored to use ast_utils:
                #   - kind_matches handles ConditionalOp/ConditionalExpression aliases
                #   - unwrap strips Paren/Conversion/ImplicitCast wrappers
                # Replaces 13 lines of substring checks and ad-hoc unwrap.
                has_conditional = False
                check_expr = rhs_expr
                for _ in range(5):  # 解包多层包装
                    if check_expr is None:
                        break
                    if kind_matches(check_expr, "ConditionalOp", "ConditionalExpression"):
                        has_conditional = True
                        break
                    inner = unwrap(check_expr)
                    if inner is None or inner is check_expr:
                        break
                    check_expr = inner

                if has_conditional:
                    # [Phase 8 / Fix F.6 2026-7-15] Filter compile-time symbols
                    # (localparam/parameter) from ternary branch signals.
                    # Use the unwrapped check_expr so ConditionalOp is at top.
                    #
                    # [V6.9 FIX] semantic_adapter returns list[str] (ALL signals).
                    # Must separate condition signals from leaf signals.
                    all_signals2 = h.signal_visitor._extract_signals_from_expr(check_expr) or []
                    cond_sig_names2 = set()
                    def _collect2(cop, acc):
                        if cop is None:
                            return
                        ck2 = str(getattr(cop, "kind", ""))
                        if "ConditionalOp" not in ck2 and "ConditionalExpression" not in ck2:
                            return
                        rc2 = getattr(cop, "conditions", None)
                        if rc2:
                            for c in rc2:
                                ce = getattr(c, "expr", None) or getattr(c, "expression", None)
                                if ce:
                                    for s in (h.signal_visitor._extract_signals_from_expr(ce) or []):
                                        acc.add(s)
                        _collect2(getattr(cop, "left", None), acc)
                        _collect2(getattr(cop, "right", None), acc)
                    _collect2(check_expr, cond_sig_names2)
                    leaf_signals2 = [s for s in all_signals2 if s not in cond_sig_names2]

                    # [V6.9] 构建每个 leaf 的条件文本
                    def _build_cond_map(cond_op, path=None):
                        result = {}
                        if path is None:
                            path = []
                        if cond_op is None:
                            return result
                        ck = str(getattr(cond_op, "kind", ""))
                        if "ConditionalOp" not in ck and "ConditionalExpression" not in ck:
                            return result
                        cond_texts = []
                        rc = getattr(cond_op, "conditions", None)
                        if rc:
                            for c in rc:
                                ce = getattr(c, "expr", None)
                                if ce:
                                    ct = h.get_signal(ce) or str(ce).strip()
                                    if ct:
                                        cond_texts.append(ct)
                        cs = " && ".join(cond_texts) if cond_texts else ""
                        left = getattr(cond_op, "left", None)
                        right = getattr(cond_op, "right", None)
                        if left:
                            lk = str(getattr(left, "kind", ""))
                            if "ConditionalOp" in lk or "ConditionalExpression" in lk:
                                result.update(_build_cond_map(left, path + [cs]))
                            elif "NamedValue" in lk:
                                name = h.get_signal(left) or ""
                                fc = " && ".join([p for p in path + [cs] if p])
                                if name:
                                    result[name] = fc
                        if right:
                            rk = str(getattr(right, "kind", ""))
                            if "ConditionalOp" in rk or "ConditionalExpression" in rk:
                                result.update(_build_cond_map(right, path + [f"!({cs})"]))
                            elif "NamedValue" in rk:
                                name = h.get_signal(right) or ""
                                neg = f"!({cs})" if cs else ""
                                fc = " && ".join([p for p in path + [neg] if p])
                                if name:
                                    result[name] = fc
                        return result

                    cond_map = _build_cond_map(check_expr)
                    signal_conditions = [(s, cond_map.get(s, "")) for s in leaf_signals2]

                    signal_conditions = h.filter_signal_conditions_by_module(
                        signal_conditions, module=module
                    )
                    # [V6.3+1 2026-07-27 FIX] combine the outer condition (from
                    # case/if ctx, e.g. "sel_d == 2'd0") with the inner ternary
                    # sig_cond (e.g. "sel_f") so the edge shows the full
                    # guarding condition, not just the inner ternary.
                    outer_cond = ctx.get("condition", "") or ""
                    # [V7.0] 构建完整 condition_chain: 外层 + 内层
                    outer_chain = ctx.get("condition_chain", []) or []
                    for sig_rhs_name, sig_cond in signal_conditions:
                        if not sig_rhs_name:
                            continue
                        # Combine outer AND inner with " && " when both present
                        if outer_cond and sig_cond:
                            combined_cond = f"({outer_cond}) && ({sig_cond})"
                        else:
                            combined_cond = outer_cond or sig_cond
                        # [V7.0] condition_chain 列表: 外层链 + 内层条件
                        if sig_cond:
                            full_chain = (list(outer_chain) if outer_chain else []) + [sig_cond]
                        else:
                            full_chain = list(outer_chain) if outer_chain else []
                        bit_slice = ""
                        if "[" in sig_rhs_name and "]" in sig_rhs_name:
                            start = sig_rhs_name.index("[")
                            bit_slice = sig_rhs_name[start:]
                        if sig_rhs_name and not sig_rhs_name[0].isalpha() and not sig_rhs_name.startswith("_"):
                            result.edges.append(
                                h.edge_factory.make_edge(
                                    src=sig_rhs_name,
                                    dst=dst_node_id,
                                    kind=EdgeKind.DRIVER,
                                    assign_type="nonblocking",
                                    expression=sig_rhs_name,
                                    bit_slice=bit_slice,
                                    clock_domain=ctx.get("clock", ""),
                                    sig_cond=combined_cond,
                                    condition_chain=full_chain,
                                    ctx=ctx,
                                )
                            )
                        else:
                            src_node_id = f"{module_name}.{sig_rhs_name}"
                            if src_node_id not in [n.id for n in result.nodes]:
                                result.nodes.append(
                                    TraceNode(
                                        id=src_node_id,
                                        name=sig_rhs_name,
                                        module=module_name,
                                        kind=NodeKind.SIGNAL,
                                        width=(1, 0),
                                    )
                                )
                            # [V6.5] 结构化驱动源
                            ds = h.build_signal_source(sig_rhs_name, check_expr, expr_str)
                            result.edges.append(
                                h.edge_factory.make_edge(
                                    src=src_node_id,
                                    dst=dst_node_id,
                                    kind=EdgeKind.DRIVER,
                                    assign_type="nonblocking",
                                    expression=expr_str,
                                    bit_slice=bit_slice,
                                    clock_domain=ctx.get("clock", ""),
                                    sig_cond=combined_cond,
                                    condition_chain=full_chain,
                                    ctx=ctx,
                                    source=ds,
                                )
                            )
                else:
                    for rhs_name in rhs_signals:
                        if not rhs_name:
                            continue
                        bit_slice = ""
                        if "[" in rhs_name and "]" in rhs_name:
                            start = rhs_name.index("[")
                            bit_slice = rhs_name[start:]
                        if rhs_name and not rhs_name[0].isalpha() and not rhs_name.startswith("_"):
                            sig_cond = ctx.get("condition", "")
                            result.edges.append(
                                h.edge_factory.make_edge(
                                    src=rhs_name,
                                    dst=dst_node_id,
                                    kind=EdgeKind.DRIVER,
                                    assign_type="nonblocking",
                                    bit_slice=bit_slice,
                                    expression=rhs_name,
                                    sig_cond=sig_cond,
                                    condition=sig_cond,
                                    condition_chain=[sig_cond] if sig_cond else [],
                                    ctx=ctx,
                                )
                            )
                        else:
                            src_node_id = f"{module_name}.{rhs_name}"
                            if src_node_id not in [n.id for n in result.nodes]:
                                result.nodes.append(
                                    TraceNode(
                                        id=src_node_id,
                                        name=rhs_name,
                                        module=module_name,
                                        kind=NodeKind.SIGNAL,
                                        width=(1, 0),
                                    )
                                )
                            # [V6.5] 结构化驱动源
                            ds = h.build_signal_source(rhs_name, rhs_expr, expr_str)
                            sig_cond = ctx.get("condition", "")
                            result.edges.append(
                                h.edge_factory.make_edge(
                                    src=src_node_id,
                                    dst=dst_node_id,
                                    kind=EdgeKind.DRIVER,
                                    assign_type="nonblocking",
                                    bit_slice=bit_slice,
                                    expression=expr_str,
                                    sig_cond=sig_cond,
                                    condition=sig_cond,
                                    condition_chain=[sig_cond] if sig_cond else [],
                                    ctx=ctx,
                                    source=ds,
                                )
                            )

                # [NEW] CLOCK 边: always_ff 块内创建 clk -> dst (CLOCK) 边
                clock_signal = ctx.get("clock", "")
                if clock_signal:
                    clock_node_id = f"{module_name}.{clock_signal}"
                    if clock_node_id not in [n.id for n in result.nodes]:
                        result.nodes.append(
                            TraceNode(
                                id=clock_node_id,
                                name=clock_signal,
                                module=module_name,
                                kind=NodeKind.SIGNAL,
                                width=(1, 0),
                            )
                        )
                    result.edges.append(
                        h.edge_factory.make_edge(
                            src=clock_node_id,
                            dst=dst_node_id,
                            expression="",  # CLOCK 边无 expression
                            kind=EdgeKind.CLOCK,
                            assign_type="nonblocking",
                            clock_domain=clock_signal,
                            ctx=ctx,
                        )
                    )

                # [NEW] RESET 边: always_ff 块内创建 rst -> dst (RESET) 边
                reset_signal = ctx.get("reset", "")
                if reset_signal:
                    reset_node_id = f"{module_name}.{reset_signal}"
                    if reset_node_id not in [n.id for n in result.nodes]:
                        result.nodes.append(
                            TraceNode(
                                id=reset_node_id,
                                name=reset_signal,
                                module=module_name,
                                kind=NodeKind.SIGNAL,
                                width=(1, 0),
                            )
                        )
                    result.edges.append(
                        h.edge_factory.make_edge(
                            src=reset_node_id,
                            dst=dst_node_id,
                            expression="",  # RESET 边无 expression
                            kind=EdgeKind.RESET,
                            assign_type="nonblocking",
                            clock_domain=clock_signal,
                            ctx=ctx,
                        )
                    )


                # [Phase 7.3 / Fix A 2026-07-13] CONDITION-DRIVEN drivers
                # Bug: 在 if-else statement-level conditions 里,
                # q <= literal_only 会被简化为 `literal → q` 边,
                # 但 condition 里的信号 (e.g. cpu_state) 不会作为 driver 出现.
                # 修复: 从 ctx.effective_condition 提取所有信号名, 添加为 DRIVER 边
                # (kind=DRIVER 但带 sig_cond, 让 trace_fanin/dataflow 能找到完整 driver chain).
                _add_condition_drivers(
                    dst_node_id, ctx, module_name, result, h=h
)




def _add_condition_drivers(dst_node_id: str,
        ctx: dict,
        module_name: str,
        result, *, h: 'AlwaysHelpers') -> None:
    """[Phase 7.6 / Fix E.4 2026-7-14] Disabled: condition signals no longer
    added as DRIVER edges.

    ROOT CAUSE (user verified 2026-7-14):
    Fix A (2026-7-13) added cond signals as DRIVER edges.
    test_case_stmt / test_complex_conditions golden expects "drivers = RHS only":
      - case (sel) 2'b00: y=a;  → drivers = [a, b, 0], NOT sel
      - if (a) q<=b;            → drivers = [b],       NOT a
      - case (1'b1) a: y=1;     → drivers = [1, 0],   NOT a, b
    Fix A violates dataflow semantics: dataflow driver = the actual value
    expression (RHS), condition is only gating context (controlflow).

    REMEDIATION:
    1. condition signals do NOT enter driver list
    2. RHS extraction still produces drivers (test cases pass)
    3. condition still stored in sig_cond context (for controlflow queries)
    4. picorv32.trap trace_fanin improvement comes from more precise RHS
       extraction (separate fix)

    Keep Fix C/D/E.1 infrastructure: _collect_signals_from_ast,
    _is_sv_literal_token still available for controlflow/coverage analysis,
    just don't write DRIVER edges.
    """
    # [Phase 7.6 / Fix E.4] No-op: compute cond_signals for analysis but don't
    # write DRIVER edges. Tests want drivers = RHS only.
    cond_signals: set[str] = set()

    # AST extraction (Fix C/D infrastructure, not used for graph)
    ast_nodes: list = []
    cond_exprs_list = ctx.get("_cond_exprs") or []
    if isinstance(cond_exprs_list, list):
        ast_nodes.extend(cond_exprs_list)
    condition_ast = ctx.get("condition_ast")
    if condition_ast is not None:
        ast_nodes.append(condition_ast)

    for ast_node in ast_nodes:
        if ast_node is None:
            continue
        try:
            _collect_signals_from_ast(ast_node, cond_signals, h=h)
        except Exception as e:
            logger.warning("条件信号收集失败: %s", e)
            pass

    # Fallback string scan (Fix E.1 filter applied, but no DRIVER edge written)
    if not cond_signals:
        effective_cond = ctx.get("effective_condition", "")
        if effective_cond:
            current = ""
            for c in effective_cond:
                if c.isalnum() or c == "_":
                    current += c
                elif c == "[":
                    continue
                else:
                    if current and current not in ("0", "1"):
                        if not h.is_sv_literal_token(current):
                            cond_signals.add(current)
                    current = ""
            if current and current not in ("0", "1"):
                if not h.is_sv_literal_token(current):
                    cond_signals.add(current)

    # [Phase 7.6 / Fix E.4] DO NOT write DRIVER edges.
    # Original edge-creation loop removed. Tests expect drivers = RHS only.
    return
    _EXCLUDED_SYMBOL_KINDS = {
    "Parameter",        # parameter [2:0] cpu_state_trap = 3'd0;
    "EnumValue",       # enum value (same as Parameter effectively)
    "TypeParameter",    # type parameter
    "Specparam",        # specparam
    "Genvar",           # generate variable (compile-time)
    }




def _collect_signals_from_ast(ast_node, cond_signals, *, h: 'AlwaysHelpers'):
    """[Phase 7.5 / Fix D 2026-07-13] Traverse AST to extract NamedValueExpression,
    but skip Symbol kind = parameter/enum value (compile-time constants).

    Difference from _signal_visitor.get_all_signals(): this version checks
    symbol.kind to exclude Parameter/EnumValue/etc, keeping only real signals.
    """
    if ast_node is None:
        return

    # NamedValueExpression: simple variable reference
    if hasattr(ast_node, "symbol") and hasattr(ast_node, "kind"):
        sym = getattr(ast_node, "symbol", None)
        if sym is not None:
            # Check symbol kind - skip parameters/enum values
            sym_kind = getattr(sym, "kind", None)
            sym_kind_name = str(sym_kind).split(".")[-1] if sym_kind else ""
            if sym_kind_name in _EXCLUDED_SYMBOL_KINDS:
                return  # Skip this NamedValue, don't recurse
            # Real signal - extract name
            try:
                name = sym.name
            except (UnicodeDecodeError, TypeError, Exception):
                name = None
            if name:
                name = name.strip() if isinstance(name, str) else str(name)
                if _is_valid_signal_name(name, h=h):
                    # Strip bit select suffix [..]
                    if "[" in name:
                        name = name.split("[", 1)[0]
                    if name and _is_valid_signal_name(name, h=h):
                        cond_signals.add(name)
            return  # NamedValue, no need to recurse

    # Recurse into child nodes
    for attr in ("left", "right", "value", "operand", "operand0", "operand1",
                 "expression", "expr", "elements", "operands", "args", "arguments"):
        child = getattr(ast_node, attr, None)
        if child is None:
            continue
        if isinstance(child, list):
            for c in child:
                if c is not None:
                    _collect_signals_from_ast(c, cond_signals, h=h)
        else:
            _collect_signals_from_ast(child, cond_signals, h=h)



def _is_valid_signal_name(name, *, h: 'AlwaysHelpers'):
    """Check if looks like a valid SV identifier (exclude AST noise and literals)"""
    if not name or len(name) < 2:
        return False
    if not (name[0].isalpha() or name[0] == "_"):
        return False
    if not all(c.isalnum() or c == "_" for c in name):
        return False
    if name.isdigit() or name in ("0", "1"):
        return False
    if "'" in name:  # SystemVerilog literal like "2'b10"
        return False
    return True



def _collect_stmts_with_context(n, ctx=None, *, h: 'AlwaysHelpers', genvar_ctx: dict | None = None) -> list[tuple[Any, dict[str, str], Any]]:
    """[V6.9] 用 semantic API 收集 always 块中的语句和 clock context。

    不再依赖已删除的 StatementCollectorVisitor。
    从 syntax AST 获取 clock/reset 信号和 if/case 脉络，
    并用 semantic adapter 获取语句列表。

    [#8 2026-08-28] genvar_ctx: generate-for 内展开的 always 块的
    {genvar_name: entry.arrayIndex} 上下文 (e.g. {'i': 0})。注入每条返回
    item 的 ctx["_genvar"], 供 _create_always_edges 做 lhs genvar substitute。
    """
    if ctx is None:
        ctx = {}

    # 1. 从 syntax 层提取 clock 和 reset 信号
    clock = _extract_clock_from_always(n, h=h)
    reset = _extract_reset_from_always(n, h=h)
    if clock:
        ctx["clock"] = clock
    if reset:
        ctx["reset"] = reset

    # 2. 从 syntax 层获取语句体 (带条件信息)
    items = _get_always_body_items(n, h=h)
    if not items:
        return items

    # 3. 处理条件脉络（if/case 等）
    #    _flatten_assignments 现在返回 (expr, cond_chain) 或 (expr, cond_chain, leaf_name) 元组
    #    cond_chain 是 list[str] (V7.0), 旧版 cond_str 是字符串
    #    leaf_name != None 表示 ternary 展开后的 leaf 信号（覆盖 rhs 信号提取）
    #    每个 item 带有自己的条件
    result = []
    for item in items:
        if isinstance(item, tuple) and len(item) >= 2:
            expr_node, cond_or_chain = item[0], item[1]
            leaf_name = item[2] if len(item) >= 3 else None
            item_ctx = dict(ctx)  # copy base ctx
            if genvar_ctx:
                item_ctx["_genvar"] = dict(genvar_ctx)
            if isinstance(cond_or_chain, list):
                # [V7.0] condition_chain: list[str]
                item_ctx["condition_chain"] = list(cond_or_chain)
                item_ctx["condition"] = " && ".join(cond_or_chain) if cond_or_chain else ""
            elif cond_or_chain:
                # 旧接口: 字符串 (向后兼容)
                item_ctx["condition"] = cond_or_chain
                item_ctx["condition_chain"] = [cond_or_chain] if " && " not in cond_or_chain else cond_or_chain.split(" && ")
            # [Plan F3-pre 2026-08-13] 回填 condition_ast: 从条件链反查 AST,
            # 取最内层 (最后一个) 条件对应的 AST 节点。修复 graph_builder
            # condition_ast 填充链路断裂 (48 条条件边全 None 的根因).
            chain = item_ctx.get("condition_chain") or []
            cond_ast = None
            for c in reversed(chain):
                ast_node = h.cond_ast_by_str.get(c)
                if ast_node is not None:
                    cond_ast = ast_node
                    break
            if cond_ast is not None:
                item_ctx["condition_ast"] = cond_ast
            if leaf_name:
                item_ctx["leaf_name"] = leaf_name
            result.append((expr_node, item_ctx, None))
        else:
            result.append((item, ctx, None))

    return result




def _extract_reset_from_always(n, *, h: 'AlwaysHelpers') -> str:
    """[V6.9] 提取 reset 信号 — 优先 semantic AST .timing.events, fallback syntax tree。

    策略:
    1. 优先找 NegEdge event（异步低有效复位）
    2. 如果 events >= 2, 第二个 event 的信号也是 reset（posedge rst 场景）
    """
    reset_signal = ""
    events = []
    # [V6.9] 优先 semantic AST: TimedStatement.timing.events (SignalEventControl list)
    body = getattr(n, "body", None)
    timing = getattr(body, "timing", None) if body else None
    if timing:
        events = getattr(timing, "events", None) or []
    # Fallback: syntax tree timingControl.events
    if not events:
        syntax = getattr(n, "syntax", None)
        if syntax:
            tc = getattr(syntax, "timingControl", None)
            if tc:
                events = getattr(tc, "events", []) or []
    if events and hasattr(events, "__iter__") and not isinstance(events, str):
        evt_list = list(events)
        # 策略 1: 找 NegEdge（异步低有效复位）
        for evt in evt_list:
            edge_str = str(getattr(evt, "edge", ""))
            if "NegEdge" in edge_str:
                expr = getattr(evt, "expr", None) or getattr(evt, "expression", None)
                if expr:
                    sig = h.get_signal(expr)
                    reset_signal = sig if (sig and not sig.startswith("Expression(")) else str(expr).strip()
                    break
        # 策略 2: 如果没有 NegEdge 但 events >= 2, 第二个是 reset（posedge rst 场景）
        if not reset_signal and len(evt_list) >= 2:
            evt = evt_list[1]
            expr = getattr(evt, "expr", None) or getattr(evt, "expression", None)
            if expr:
                sig = h.get_signal(expr)
                reset_signal = sig if (sig and not sig.startswith("Expression(")) else str(expr).strip()
    return reset_signal




def _get_always_body_items(n, *, h: 'AlwaysHelpers') -> list:
    """[V6.9] 从 semantic AST 获取 flat assignment expressions。

    全部使用 semantic AST (StatementKind/ExpressionKind)。

    - always @(posedge clk): ProceduralBlock.body = TimedStatement → .stmt
    - initial:           ProceduralBlock.body = ExpressionStatement / BlockStatement
    - always_comb:       ProceduralBlock.body = BlockStatement / ExpressionStatement
    """
    sem_body = getattr(n, "body", None)
    if sem_body is None:
        return []

    kind = getattr(sem_body, "kind", None)
    # TimedStatement: unwrap timing wrapper
    if kind == StatementKind.Timed:
        inner = getattr(sem_body, "stmt", None) or getattr(sem_body, "statement", None)
        if inner is None:
            return []
        sem_body = inner

    items = []
    h.flatten_semantic(sem_body, items)
    return items
