# ==============================================================================
# extractors/statement_flattener.py - semantic AST 展平 (Visitor 模式)
#
# [ARCHITECTURE_TODOLIST #1 Step 5 2026-08-28]
# 从 driver_extractor.py 拆出 8 个 _flatten_* 方法 (line 2048-2251, 204 行):
#   - _flatten_assignments         (10 行) DEPRECATED 兼容入口, 委派到 _flatten_semantic
#   - _flatten_semantic            (33 行) 主调度: 按 StatementKind 分发到 6 个 visitor
#   - _flatten_block               (24 行) StatementKind.Block 展平
#   - _flatten_timed               ( 5 行) StatementKind.Timed 跳 timing
#   - _flatten_conditional         (41 行) StatementKind.Conditional 展开 if/else
#   - _flatten_loop                (10 行) While/For/DoWhile/Forever/Repeat/Foreach
#   - _flatten_expression_statement (31 行) ExpressionStatement (Assignment/Call)
#   - _flatten_case                (50 行) Case/PatternCase 展平
#
# ── 依赖设计 ──────────────────────────────────────────────────────────────────
# - get_signal: 唯一外部 helper (3 个 visitor 用到: conditional / expression / case)。
#   全文件 _get_signal 有 27 处调用, Step 3 已迁 _common.get_signal。沿用既有
#   Callable 注入模式。
# - cond_ast_by_str: DriverExtractor 实例的 dict (line 122 init, line 1968 read),
#   记录 cond_string → AST 节点映射, 供 _collect_stmts_with_context 回填
#   condition_ast (Plan F3-pre 2026-08-13)。**作为参数传入**而非共享全局 —
#   保持无副作用, 与 AGENTS.md 核心纪律 #2 一致。
#
# ── 行为契约 ──────────────────────────────────────────────────────────────────
# - 铁律15/26: Visitor 模式 — 每个 StatementKind 独立方法, 禁止字符串匹配。
# - 副作用仅通过 (1) append 到 result (2) write cond_ast_by_str dict。
# - 递归通过 _flatten_semantic 互调, get_signal / cond_ast_by_str 自动转发。
# ==============================================================================

from pyslang.pyslang.ast import ExpressionKind, StatementKind  # [V6.9] semantic AST only


def _flatten_assignments(stmt, result: list, cond_stack: list[str] | None = None, *, get_signal, cond_ast_by_str):
    """[DEPRECATED] 旧 syntax-based 展开。保留兼容 _expand_and_append_assignment。"""
    # 重定向到 semantic 版本
    _flatten_semantic(stmt, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)

    # ======================================================================
    # SemanticStatementFlattener: 纯 semantic AST 展平 (V6.9)
    # 铁律15/26: Visitor 模式 — 每个 StatementKind 独立方法，禁止字符串匹配
    # ======================================================================




def _flatten_semantic(stmt, result: list, cond_stack: list[str] | None = None, *, get_signal, cond_ast_by_str):
    """[V6.9] Dispatcher — 按 StatementKind / ExpressionKind 分发到独立 visitor 方法。

    铁律15/26: 禁止 if-elif 链，禁止 str(kind) 字符串匹配。
    """
    if stmt is None:
        return
    if cond_stack is None:
        cond_stack = []

    kind = getattr(stmt, "kind", None)

    if kind == StatementKind.Block:
        _flatten_block(stmt, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
    elif kind == StatementKind.Timed:
        _flatten_timed(stmt, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
    elif kind == StatementKind.Conditional:
        _flatten_conditional(stmt, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
    elif kind in (StatementKind.WhileLoop, StatementKind.ForLoop, StatementKind.DoWhileLoop,
                  StatementKind.ForeverLoop, StatementKind.RepeatLoop, StatementKind.ForeachLoop):
        _flatten_loop(stmt, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
    elif kind == StatementKind.ExpressionStatement:
        _flatten_expression_statement(stmt, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
    elif kind in (StatementKind.Case, StatementKind.PatternCase):
        _flatten_case(stmt, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
    elif kind == ExpressionKind.Assignment:
        condition_chain = list(cond_stack) if cond_stack else []
        result.append((stmt, condition_chain))
    # 其他 StatementKind（Break, Continue, Return, Wait, EventTrigger 等）：
    # 不展开，不影响驱动提取。

    # —— Visitor 方法 ——




def _flatten_block(stmt, result: list, cond_stack: list[str], *, get_signal, cond_ast_by_str):
    """StatementKind.Block: 遍历 .body (单个对象或 iterable)。

    .body 可能是:
      - 单个 Statement (ConditionalStatement, ExpressionStatement 等)
      - iterable list of Statement
      - StatementList (StatementKind.List) → 需迭代 .list
    """
    body_val = getattr(stmt, "body", None)
    if body_val is None:
        return
    # StatementKind.List: 特殊类型，迭代 .list 属性
    if getattr(body_val, "kind", None) == StatementKind.List:
        stmt_list = getattr(body_val, "list", None)
        if stmt_list is not None and hasattr(stmt_list, "__iter__") and not isinstance(stmt_list, str):
            for item in stmt_list:
                _flatten_semantic(item, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
        return
    if hasattr(body_val, "__iter__") and not isinstance(body_val, str):
        for item in body_val:
            _flatten_semantic(item, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
    else:
        _flatten_semantic(body_val, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)




def _flatten_timed(stmt, result: list, cond_stack: list[str], *, get_signal, cond_ast_by_str):
    """StatementKind.Timed: 跳过 timing，进入 .stmt。"""
    inner = getattr(stmt, "stmt", None) or getattr(stmt, "statement", None)
    _flatten_semantic(inner, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)




def _flatten_conditional(stmt, result: list, cond_stack: list[str], *, get_signal, cond_ast_by_str):
    """StatementKind.Conditional: 展开 ifTrue + ifFalse。

    semantic AST 用 .ifTrue/.ifFalse（不是 syntax 的 .statement/.elseClause）。
    """
    cond = getattr(stmt, "conditions", None) or getattr(stmt, "predicate", None) or getattr(stmt, "condition", None)
    # .conditions 是 Condition 对象列表；取出第一个 .expr 并用 _get_signal 提取信号名
    cond_expr = None
    if hasattr(cond, "__iter__") and not isinstance(cond, str):
        cond_list = list(cond)
        if cond_list:
            cond_expr = getattr(cond_list[0], "expr", None)
            new_cond = get_signal(cond_expr) if cond_expr else ""
        else:
            new_cond = ""
    else:
        new_cond = str(cond).strip() if cond is not None else ""
    # [Plan F3-pre 2026-08-13] 记录条件 AST (回填 edge.condition_ast)
    if new_cond and cond_expr is not None:
        cond_ast_by_str[new_cond] = cond_expr
    is_real = new_cond and not any(kw in new_cond for kw in ("posedge", "negedge", "or "))

    # ifTrue
    if is_real:
        cond_stack.append(new_cond)
    then_stmt = getattr(stmt, "ifTrue", None) or getattr(stmt, "statement", None)
    _flatten_semantic(then_stmt, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
    if is_real:
        cond_stack.pop()

    # ifFalse（仅当有 else 分支时）
    else_node = getattr(stmt, "ifFalse", None) or getattr(stmt, "elseClause", None) or getattr(stmt, "elseStatement", None)
    if else_node is not None:
        if is_real:
            neg_cond = f"!{new_cond}" if all(c.isalnum() or c == '_' for c in new_cond) else f"!({new_cond})"
            cond_stack.append(neg_cond)
        clause = getattr(else_node, "clause", None) or getattr(else_node, "statement", None) or else_node
        _flatten_semantic(clause, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
        if is_real:
            cond_stack.pop()




def _flatten_loop(stmt, result: list, cond_stack: list[str], *, get_signal, cond_ast_by_str):
    """StatementKind WhileLoop/ForLoop/DoWhile/Forever/Repeat/Foreach: 进入 .body。"""
    body = getattr(stmt, "body", None)
    if body is not None:
        if hasattr(body, "__iter__") and not isinstance(body, str):
            for item in body:
                _flatten_semantic(item, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
        else:
            _flatten_semantic(body, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)




def _flatten_expression_statement(stmt, result: list, cond_stack: list[str], *, get_signal, cond_ast_by_str):
    """StatementKind.ExpressionStatement: 提取 .expr (Assignment/Call 则追加)。

    铁律1: 只用 semantic AST ExpressionKind，不碰 SyntaxKind。
    """
    expr = getattr(stmt, "expr", None)
    if expr is None:
        return
    ek = getattr(expr, "kind", None)
    condition_chain = list(cond_stack) if cond_stack else []
    if ek == ExpressionKind.Assignment:
        result.append((expr, condition_chain))
    elif ek == ExpressionKind.Call:
        # [iter_076 #42/#43 试验] 不拆 Call — 保留整体, 交给 handle_invocation
        # 做完整形参映射 (param_map + internal_drivers). 拆分只处理单 input
        # 单 output, 多参数时 input_sig 覆盖错误.
        result.append((expr, condition_chain))




def _flatten_case(stmt, result: list, cond_stack: list[str], *, get_signal, cond_ast_by_str):
    """StatementKind Case/PatternCase: 展开各 CaseItem。

    每个 CaseItem 有 .expressions (值列表) 和 .clause (对应语句)。
    """
    case_expr = getattr(stmt, "expr", None) or getattr(stmt, "expression", None)
    # [V6.9] 用 _get_signal 而非 str() 避免对象引用
    case_cond = get_signal(case_expr) or str(case_expr).strip() if case_expr else ""
    # [Plan F3-pre 2026-08-13] 记录 case 选择信号 AST
    if case_cond and case_expr is not None:
        cond_ast_by_str[case_cond] = case_expr
    items = getattr(stmt, "items", None)
    if items is not None and hasattr(items, "__iter__") and not isinstance(items, str):
        for item in items:
            item_exprs = getattr(item, "expressions", None)
            if item_exprs and hasattr(item_exprs, "__iter__") and not isinstance(item_exprs, str):
                # [V6.9] 用 _get_signal 而非 str() 避免对象引用
                expr_strs = []
                for e in item_exprs:
                    sig = get_signal(e)
                    if sig and not sig.startswith("Expression("):
                        expr_strs.append(sig)
                    else:
                        expr_strs.append(str(e).strip())
                item_cond = " || ".join(expr_strs)
            else:
                # [V6.9] 用 _get_signal 而非 str() 避免对象引用
                raw = getattr(item, "expression", None)
                sig = get_signal(raw) if raw else ""
                item_cond = sig if (sig and not sig.startswith("Expression(")) else str(raw or "").strip()
            case_full = f"{case_cond} == {item_cond}" if case_cond and item_cond else (item_cond or case_cond)
            if case_full:
                cond_stack.append(case_full)
            case_stmt = getattr(item, "clause", None) or getattr(item, "statement", None) or getattr(item, "stmt", None)
            _flatten_semantic(case_stmt, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
            if case_full:
                cond_stack.pop()

        # [V6.9] pyslang semantic AST stores default branch outside `.items`
        # in `.defaultCase` (ExpressionStatement), not as a CaseItem.
        default_case = getattr(stmt, "defaultCase", None)
        if default_case is not None:
            item_cond = "default"
            case_full = f"{case_cond} == default" if case_cond else "default"
            if case_full:
                cond_stack.append(case_full)
            _flatten_semantic(default_case, result, cond_stack, get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)
            if case_full:
                cond_stack.pop()

