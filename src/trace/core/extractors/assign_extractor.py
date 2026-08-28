# ==============================================================================
# extractors/assign_extractor.py - continuous assign 语句 driver 边提取
#
# [ARCHITECTURE_TODOLIST #1 Step 4 2026-08-28]
# 从 driver_extractor.py 拆出 assign phase 全部 5 个方法 + 2 个专属 helper (580 行):
#   - _create_assign_edges              (25 行) 主入口, 4-way dispatch
#   - _handle_concat_assign             (90 行) 5a: Concatenation 拼接赋值
#   - _handle_call_assign               (27 行) 5b: RHS 是 CallExpression
#   - _handle_binary_invocation_assign  (26 行) 5c: Binary 含 Invocation
#   - _handle_normal_assign            (329 行) 5d: 其他 (最大, 见下方 TODO)
#   - _extract_assign_lr                (14 行) assign 专属: 解包 .left/.right
#   - _extract_ternary_condition        (69 行) assign 专属: 三元条件提取
#
# ── 为什么用 AssignHelpers 打包而不是逐个传 Callable ────────────────────────
# 本模块依赖 driver_extractor 的 13 个共享 helper。Step 1+2/3b 只需 2-6 个,
# 直接做关键字参数即可; 到 13 个时逐个传会让每个 handler 签名膨胀到 15 行,
# 且 handler 之间互调要层层转发 —— 比拆分前更难读, 违背"函数应简洁"。
#
# 故打包成 AssignHelpers (dataclass): 调用方构造一次, 内部统一 h.xxx 访问。
# 这些 helper 仍**留在 driver_extractor**, 因为它们是全文件共享基础设施
# (_get_signal 33 处调用; _parse_assign / _expr_is_compile_time /
#  _filter_signal_conditions_by_module / _build_signal_source 被
#  _create_always_edges 共用 —— 属 Step 6 范围, 不能提前搬走)。
#
# ── 行为契约 (必须 1:1 跟原方法一致, 测试保护) ──────────────────────────────
# - dispatch 顺序必须是 concat → call → binary_invocation → normal (短路 return True)
# - 每个 assign 独立取 genvar_ctx (generate-for 内 acc[i+1] 需 substitute i → N)
# - 所有边 assign_type="continuous", kind=EdgeKind.DRIVER
# - _handle_normal_assign 内 ScopedName (tb.data) 要建 instance 路径上所有父节点
#
# ── TODO (不在 Step 4 范围) ─────────────────────────────────────────────────
# _handle_normal_assign 有 329 行, 远超 AGENTS.md 的 ~50 行阈值。内部有 4 个
# 清晰分段 (ScopedName 处理 / wrapper unwrap / conditional fallback / expr tree),
# 可进一步拆成子函数。但那是**行为重构**, 与本次"搬文件"混在一个 commit 会
# 难以归因回归。已单独记录, 建议 Step 4b 处理。
# ==============================================================================
from dataclasses import dataclass
from typing import Any, Callable

from ..ast_utils import kind_matches, unwrap
from ..graph.models import EdgeKind, NodeKind, TraceNode


@dataclass
class AssignHelpers:
    """[Step 4 2026-08-28] driver_extractor 共享 helper 的注入包.

    由 DriverExtractor._create_assign_edges 薄壳构造并传入。
    字段名去掉了原方法的下划线前缀 (self._get_signal → h.get_signal)。
    """

    adapter: Any
    store_expr_tree: Callable
    get_signal: Callable
    get_all_signals: Callable
    get_all_real_signals: Callable
    build_signal_source: Callable
    append_edge: Callable
    handle_invocation: Callable
    find_invocations: Callable
    parse_assign: Callable
    expr_is_compile_time: Callable
    filter_compile_time_signal_names: Callable
    filter_signal_conditions_by_module: Callable
    signal_visitor: Any = None
    edge_factory: Any = None


def create_assign_edges(module, result, module_name, *, h: 'AssignHelpers'):
    """[REFACTOR 2026-06-26] 处理所有 continuous assign 语句.

    4 sub-phase dispatch:
    - 5a: _handle_concat_assign (LHS/RHS 是 Concatenation)
    - 5b: _handle_call_assign (RHS 是 CallExpression)
    - 5c: _handle_binary_invocation_assign (Binary 含 Invocation)
    - 5d: _handle_normal_assign (其他)
    """
    for assign in h.adapter.get_assignments(module):
        # [G1 iter_038] Plan F1: 从 assign 拿 genvar_ctx (generate for 内的 iteration)
        #   gen_accum[1] → ctx={'i': 1}, acc[i+1] RHS 里 'i' substitute 成 '1'
        try:
            genvar_ctx = h.adapter.get_genvar_context(assign) or {}
        except Exception:
            genvar_ctx = {}
        raw_lhs, raw_rhs = _extract_assign_lr(assign)
        if _handle_concat_assign(assign, raw_lhs, raw_rhs, module, result, module_name, genvar_ctx, h=h):
            continue
        if _handle_call_assign(assign, raw_lhs, raw_rhs, module, result, module_name, genvar_ctx, h=h):
            continue
        if _handle_binary_invocation_assign(assign, raw_lhs, raw_rhs, module, result, module_name, genvar_ctx, h=h):
            continue
        _handle_normal_assign(assign, module, result, module_name, genvar_ctx, h=h)



def _handle_concat_assign(assign, raw_lhs, raw_rhs, module, result, module_name, genvar_ctx: dict | None = None, *, h: 'AssignHelpers') -> bool:
    """[REFACTOR 2026-06-26] 5a: 处理 Concatenation 拼接赋值. 处理了 return True (已 dispatch), 否则 False."""
    if not (raw_lhs and hasattr(raw_lhs, "kind") and "Concatenation" in str(raw_lhs.kind)):
        return False
    # 提取 LHS 拼接中的所有位选信号
    lhs_elements = []
    lhs_operands = getattr(raw_lhs, "operands", None) or getattr(raw_lhs, "expressions", None)
    if lhs_operands and hasattr(lhs_operands, "__iter__") and not isinstance(lhs_operands, str):
        for op in lhs_operands:
            op_kind = getattr(op, "kind", None)
            if not op_kind or "Token" in str(op_kind):
                continue
            if "ElementSelect" in str(op_kind) or "RangeSelect" in str(op_kind):
                name = h.get_signal(op)
                if name:
                    lhs_elements.append(name)
            elif "Identifier" in str(op_kind) or "NamedValue" in str(op_kind):
                name = h.get_signal(op)
                if name:
                    lhs_elements.append(name)

    # 提取 RHS 拼接中的所有信号
    # [FIX 2026-06-26] 当 LHS 是 concat 但 RHS 不是 (e.g. CallExpression),
    # return False 让 _handle_call_assign 接着处理 (跟原代码 if-elif chain 行为一致)
    if not (raw_rhs and hasattr(raw_rhs, "kind") and "Concatenation" in str(raw_rhs.kind)):
        return False
    rhs_signals = []
    rhs_operands = getattr(raw_rhs, "operands", None) or getattr(raw_rhs, "expressions", None)
    if rhs_operands and hasattr(rhs_operands, "__iter__") and not isinstance(rhs_operands, str):
        for op in rhs_operands:
            op_kind = getattr(op, "kind", None)
            if not op_kind or "Token" in str(op_kind):
                continue
            signals = h.get_all_signals(op)
            if signals:
                rhs_signals.extend(signals)

    # 为 LHS 的每个元素创建节点和边
    for lhs_name in lhs_elements:
        dst_node_id = f"{module_name}.{lhs_name}"
        if dst_node_id not in [n.id for n in result.nodes]:
            result.nodes.append(
                TraceNode(
                    id=dst_node_id,
                    name=lhs_name,
                    module=module_name,
                    kind=NodeKind.SIGNAL,
                    width=(1, 0),
                )
            )

        # 对齐映射: rhs_signals[i] -> lhs_elements[i]
        for rhs_sig in rhs_signals:
            if rhs_sig and not rhs_sig[0].isalpha() and not rhs_sig.startswith("_"):
                # [V4] factory 统一入口
                h.append_edge(
                    result,
                    src=rhs_sig,
                    dst=dst_node_id,
                    kind=EdgeKind.DRIVER,
                    assign_type="continuous",
                )
            else:
                src_node_id = f"{module_name}.{rhs_sig}"
                if src_node_id not in [n.id for n in result.nodes]:
                    result.nodes.append(
                        TraceNode(
                            id=src_node_id,
                            name=rhs_sig,
                            module=module_name,
                            kind=NodeKind.SIGNAL,
                            width=(1, 0),
                        )
                    )
                # [V4] factory 统一入口
                h.append_edge(
                    result,
                    src=src_node_id,
                    dst=dst_node_id,
                    kind=EdgeKind.DRIVER,
                    assign_type="continuous",
                )
    # [REFACTOR 2026-08-07 A计划] 拼接赋值: assign y = {a, b};
    # raw_rhs 是 Concat semantic 节点，.syntax 构建 Concat 树
    if raw_lhs is not None:
        lst = h.get_signal(raw_lhs)
        if lst and raw_rhs is not None:
            h.store_expr_tree(lst, raw_rhs, module_name, result, genvar_ctx=genvar_ctx)
    return True



def _handle_call_assign(assign, raw_lhs, raw_rhs, module, result, module_name, genvar_ctx: dict | None = None, *, h: 'AssignHelpers') -> bool:
    """[REFACTOR 2026-06-26] 5b: 处理 RHS 是 CallExpression (函数调用)."""
    if not (raw_rhs and hasattr(raw_rhs, "kind") and "Call" in str(raw_rhs.kind)):
        return False
    # 先创建 LHS 节点(函数调用的目标)
    lhs_name = None
    if raw_lhs:
        lhs_name = h.get_signal(raw_lhs)
        if lhs_name:
            dst_node_id = f"{module_name}.{lhs_name}"
            if dst_node_id not in [n.id for n in result.nodes]:
                result.nodes.append(
                    TraceNode(
                        id=dst_node_id,
                        name=lhs_name,
                        module=module_name,
                        kind=NodeKind.SIGNAL,
                        width=(1, 0),
                    )
                )
    # 调用 _handle_invocation,传入 lhs_name 作为目标
    h.handle_invocation(raw_rhs, {}, module, module_name, result, lhs_name)
    # [REFACTOR 2026-08-07 A计划] 函数调用赋值: assign y = func(a,b);
    if lhs_name and raw_rhs is not None:
        h.store_expr_tree(lhs_name, raw_rhs, module_name, result, genvar_ctx=genvar_ctx)
    return True



def _handle_binary_invocation_assign(assign, raw_lhs, raw_rhs, module, result, module_name, genvar_ctx: dict | None = None, *, h: 'AssignHelpers') -> bool:
    """5c: 处理 BinaryExpression 包含 InvocationExpression.

    例: assign result = a & my_func(b);
    raw_lhs/raw_rhs 由 _create_assign_edges 经 _extract_assign_lr 解包传入
    (与其他 handler 签名一致).

    [FIX 2026-08-07] case19 overflow 孤立根因:
    之前内部用 `assign.assignments[0].left` 重新提取 raw_lhs, 对语义 AST
    ContinuousAssignSymbol 只有 .assignment 无 .assignments → raw_lhs=None
    → lhs_name=None → 不建 sat_add→overflow 返回边 + 不存 expr_tree
    → overflow 输出节点孤立. 已改为直接接收解包的 raw_lhs.
    """
    if not (raw_rhs and hasattr(raw_rhs, "kind") and "Binary" in str(raw_rhs.kind)):
        return False
    invocations_found = h.find_invocations(raw_rhs)
    if not invocations_found:
        return False
    lhs_name = h.get_signal(raw_lhs) if raw_lhs else None
    for invocation in invocations_found:
        h.handle_invocation(invocation, {}, module, module_name, result, lhs_name)
    # [REFACTOR 2026-08-07 A计划] 二元+函数调用赋值: assign y = a & func(b);
    if lhs_name and raw_rhs is not None:
        h.store_expr_tree(lhs_name, raw_rhs, module_name, result, genvar_ctx=genvar_ctx)
    return True



def _handle_normal_assign(assign, module, result, module_name, genvar_ctx: dict | None = None, *, h: 'AssignHelpers') -> None:
    """[REFACTOR 2026-06-26] 5d: 默认 assign 处理 (call/concat/binary-invocation 之外的).

    处理 ScopedName (tb.data), ConditionalOp, bit_slice, 等.
    这是最大的 sub-method (~197 lines).
    """
    lhs, rhs, rhs_expr = h.parse_assign(assign)
    if not (lhs and (rhs or rhs_expr is not None)):
        return
    # [FIX] ScopedName: tb.data → 创建 instance 路径上的所有父节点
    if "." in lhs:
        lhs_parts = lhs.split(".")
        for i in range(1, len(lhs_parts)):
            parent_name = ".".join(lhs_parts[:i])
            parent_id = f"{module_name}.{parent_name}"
            if parent_id not in [n.id for n in result.nodes]:
                result.nodes.append(
                    TraceNode(
                        id=parent_id,
                        name=parent_name,
                        module=module_name,
                        kind=NodeKind.PORT_IN,
                        width=(1, 0),
                    )
                )
        # [Plan E1.3 2026-08-10] 删除错误的 BIT_SELECT 边生成.
        #
        # 旧代码对所有 '.' 分隔的路径生成 BIT_SELECT 边, 包括
        # instance 路径 (e.g., u_scale.din → u_scale). 但 u_scale 是
        # module 实例名, 不是信号, 这条边没语义意义.
        #
        # 真 BIT_SELECT (e.g., data[7:0] → data, din[3:0] → din)
        # 由 bit_select_handler._create_hierarchical_bit_nodes() 处理,
        # 那里只对含 '[..]' 的 bit slice 节点生成, 是正确的.
        #
        # 修后效果:
        # - case26 (golden_hier_top) 错 BIT_SELECT 边从 12 个 → 0
        # - viz.edges 减少 12 条无效边
        # - checker E1 filter 不再需要 filter 这类误报

    dst_node_id = f"{module_name}.{lhs}"
    if dst_node_id not in [n.id for n in result.nodes]:
        result.nodes.append(TraceNode(id=dst_node_id, name=lhs, module=module_name, kind=NodeKind.SIGNAL, width=(1, 0)))
    rhs_kind = str(getattr(rhs_expr, "kind", "")) if rhs_expr else ""
    if "EqualsValueClause" in rhs_kind:
        rhs_signals = []
    else:
        rhs_signals = h.get_all_real_signals(rhs_expr, module=module, genvar_ctx=genvar_ctx) if rhs_expr else [rhs]

    ternary_condition = _extract_ternary_condition(rhs_expr)

    # [V6.3+3 2026-07-27] Use ast_utils for wrapper unwrap and kind
    # matching. Replaces 4 duplicated unwrap blocks across this file.
    has_conditional = False
    check_expr = rhs_expr
    for _ in range(10):  # 解包多层包装 (最多 10 层, $signed(Conditional) 需要 <10)
        if check_expr is None:
            break
        if kind_matches(check_expr, "ConditionalOp", "ConditionalExpression"):
            has_conditional = True
            break
        # [V6.9] Also unwrap Call (system function) — e.g. $signed(g ? x0 : x1)
        # where the ternary is an argument to the system function call
        ck = str(getattr(check_expr, "kind", ""))
        if "Call" in ck:
            args = getattr(check_expr, "arguments", None)
            if args and hasattr(args, "__iter__") and not isinstance(args, str):
                for arg in args:
                    if kind_matches(arg, "ConditionalOp", "ConditionalExpression"):
                        check_expr = arg
                        has_conditional = True
                        break
            if has_conditional:
                break
        inner = unwrap(check_expr)
        if inner is None or inner is check_expr:
            break
        check_expr = inner

    if not rhs_signals:
        # [Phase 8 / Fix F 2026-7-14] If rhs_expr is a compile-time symbol (parameter,
        # enum value, localparam), don't fall back to [rhs] - that would re-add
        # the parameter as a fake driver.
        # [FIX 2026-7-15] Pass module for Syntax AST resolution.
        if rhs_expr is not None and h.expr_is_compile_time(rhs_expr, module=module):
            rhs_signals = []  # Stay empty, no driver
        elif has_conditional:
            # [V6.9] rhs_expr wrapped (e.g. $signed(ternary)): use unwrapped check_expr
            rhs_signals = h.get_all_real_signals(check_expr, module=module, genvar_ctx=genvar_ctx) or []
        else:
            rhs_signals = [rhs]

    # [V6.9] If has_conditional but rhs_signals still empty after above fallback,
    # try one more time with the unwrapped ternary expression
    if has_conditional and not rhs_signals:
        rhs_signals = h.signal_visitor._extract_signals_from_expr(check_expr) or []
        rhs_signals = h.filter_compile_time_signal_names(check_expr, rhs_signals, module=module)
    if rhs_expr:
        try:
            expr_str = h.signal_visitor.get_source_text(rhs_expr) or str(rhs_expr) or h.signal_visitor.get_source_text(rhs_expr) or str(rhs_expr)
        except (UnicodeDecodeError, TypeError):
            expr_str = "<expr:non-utf8>"
    else:
        expr_str = rhs or ""

    if has_conditional:
        # [Phase 8 / Fix F.6 2026-7-15] Filter compile-time symbols
        # (localparam/parameter) from ternary branch signals.
        # [V6.3+4 2026-07-28] Pass UNWRAPPED check_expr to
        # get_signals_with_conditions so the visitor sees the
        # ConditionalOp directly (not the outer ParenthesizedExpression).
        # This mirrors V6.3+1 fix in _create_always_edges bug #2.
        #
        # [V6.9 FIX] semantic_adapter returns list[str] (ALL signals).
        # Must separate condition signals (g, h) from leaf signals (x0, x1).
        all_signals = h.signal_visitor._extract_signals_from_expr(check_expr) or []

        # [V6.9] 递归收集所有层的条件信号名
        # g ? (h ? x0 : x1) : x2 → 条件信号 = {g, h}
        def _collect_cond_signals(cond_op, acc_set):
            if cond_op is None:
                return
            ck = str(getattr(cond_op, "kind", ""))
            if "ConditionalOp" not in ck and "ConditionalExpression" not in ck:
                return
            rc = getattr(cond_op, "conditions", None)
            if rc:
                for c in rc:
                    ce = getattr(c, "expr", None) or getattr(c, "expression", None)
                    if ce:
                        for s in (h.signal_visitor._extract_signals_from_expr(ce) or []):
                            acc_set.add(s)
            _collect_cond_signals(getattr(cond_op, "left", None), acc_set)
            _collect_cond_signals(getattr(cond_op, "right", None), acc_set)
        cond_sig_names = set()
        _collect_cond_signals(check_expr, cond_sig_names)

        # [FIX 2026-08-09 A方案] 用分支信号作为 leaf_signals, 而不是从 all_signals 排除条件信号.
        # 原逻辑 'leaf_signals = [s for s in all_signals if s not in cond_sig_names]' 在
        # 'z = (a > b) ? (a - b) : 8'd0' 这类嵌套表达式 cond 场景下丢边:
        #   all_signals = {a, b}, cond_sig_names = {a, b} (a、b 同时出现在 cond 和 branch)
        #   leaf_signals = {} → 0 条边生成 → z 在 viz.edges 里消失 → viz_to_elk 不会为 z
        #   生成 case 框 → port_out 'z' 在 SVG 里孤儿.
        # 修复: 递归收集 ternary 分支 (left/right) 里出现的所有信号, 这才是真正的
        # 'driver 来源信号'. 'cond_sig_names' 仅用于去重/参考, 不作为排除集.
        branch_sigs = set()
        def _collect_branch_signals(cond_op):
            if cond_op is None:
                return
            ck = str(getattr(cond_op, "kind", ""))
            if "ConditionalOp" not in ck and "ConditionalExpression" not in ck:
                return
            for arm in [getattr(cond_op, "left", None), getattr(cond_op, "right", None)]:
                if arm is None:
                    continue
                ak = str(getattr(arm, "kind", ""))
                if "ConditionalOp" in ak or "ConditionalExpression" in ak:
                    _collect_branch_signals(arm)
                else:
                    for s in (h.signal_visitor._extract_signals_from_expr(arm) or []):
                        branch_sigs.add(s)
        _collect_branch_signals(check_expr)

        # Leaf signals = 在分支中出现的信号 (包含同时在条件中出现的 — 它们仍然驱动输出)
        leaf_signals = [s for s in all_signals if s in branch_sigs]

        # [V6.9] 递归遍历 ConditionalOp 为每个 leaf 构建条件文本
        # g ? (h ? x0 : x1) : x2 → x0:"g && h", x1:"g && !h", x2:"!g"
        def _build_ternary_cond_map(cond_op, path=None):
            result_map = {}
            if path is None:
                path = []
            if cond_op is None:
                return result_map
            ck = str(getattr(cond_op, "kind", ""))
            if "ConditionalOp" not in ck and "ConditionalExpression" not in ck:
                return result_map

            # 提取条件文本
            cond_texts = []
            raw_c = getattr(cond_op, "conditions", None)
            if raw_c:
                for c in raw_c:
                    ce = getattr(c, "expr", None)
                    if ce:
                        ct = h.get_signal(ce) or str(ce).strip()
                        if ct:
                            cond_texts.append(ct)
            cond_str = " && ".join(cond_texts) if cond_texts else ""

            left = getattr(cond_op, "left", None)
            right = getattr(cond_op, "right", None)

            def _extract_arm_signals(arm_expr, cond_path):
                """Extract all leaf signal names from a ternary arm.

                Returns dict of {signal_name: (cond_list, arm_ast)} where cond_list
                is the condition path and arm_ast is the original sub-expression AST
                (preserved for source_op detection).
                """
                if arm_expr is None:
                    return {}
                ak = str(getattr(arm_expr, "kind", ""))
                if "ConditionalOp" in ak or "ConditionalExpression" in ak:
                    return _build_ternary_cond_map(arm_expr, cond_path)
                # Preserve sub-expression AST for source_op extraction later
                names = h.signal_visitor._extract_signals_from_expr(arm_expr) or []
                return {n: (list(cond_path), arm_expr) for n in names if n}

            # 递归 left (true 分支) / right (false 分支)
            result_map.update(_extract_arm_signals(left, path + [cond_str]))
            neg_cond = f"!({cond_str})" if cond_str else ""
            result_map.update(_extract_arm_signals(right, path + [neg_cond]))

            return result_map

        cond_map = _build_ternary_cond_map(check_expr)
        # cond_map: {signal_name: (cond_path_list, arm_ast)}
        signal_conditions = [(s, cond_map[s][0], cond_map[s][1]) for s in leaf_signals if s in cond_map]

        signal_conditions = h.filter_signal_conditions_by_module(
            signal_conditions, module=module
        )
        for rhs_name, sig_cond_list, arm_ast in signal_conditions:
            if not rhs_name:
                continue
            sig_cond_str = " && ".join(sig_cond_list) if sig_cond_list else ""
            bit_slice = ""
            if "[" in rhs_name and "]" in rhs_name:
                start = rhs_name.index("[")
                bit_slice = rhs_name[start:]
            if rhs_name and not rhs_name[0].isalpha() and not rhs_name.startswith("_"):
                result.edges.append(
                    h.edge_factory.make_edge(
                        src=rhs_name,
                        dst=dst_node_id,
                        kind=EdgeKind.DRIVER,
                        assign_type="continuous",
                        expression=rhs_name,
                        bit_slice=bit_slice,
                        sig_cond=sig_cond_str,
                        condition=sig_cond_str,
                        condition_chain=sig_cond_list if sig_cond_list else [],
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
                # [V6.5] 结构化驱动源 — 用保留下来的子表达式 AST 检测 source_op
                ds = h.build_signal_source(rhs_name, arm_ast, expr_str)
                result.edges.append(
                    h.edge_factory.make_edge(
                        src=src_node_id,
                        dst=dst_node_id,
                        kind=EdgeKind.DRIVER,
                        assign_type="continuous",
                        expression=expr_str,
                        bit_slice=bit_slice,
                        sig_cond=sig_cond_str,
                        condition=sig_cond_str,
                        condition_chain=sig_cond_list if sig_cond_list else [],
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
                # [V4] factory 统一入口
                chain = [ternary_condition] if ternary_condition else []
                h.append_edge(
                    result,
                    src=rhs_name,
                    dst=dst_node_id,
                    kind=EdgeKind.DRIVER,
                    assign_type="continuous",
                    expression=rhs_name,
                    bit_slice=bit_slice,
                    condition=ternary_condition,
                    condition_chain=chain,
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
                # [V4] factory 统一入口
                chain = [ternary_condition] if ternary_condition else []
                h.append_edge(
                    result,
                    src=src_node_id,
                    dst=dst_node_id,
                    kind=EdgeKind.DRIVER,
                    assign_type="continuous",
                    expression=expr_str,
                    bit_slice=bit_slice,
                    condition=ternary_condition,
                    condition_chain=chain,
                    source=ds,
                )

    # [REFACTOR 2026-08-07 A计划] 从完整 rhs 构建表达式树 (assign y = rhs)
    # rhs_expr 是完整 semantic 表达式，.syntax 建整棵树（含三元/嵌套运算）
    if lhs and rhs_expr is not None:
        h.store_expr_tree(lhs, rhs_expr, module_name, result, genvar_ctx=genvar_ctx)



def _extract_assign_lr(assign) -> tuple:
    """[语义 AST] 从 assign 节点提取 (raw_lhs, raw_rhs).

    get_assignments() 只返回 SymbolKind.ContinuousAssign, 其结构固定:
    - .assignment → AssignmentExpression (含 .left/.right)
    - 本身无 .left/.right/assignments
    [重构 2026-08-07] 激进精简: 删除历史语法树 fallback (assignments/right),
    它们在新 pipeline (纯语义 AST) 下是死代码.
    """
    ass = getattr(assign, "assignment", None)
    if ass is None:
        return None, None
    return getattr(ass, "left", None), getattr(ass, "right", None)



def _extract_ternary_condition(expr) -> str:
    """从三元运算符表达式提取条件字符串

    例如: assign y = en ? d : 0;
    返回 "en"

    Args:
        expr: RHS 表达式，可能包含 ConditionalOp

    Returns:
        条件表达式字符串，如果非三元则返回空字符串
    """
    if expr is None:
        return ""

    # [V6.3+4 2026-07-28] Refactored to use ast_utils for wrapper unwrap
    # and kind matching. Replaces 6 lines of substring checks and ad-hoc
    # operand/expr unwrap with a single unwrap() call.
    current = expr
    for _ in range(5):  # 最多解包5层 (was 3, increased to match _create_always_edges)
        if current is None:
            return ""

        # [V6.3+4] Use kind_matches instead of substring "ConditionalOp" in str(kind)
        # to handle pyslang 10/11 SyntaxKind.ConditionalExpression (and any future
        # enum renames via _KIND_ALIASES).
        if kind_matches(current, "ConditionalOp", "ConditionalExpression"):
            # 提取条件
            conditions = getattr(current, "conditions", None)
            if conditions and len(conditions) > 0:
                cond = conditions[0]
                cond_expr = getattr(cond, "expr", None)
                if cond_expr:
                    # 尝试从 syntax 获取可读字符串
                    syntax = getattr(cond_expr, "syntax", None)
                    if syntax:
                        try:
                            s = str(syntax).strip()
                            if s:
                                return s
                        except (UnicodeDecodeError, TypeError):
                            pass
                    # 尝试获取符号名
                    if hasattr(cond_expr, "symbol"):
                        sym = getattr(cond_expr, "symbol", None)
                        if sym:
                            try:
                                name = sym.name
                            except (UnicodeDecodeError, TypeError, Exception):
                                name = None
                            if name:
                                try:
                                    return str(name).strip()
                                except (UnicodeDecodeError, TypeError):
                                    return "<id:non-utf8>"
                    try:
                        return str(cond_expr).strip()
                    except (UnicodeDecodeError, TypeError):
                        return "<id:non-utf8>"
            return ""

        # [V6.3+4] Use ast_utils.unwrap() instead of ad-hoc operand/expr getattr
        inner = unwrap(current)
        if inner is None or inner is current:  # 防止无限循环
            return ""
        current = inner

    return ""
