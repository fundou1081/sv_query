# ==============================================================================
# extractors/function_extractor.py - function/task 调用展开 (invocation edges)
#
# [ARCHITECTURE_TODOLIST #1 Step 7 2026-08-28]
# 从 driver_extractor.py 拆出 function/task 相关 7 个方法 (648 行):
#   - _find_invocations           ( 32 行) 递归找 Invocation/Call 表达式
#   - _get_constructor_call       ( 11 行) 构造器调用名
#   - _find_func_assignment_rhs   ( 57 行) 函数调用的赋值 RHS
#   - _handle_invocation          ( 26 行) 入口: 解析 + 展开 invocation
#   - _parse_invocation_call      (122 行) invocation → (call_name, args, named_args)
#   - _find_task_definition       ( 42 行) 按名字找 task 定义
#   - _create_invocation_edges    (358 行) 主展开: 输出参数映射 + DRIVER 边
#   - _get_all_signals            (  9 行) 信号提取 (仅被 invocation 用, 随模块搬入)
#
# ── 保留在 driver_extractor 的共享 helper (注入) ────────────────────────────
# _get_signal: 全文件共享 (Step 3 已迁 _common), 注入。
# _subroutine_expander: DriverExtractor 构造时初始化的 SubroutineExpander 实例,
#   用于 task/function 展开 (has_conditional_branches / expand), 注入。
#
# ── 依赖设计 ──────────────────────────────────────────────────────────────────
# FunctionHelpers dataclass 注入 (沿用 Step 4/6 模式):
#   get_signal / subroutine_expander / signal_visitor / edge_factory。
#
# ── 行为契约 ──────────────────────────────────────────────────────────────────
# - _create_invocation_edges 358 行**本次只搬不拆** (行为重构独立 commit)。
# - 副作用仅通过 append result.nodes/result.edges。
# - 内部互调 _xxx(...) 带 h=h 自动转发。
# ==============================================================================
from dataclasses import dataclass
from typing import Any, Callable

from ..builder.subroutine_expander import CallSiteInfo
from ..graph.models import EdgeKind, NodeKind, SignalSource, TraceNode
from ..._safe import safe_attr, safe_str  # [iter_141] 非 utf8 防崩


@dataclass
class FunctionHelpers:
    """[Step 7 2026-08-28] driver_extractor 共享 helper 注入包."""

    adapter: Any
    get_signal: Callable
    signal_visitor: Any = None
    edge_factory: Any = None
    subroutine_expander: Any = None


def _get_all_signals(signal, *, h: 'FunctionHelpers') -> list[str]:
    """[Step 7 2026-08-28] 从 driver_extractor._get_all_signals 搬入.

    提取表达式中的所有信号名 (铁律29: 直接使用 SignalExpressionVisitor)。
    行为 1:1 一致, 仅 self._signal_visitor → h.signal_visitor。
    """
    if signal is None:
        return []
    return h.signal_visitor._extract_signals_from_expr(signal) or []


def _find_invocations(expr, invocations=None, *, h: 'FunctionHelpers') -> list:
    """[REFACTOR 2026-06-26] 5c-helper: 递归找表达式中的 InvocationExpression / CallExpression.

    之前是 inline closure, 现在抽 public method 可单测.
    """
    if invocations is None:
        invocations = []
    if expr is None:
        return invocations
    kind = getattr(expr, "kind", None)
    kind_str = str(kind) if kind else ""
    if kind and ("Invocation" in kind_str or "Call" in kind_str):
        invocations.append(expr)
        return invocations  # Don't recurse into children
    # If expr has __iter__, don't recurse into its attributes
    # because iteration already yields children
    if hasattr(expr, "__iter__") and not isinstance(expr, str):
        for c in expr:
            if hasattr(c, "kind"):
                _find_invocations(c, invocations, h=h)
    else:
        for child_attr in ["left", "right", "predicate", "condition"]:
            child = getattr(expr, child_attr, None)
            if child:
                _find_invocations(child, invocations, h=h)
    return invocations

    # ==============================================================================
    # [V6.5 2026-07-28] [V6.6] SignalSource — 结构化信号源 (driver/load 共用)
    # ==============================================================================



def _get_constructor_call(initializer, *, h: 'FunctionHelpers') -> str | None:
    """提取构造函数调用名 (new())"""
    if initializer is None:
        return None
    # initializer 结构: = new()
    # 提取函数调用名
    if hasattr(initializer, "name"):
        name = initializer.name
        return name.value if hasattr(name, "value") else str(name)
    return "new"  # 默认返回 new




def _find_func_assignment_rhs(stmt, func_name, *, h: 'FunctionHelpers'):
    """
    在语句中查找函数赋值语句的 RHS
    例如: gray_conv = {a[7], a[6:0] ^ a[7:1]} 返回 ConcatenationExpression AST
    """
    if stmt is None:
        return None

    kind = str(getattr(stmt, "kind", ""))

    # ExpressionStatement
    if "ExpressionStatement" in kind:
        expr = getattr(stmt, "expr", None)
        if expr:
            left = getattr(expr, "left", None)
            right = getattr(expr, "right", None)
            if left and right:
                # 检查是否是函数名的赋值
                left_name = None
                if hasattr(left, "identifier"):
                    ident = left.identifier
                    left_name = getattr(ident, "value", None) or str(ident).strip()
                elif hasattr(left, "value"):
                    left_name = str(left.value).strip()

                if left_name == func_name:
                    return right
        return None

    # SequentialBlock
    if "SequentialBlock" in kind:
        # v11: SequentialBlockStatement.children 是 plain list (no SyntaxList wrapper)
        statements = None
        for i, child in enumerate(stmt):
            child_kind = str(getattr(child, "kind", ""))
            if ("SyntaxList" in child_kind or isinstance(child, list)) and i == 4:
                statements = child
                break

        if statements is None:
            # Fallback to iterating over stmt itself
            for item in stmt:
                item_kind = str(getattr(item, "kind", ""))
                if "ExpressionStatement" in item_kind:
                    result = _find_func_assignment_rhs(item, func_name, h=h)
                    if result:
                        return result
        else:
            for item in statements:
                item_kind = str(getattr(item, "kind", ""))
                if "ExpressionStatement" in item_kind:
                    result = _find_func_assignment_rhs(item, func_name, h=h)
                    if result:
                        return result

    return None




def _handle_invocation(invocation, ctx, module, module_name, result, lhs_name=None, *, h: 'FunctionHelpers'):
    """
    处理 task/function 调用
    建立参数映射并添加边

    Args:
        invocation: InvocationExpression AST 节点
        ctx: 上下文(时钟、复位等)
        module: 模块 AST 节点
        module_name: 模块名
        result: TraceResult 用于收集节点和边
        lhs_name: 可选,函数调用的目标信号名(ContinuousAssign 的 LHS)
    """
    call_info = _parse_invocation_call(invocation, h=h)
    if not call_info:
        return
    call_name, call_args, named_args = call_info

    # [iter_151 C1 class 方法调用] receiver (thisClass) 解析: p.set(x) 的
    # receiver = p (class 实例); arr[0].set(x) 的 receiver = 数组元素
    # (ElementSelect, iter_156 E8) — module task/function 无 thisClass。
    receiver_id = None
    receiver_class_name = None
    this_cls = getattr(invocation, "thisClass", None)
    if this_cls is not None:
        # thisClass 形态: NamedValue (p) 或 ElementSelect (arr[0], E8)
        _tc_kind = str(getattr(this_cls, "kind", ""))
        rcvr_sym = getattr(this_cls, "symbol", None)
        _arr_suffix = ""
        _type_src = this_cls
        if "ElementSelect" in _tc_kind:
            # 数组元素 receiver: value (NamedValue arr) + selector (常量 idx)
            val = getattr(this_cls, "value", None)
            rcvr_sym = getattr(val, "symbol", None)
            sel = getattr(this_cls, "selector", None)
            if sel is not None:
                # IntegerLiteral: 尝试 value / toString
                _iv = None
                for _a in ("value", "toString"):
                    _v = getattr(sel, _a, None)
                    if _v is not None:
                        _iv = _v
                        break
                if _iv is None:
                    try:
                        _iv = int(str(sel))
                    except (ValueError, TypeError):
                        _iv = None
                if _iv is not None:
                    _arr_suffix = f"[{_iv}]"
            _type_src = val
        if rcvr_sym is not None:
            try:
                rcvr_name = safe_str(safe_attr(rcvr_sym, "name"))
                if rcvr_name:
                    receiver_id = f"{module_name}.{rcvr_name}{_arr_suffix}"
                # type: 数组 (arr) 需剥 elementType → class 名
                rcvr_type = getattr(_type_src, "type", None) \
                    or getattr(rcvr_sym, "type", None)
                if rcvr_type is None and _type_src is not this_cls:
                    rcvr_type = getattr(rcvr_sym, "type", None)
                tname = ""
                _t = rcvr_type
                while _t is not None:
                    _tk = str(getattr(_t, "kind", ""))
                    if "ClassType" in _tk:
                        tname = safe_str(safe_attr(_t, "name"))
                        break
                    _t = (getattr(_t, "elementType", None)
                          or getattr(_t, "arrayElementType", None))
                if tname:
                    receiver_class_name = tname
            except (UnicodeDecodeError, TypeError):
                receiver_id = None

    task_def = None
    # [iter_156 对抗 E11] class 方法调用 (receiver 已知) 必须**优先**解析
    # class 方法: module 若有同名 function/task, 旧顺序先命中 module 定义 →
    # class 方法链断 (E11 实测)。receiver_class_name 存在 = thisClass 明确
    # 指向 class 实例, 方法定义在 class (或父类, E7 backlog) 域。
    if receiver_class_name:
        task_def = _find_class_method(receiver_class_name, call_name, h=h)
    if not task_def:
        task_def = _find_task_definition(module, call_name, h=h)
    if not task_def and receiver_class_name:
        # E7 backlog: 继承方法 (sub_packet extends packet, set 在父类) —
        # _find_class_method 需沿 extends 链; 现未支持, 显式记录
        pass
    if not task_def:
        return
    # [HANDOFF] def_params 由 _create_invocation_edges 内部根据 task kind 计算
    _create_invocation_edges(
        invocation, ctx, module, module_name, result, lhs_name,
        call_name, call_args, named_args, task_def, h=h,
        receiver_id=receiver_id,
        receiver_class_name=receiver_class_name,
    )


def _find_class_method(class_name: str, method_name: str, *, h: 'FunctionHelpers'):
    """[iter_151 C1 / iter_156 E7] 找 class 方法定义 (SubroutineSymbol).

    receiver 类型名 (packet) → adapter.get_classes() 匹配 ClassSymbol →
    迭代成员找 Subroutine == method_name (set)。**E7: 找不到时沿 extends
    链递归父类** (sub_packet extends packet, set 在父类 — 子类实例调用
    继承方法)。找不到返回 None (显式, 不静默)。
    """
    try:
        classes = h.adapter.get_classes()
    except Exception as e:
        logger.warning("class 枚举失败: %s", e)
        return None
    by_name: dict = {}
    for cls in classes:
        try:
            cname = safe_str(safe_attr(cls, "name"))
        except (UnicodeDecodeError, TypeError):
            continue
        if cname and cname not in by_name:
            by_name[cname] = cls

    def _extends_of(cls) -> str | None:
        """父类名 (baseClass.name 或 syntax extendsClause)."""
        base = getattr(cls, "baseClass", None)
        if base is not None:
            try:
                return safe_str(safe_attr(base, "name")) or None
            except (UnicodeDecodeError, TypeError):
                return None
        syntax = getattr(cls, "syntax", None)
        ec = getattr(syntax, "extendsClause", None) if syntax is not None else None
        if ec is None:
            return None
        text = safe_str(ec).strip()
        if text.startswith("extends"):
            return text[len("extends"):].strip().split()[0]
        return None

    seen = set()
    cur = class_name
    while cur and cur not in seen:
        seen.add(cur)
        cls = by_name.get(cur)
        if cls is None:
            return None
        try:
            members = list(cls)
        except TypeError:
            return None
        for member in members:
            if 'Subroutine' not in str(getattr(member, 'kind', '')):
                continue
            try:
                mname = safe_str(safe_attr(member, "name"))
            except (UnicodeDecodeError, TypeError):
                continue
            if mname == method_name:
                return member
        cur = _extends_of(cls)  # E7: 沿继承链找父类方法
    return None




def _parse_invocation_call(invocation, *, h: 'FunctionHelpers') -> tuple | None:
    """[REFACTOR 2026-06-26] 解析 invocation → (call_name, call_args, named_args).

    Returns None if call_name / args 缺失.
    """
    # 获取调用名称
    # Semantic AST: CallExpression uses .subroutine or .subroutineName
    # SyntaxTree: CallExpression uses .left
    callee = getattr(invocation, "left", None)
    call_name = None
    if callee:
        call_name = safe_str(callee).strip()
    if not call_name:
        # Try Semantic AST path: .subroutineName or .subroutine
        call_name = safe_attr(invocation, "subroutineName", None)  # [iter_141] 非 utf8 防崩
        if not call_name:
            subroutine = getattr(invocation, "subroutine", None)
            if subroutine:
                call_name = safe_attr(subroutine, "name", None)
        if call_name:
            call_name = str(call_name).strip()
    if not call_name:
        return None

    # 获取调用参数 (OrderedArgument 或 NamedArgument 列表)
    args_node = getattr(invocation, "arguments", None)
    if args_node is None:
        return None

    call_args = []  # 位置参数列表
    named_args = {}  # 命名参数字典 {name: signal}

    # [V6.9] Semantic AST: CallExpression.arguments 直接可迭代（list of Expressions）
    #         syntax tree: arguments 有 .parameters 属性
    #         优先尝试 list(args_node)，成功就走语义 AST 路径
    try:
        arg_items = list(args_node)
        # Semantic AST path: each item is an Expression (NamedValueExpression etc)
        for expr in arg_items:
            if expr is None:
                continue
            # [V6.9 fix] 语义 AST 的 Expression 直接有 .kind，不需要 .expr
            #         syntax tree 的 Token（逗号、括号）也有 .kind 但无 .symbol
            #         用 .symbol 区分：语义 AST 的 Expression 有 .symbol
            # [iter_076 #42 fix] AssignmentExpression (task/function 调用的
            #         output 实参) 既无 .symbol 也无 .expr — 会被当成
            #         syntax-tree token 误跳过, 导致 output 实参丢失。
            #         放行 Assignment 类型 (通过 .left 访问).
            is_semantic = hasattr(expr, "symbol")
            kind_str = str(getattr(expr, "kind", ""))
            if not hasattr(expr, "expr") and not is_semantic and "Assignment" not in kind_str:
                continue
            # NamedArgument: .in(a) 格式，name 字段存参数名
            # [iter_076 #42 fix] pyslang 语义 AST 中 NamedValueExpression.name
            # 和 AssignmentExpression.name 均为空字符串, 但 hasattr 为 True —
            # 旧代码无条件 continue 把 output 实参 (AssignmentExpression) 吞掉。
            # 只有真正的 NamedArgument (name 非空 + arg_expr) 才 continue,
            # 其余 fall through 到下方 kind 分支继续处理。
            if hasattr(expr, "name"):
                name = safe_str(safe_attr(expr, "name")).strip()
                arg_expr = getattr(expr, "expr", None)
                if name and arg_expr:
                    arg_name = h.get_signal(arg_expr)
                    if arg_name:
                        named_args[name] = arg_name.strip()
                    continue
            if "NamedValue" in kind_str:
                arg_name = h.get_signal(expr)
                if arg_name:
                    call_args.append(arg_name.strip())
            elif "Assignment" in kind_str:
                lhs = getattr(expr, "left", None)
                if lhs:
                    while hasattr(lhs, "kind") and "Assignment" in str(lhs.kind):
                        lhs = getattr(lhs, "left", None)
                    if lhs and hasattr(lhs, "kind") and "NamedValue" in str(lhs.kind):
                        # [iter_076 #42 fix] output 实参的 LHS 是 NamedValue —
                        # get_signal 直接可用 (与 input 实参同一路径, 无 fallback).
                        arg_name = h.get_signal(lhs)
                        if arg_name:
                            call_args.append(arg_name.strip())
                rhs = getattr(expr, "right", None)
                if rhs and hasattr(rhs, "kind") and "NamedValue" in str(rhs.kind):
                    arg_name = h.get_signal(rhs)
                    if arg_name:
                        call_args.append(arg_name.strip())
            elif "Empty" not in kind_str:
                arg_name = h.get_signal(expr)
                if arg_name:
                    call_args.append(arg_name.strip())
    except (TypeError, ValueError):
        # Fallback: syntax tree path with .parameters
        if hasattr(args_node, "parameters"):
            params = getattr(args_node, "parameters", [])
            for arg in params:
                arg_kind = str(getattr(arg, "kind", ""))
                # [V6.9 fix] syntax tree parameters 包含 Token 项（逗号、括号）
                #          用 hasattr(arg, 'expr') 过滤，只有有 .expr 的才是真正的参数
                if not hasattr(arg, "expr"):
                    continue
                if "OrderedArgument" in arg_kind:
                    expr = getattr(arg, "expr", None)
                    if expr:
                        arg_name = h.get_signal(expr)
                        if arg_name:
                            call_args.append(arg_name.strip())
                elif "NamedArgument" in arg_kind:
                    name = safe_attr(arg, "name", None)
                    expr = getattr(arg, "expr", None)
                    if name and expr:
                        name_str = str(name).strip()
                        arg_name = h.get_signal(expr)
                        if arg_name:
                            named_args[name_str] = arg_name.strip()
        else:
            return None

    return call_name, call_args, named_args





def _find_task_definition(module, call_name, *, h: 'FunctionHelpers') -> tuple:
    """[REFACTOR 2026-06-26] 找 task/function 定义.

    Returns (task_def, def_params). Both may be None/empty.
    """
    # 查找 task 定义 - 在 module 中查找
    task_def = None
    for task in h.adapter.get_task_declarations(module):
        if h.adapter.get_task_name(task) == call_name:
            task_def = task
            break

    if not task_def:
        # 查找 function 定义
        for func in h.adapter.get_function_declarations(module):
            if h.adapter.get_function_name(func) == call_name:
                task_def = func
                break

    if not task_def:
        # [FIX] CU 级别函数: 在 parser.trees 中搜索 CompilationUnit 级别的函数
        for _fname, tree in h.adapter.parser.trees.items():
            if tree and hasattr(tree, "root"):
                for member in tree.root.members:
                    if hasattr(member, "kind") and "Function" in str(member.kind):
                        proto = getattr(member, "prototype", None)
                        if proto:
                            name = safe_attr(proto, "name", None)
                            if name:
                                # name 是 IdentifierNameSyntax,需要转成字符串再 strip
                                name_val = str(name).strip()
                                if name_val == call_name:
                                    task_def = member
                                    break
                if task_def:
                    break

    if not task_def:
        return None
    return task_def





def _is_class_member(class_name: str, member_name: str, *, h: 'FunctionHelpers') -> bool:
    """[iter_157 E5] receiver class 是否有该成员 (CLASS_PROPERTY) — 编译期
    确定 (静态限定: 成员名存在于类型定义才映射, 防拼假节点)."""
    try:
        classes = h.adapter.get_classes()
    except Exception:
        return False
    for cls in classes:
        try:
            cname = safe_str(safe_attr(cls, "name"))
        except (UnicodeDecodeError, TypeError):
            continue
        if cname != class_name:
            continue
        try:
            members = list(cls)
        except TypeError:
            return False
        for m in members:
            if 'ClassProperty' not in str(getattr(m, 'kind', '')):
                continue
            try:
                if safe_str(safe_attr(m, "name")) == member_name:
                    return True
            except (UnicodeDecodeError, TypeError):
                continue
        return False
    return False


def _expand_nested_class_calls(method_def, receiver_id, receiver_class_name,
                               param_map, module_name, ctx, result, *, h,
                               depth: int = 0):
    """[iter_157 E5/E13] 方法体内**嵌套调用**展开 (静态限定, 方豆提醒).

    编译期可确定的 receiver:
    - 隐式 this (helper(d) 无 receiver) → 外层 receiver (同类方法)
    - 显式成员 receiver (i.set(v), i 是外层实例的 class 成员) → 外层
      receiver.i (成员类型定 class)
    实参经外层 param_map 传递 (嵌套形参 ← 实参 ← 调用点信号)。

    不建模 (动态分派, 文档标记 — class_tracing_plan E5/E13 注):
    - virtual 方法 override 实际分派 (运行时对象类型未知)
    - 句柄运行时重指向 (p.i 被重新 new 到别实例)
    - 遍历句柄集合的动态调用
    depth ≤ 3 防自/互递归静态展开无界。
    """
    if depth > 3 or method_def is None:
        return
    body = getattr(method_def, "body", None)
    if body is None:
        return

    # 遍历方法体语句找 Call (语义: List/SequentialBlock 可迭代, 语句走
    # expr/stmt 树)
    def _walk(node, found):
        if node is None:
            return
        k = str(getattr(node, 'kind', ''))
        sk = str(getattr(node, 'statementKind', ''))
        if 'Call' in k or 'Invocation' in k:
            found.append(node)
            return
        # [iter_157 E5] 收敛 attr 集 (expr/stmt/list/statements/body):
        # 避免 expression 对象上访问无关 attr (condition/thenBlock 等) 触发
        # 深层/循环递归 (RecursionError 被外层 except 静默吞 → 找不到 call)
        for attr in ('stmt', 'expr', 'list', 'statements', 'body', 'items'):
            v = getattr(node, attr, None)
            if v is None:
                continue
            if isinstance(v, list):
                for c in v:
                    _walk(c, found)
            else:
                _walk(v, found)

    calls = []
    _walk(body, calls)
    for inv in calls:
        try:
            cname = safe_attr(inv, "subroutineName", None) or ""
            if not cname:
                continue
            # receiver: thisClass (显式成员 i) / None (隐式 this)
            recv_id2, recv_cls2 = receiver_id, receiver_class_name
            tc = getattr(inv, "thisClass", None)
            if tc is not None:
                tc_k = str(getattr(tc, 'kind', ''))
                if 'ElementSelect' in tc_k:
                    continue  # 数组成员 receiver — 组合数组专项 (backlog)
                sym = getattr(tc, 'symbol', None)
                mname = safe_str(safe_attr(sym, 'name')) if sym is not None else ""
                if not mname:
                    continue
                # 成员 receiver: i 须是外层实例成员 (class 型) — 静态限定
                if _is_class_member(receiver_class_name or "", mname, h=h):
                    # 成员 i 的 class 类型名
                    mcls = _member_class_name(receiver_class_name or "", mname, h=h)
                    if not mcls:
                        continue
                    recv_id2 = f"{receiver_id}.{mname}"
                    recv_cls2 = mcls
                else:
                    continue  # 非成员 receiver (局部句柄等) — 静态不可定, 跳过
            # 找方法定义 (含继承)
            method2 = _find_class_method(recv_cls2 or "", cname, h=h)
            if method2 is None:
                continue
            # 形参映射: def_params ↔ 实参 (实参信号经外层 param_map)
            try:
                params = h.adapter.get_function_params(method2)
            except Exception:
                params = []
            args = list(getattr(inv, 'arguments', None) or [])
            pmap2 = {}
            for i, pe in enumerate(params):
                if isinstance(pe, dict):
                    pname = pe.get('name')
                else:
                    pname = pe[1] if len(pe) > 1 else None
                if not pname or i >= len(args):
                    continue
                a = args[i]
                ak = str(getattr(a, 'kind', ''))
                if 'NamedValue' in ak:
                    # 实参符号名 = symbol.name (safe_attr(a,'symbol') 返回
                    # 对象, 直接 str 得 'Symbol(...)' 垃圾 — iter_157 实测)
                    _asym = safe_attr(a, 'symbol', None)
                    asig = (safe_str(safe_attr(_asym, 'name'))
                            if _asym is not None else None)
                    # 实参: 外层形参 (param_map) 或顶层信号
                    if asig and asig in param_map:
                        pmap2[pname] = param_map[asig]
                    elif asig and receiver_id:
                        pmap2[pname] = f"{module_name}.{asig}"
                # 常量/复杂表达式 → 无映射 (默认参数等不展开)
            # 展开 method2 成员赋值 (analyze → 实例属性边, 同 C1 规则)
            try:
                idr = h.adapter.analyze_task_internal_drivers(method2)
            except Exception:
                idr = {}
            fname2 = safe_str(safe_attr(method2, 'name'))
            for member2, rhss in idr.items():
                if member2 == fname2:
                    continue
                dst2 = f"{recv_id2}.{member2}"
                for r2 in rhss:
                    if not r2 or r2.isdigit():
                        continue
                    b2 = r2.split('[')[0]
                    src2 = None
                    if "." in b2:
                        hd, _, tl = b2.partition(".")
                        if hd in pmap2:
                            src2 = f"{module_name}.{pmap2[hd]}.{tl}"
                    elif b2 in pmap2:
                        src2 = f"{module_name}.{pmap2[b2]}"
                    elif (recv_cls2 and _is_class_member(recv_cls2, b2, h=h)):
                        src2 = f"{recv_id2}.{b2}"
                    if not src2 or src2 == dst2:
                        continue
                    if src2 not in [n.id for n in result.nodes]:
                        result.nodes.append(TraceNode(
                            id=src2, name=b2, module=module_name,
                            kind=NodeKind.SIGNAL, width=(1, 0)))
                    if dst2 not in [n.id for n in result.nodes]:
                        result.nodes.append(TraceNode(
                            id=dst2, name=member2, module=recv_id2,
                            kind=NodeKind.SIGNAL, width=(1, 0)))
                    result.edges.append(
                        h.edge_factory.make_edge(
                            src=src2, dst=dst2, kind=EdgeKind.DRIVER,
                            assign_type="blocking", ctx=ctx,
                        ))
            # 递归: method2 内再嵌套
            _expand_nested_class_calls(
                method2, recv_id2, recv_cls2, pmap2, module_name, ctx,
                result, h=h, depth=depth + 1)
        except (UnicodeDecodeError, TypeError):
            continue


def _member_class_name(class_name: str, member_name: str, *, h: 'FunctionHelpers') -> str | None:
    """[iter_157 E13] class 成员 (i) 的类型名 — 成员是 class 实例 (inner)."""
    try:
        classes = h.adapter.get_classes()
    except Exception:
        return None
    for cls in classes:
        try:
            cname = safe_str(safe_attr(cls, "name"))
        except (UnicodeDecodeError, TypeError):
            continue
        if cname != class_name:
            continue
        try:
            members = list(cls)
        except TypeError:
            return None
        for m in members:
            if 'ClassProperty' not in str(getattr(m, 'kind', '')):
                continue
            try:
                if safe_str(safe_attr(m, 'name')) != member_name:
                    continue
            except (UnicodeDecodeError, TypeError):
                continue
            # 成员 type → ClassType name (剥 elementType)
            t = getattr(m, 'type', None)
            while t is not None:
                tk = str(getattr(t, 'kind', ''))
                if 'ClassType' in tk:
                    return safe_str(safe_attr(t, 'name')) or None
                t = (getattr(t, 'elementType', None)
                     or getattr(t, 'arrayElementType', None))
            return None
        return None
    return None


def _create_invocation_edges(invocation, ctx, module, module_name, result, lhs_name,
                                 call_name, call_args, named_args, task_def, *, h: 'FunctionHelpers',
                                 receiver_id=None, receiver_class_name=None):
    """[REFACTOR 2026-06-26] 建 invocation 边 (含 def_params + param_map + function + output).

    receiver_id: [iter_151 C1] class 方法调用 (p.set) 的 receiver 实例路径
    (top.p); None = module task/function 调用。
    receiver_class_name: [iter_157 E5/E13] receiver 的类型名 (嵌套调用解析
    成员 receiver 用), None = module 调用。
    """
    try:
        # 内部计算 def_params
        if "Task" in str(getattr(task_def, "kind", "")):
            def_params = h.adapter.get_task_params(task_def)
        else:
            def_params = h.adapter.get_function_params(task_def)
        # 获取定义参数
        if "Task" in str(getattr(task_def, "kind", "")):
            def_params = h.adapter.get_task_params(task_def)
        else:
            def_params = h.adapter.get_function_params(task_def)

        # 建立映射: def_params[i] -> call_args[i] 或 named_args[name]
        param_map = {}  # def_param_name -> call_arg_name
        for i, param_entry in enumerate(def_params):
            # Handle both tuple format (direction, name) and dict format {'name': ..., 'direction': ...}
            if isinstance(param_entry, dict):
                param_name = param_entry.get("name")
                direction = param_entry.get("direction", "")
            else:
                # Tuple format: (direction, param_name)
                direction, param_name = param_entry

            if not param_name:
                continue

            # 首先尝试从命名参数获取
            if param_name in named_args:
                param_map[param_name] = named_args[param_name]
            # 否则从位置参数获取
            elif i < len(call_args):
                param_map[param_name] = call_args[i]

        # 分析 task/function 内部的驱动关系
        internal_drivers = h.adapter.analyze_task_internal_drivers(task_def)

        # [FIX] 对于函数,还需要处理隐式返回值(函数名本身作为output)
        # 函数调用: gray_conv(in) -> 返回值驱动内部 expression
        # 需要映射 call_args -> def_params,然后从 internal_drivers 获取返回值驱动源
        is_function = getattr(
            task_def, "subroutineKind", None
        ) == task_def.subroutineKind.Function or "Function" in str(getattr(task_def, "kind", ""))

        # 建立映射: def_param_name -> call_arg_name (反向映射,用于查找调用参数)
        reverse_param_map = {}  # call_arg_name -> def_param_name
        for def_param_name, call_arg_name in param_map.items():
            reverse_param_map[call_arg_name] = def_param_name

        # [FIX] 对于函数,还需要处理隐式返回值(函数名本身作为output)
        # 函数调用: gray_conv(in) -> 返回值驱动内部 expression
        # 需要映射 call_args -> def_params,然后从 internal_drivers 获取返回值驱动源
        is_function = getattr(
            task_def, "subroutineKind", None
        ) == task_def.subroutineKind.Function or "Function" in str(getattr(task_def, "kind", ""))

        # 建立映射: def_param_name -> call_arg_name (反向映射,用于查找调用参数)
        reverse_param_map = {}  # call_arg_name -> def_param_name
        for def_param_name, call_arg_name in param_map.items():
            reverse_param_map[call_arg_name] = def_param_name

        if is_function:
            func_name = h.adapter.get_function_name(task_def)

            # [NEW] 使用 SubroutineExpander 展开函数
            # 条件: 有条件分支的函数 OR 无内部驱动的简单函数(常量赋值)
            should_expand = (
                task_def
                and lhs_name
                and (
                    h.subroutine_expander.has_conditional_branches(task_def)
                    or not internal_drivers  # 简单函数/常量函数
                )
            )
            if should_expand:
                call_site = CallSiteInfo(
                    invocation=invocation,
                    call_name=call_name,
                    call_args=call_args,
                    named_args=named_args,
                    func_def=task_def,
                    def_params=def_params,
                    param_map=param_map,
                    reverse_param_map=reverse_param_map,
                    lhs_name=f"{module_name}.{lhs_name}",
                    is_function=True,
                )
                expansion = h.subroutine_expander.expand(call_site, ctx)
                for node in expansion.nodes:
                    if node.id not in [n.id for n in result.nodes]:
                        result.nodes.append(node)
                for edge in expansion.edges:
                    result.edges.append(edge)

            # Only process internal_drivers if it has content
            if func_name in internal_drivers and lhs_name:
                rhs_ast = None
                for item in getattr(task_def, "items", []):
                    kind = str(getattr(item, "kind", ""))
                    # SequentialBlock
                    if "SequentialBlock" in kind:
                        for attr in ["items", "statements", "body"]:
                            block_items = getattr(item, attr, None)
                            if block_items and hasattr(block_items, "__iter__"):
                                for bi in block_items:
                                    rhs_ast = _find_func_assignment_rhs(bi, func_name, h=h)
                                    if rhs_ast:
                                        break
                    # 直接是 ExpressionStatement
                    elif "ExpressionStatement" in kind:
                        rhs_ast = _find_func_assignment_rhs(item, func_name, h=h)
                        if rhs_ast:
                            break
                    if rhs_ast:
                        break

                # [FIX] For function calls, also create edge from function return value to lhs_name
                # Function return value is the function name itself (implicit in SystemVerilog)
                # e.g., assign out = gray_conv(in); should have: gray_conv -> out
                # 注意:这段代码应该在 if rhs_ast: 块之外,这样才能处理 ReturnStatement 形式的函数
                # [iter_156 E4] class 函数 (receiver_id) 的 module 隐式返回假节点
                # (func_return_id = module_name.func_name, e.g. top.get) 不适用 —
                # class 返回值 = return 语句表达式 (成员), 走下方 class 返回展开。
                if is_function and lhs_name and not receiver_id:
                    func_return_id = f"{module_name}.{func_name}"
                    dst_id = f"{module_name}.{lhs_name}"
                    if func_return_id != dst_id:  # Avoid self-loop
                        if func_return_id not in [n.id for n in result.nodes]:
                            result.nodes.append(
                                TraceNode(
                                    id=func_return_id,
                                    name=func_name,
                                    module=module_name,
                                    kind=NodeKind.SIGNAL,
                                    width=(1, 0),
                                )
                            )
                        if dst_id not in [n.id for n in result.nodes]:
                            result.nodes.append(
                                TraceNode(
                                    id=dst_id, name=lhs_name, module=module_name, kind=NodeKind.SIGNAL, width=(1, 0)
                                )
                            )
                        # [V8.3] 函数返回边的 source 用函数名作为 op
                        func_source = SignalSource(
                            signal=func_name,
                            full_expression=func_name,
                            op="Call",
                        )
                        result.edges.append(
                            h.edge_factory.make_edge(
                                src=func_return_id,
                                dst=dst_id,
                                kind=EdgeKind.DRIVER,
                                assign_type="continuous",
                                ctx=ctx,
                                source=func_source,
                            )
                        )

                if rhs_ast:
                    # 用 _get_all_signals 提取所有信号
                    all_signals = _get_all_signals(rhs_ast)
                    for sig in all_signals:
                        if not sig or sig.startswith("{") or not sig[0].isalpha():
                            continue
                        # Map signal to call_arg
                        base_sig = sig.split("[")[0] if "[" in sig else sig
                        call_arg = param_map.get(base_sig)
                        if call_arg and lhs_name:
                            src_node_id = f"{module_name}.{call_arg}"
                            dst_node_id = f"{module_name}.{lhs_name}"

                            if src_node_id not in [n.id for n in result.nodes]:
                                result.nodes.append(
                                    TraceNode(
                                        id=src_node_id,
                                        name=call_arg,
                                        module=module_name,
                                        kind=NodeKind.SIGNAL,
                                        width=(1, 0),
                                    )
                                )
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

                            # [V8.3] 函数入参边的 source: 用 Call 标记，不挂算术 OP
                            arg_source = SignalSource(
                                signal=call_arg,
                                full_expression=f"{func_name}({call_arg})",
                                op="",
                            )
                            result.edges.append(
                                h.edge_factory.make_edge(
                                    src=src_node_id,
                                    dst=dst_node_id,
                                    kind=EdgeKind.DRIVER,
                                    assign_type="continuous",
                                    ctx=ctx,
                                    source=arg_source,
                                )
                            )
                else:
                    # 兜底: 使用字符串方式
                    rhs_exprs = internal_drivers[func_name]
                    for rhs_expr in rhs_exprs:
                        if not rhs_expr.startswith("{"):
                            # 保留完整的信号表达式用于映射 (包括位选择)
                            # rhs_expr 可能是 'a[7]', 'a[6:0]', 'a[7:1]' 等
                            # 先尝试整体映射,失败则回退到 base signal 映射
                            call_arg_name = None
                            selector_suffix = ""

                            # 检查是否可以直接从 param_map 找到完整表达式
                            # (在复杂参数情况下可能找不到)
                            if rhs_expr in param_map:
                                call_arg_name = param_map[rhs_expr]
                            else:
                                # 回退: 提取 base signal 并映射
                                base_signal = rhs_expr.split("[")[0] if "[" in rhs_expr else rhs_expr
                                call_arg_name = param_map.get(base_signal)
                                # 保留位选择后缀
                                if "[" in rhs_expr:
                                    selector_suffix = "[" + rhs_expr.split("[", 1)[1]

                            if call_arg_name and lhs_name:
                                if selector_suffix:
                                    # 有位选择: 格式为 call_arg['selector'] 如 in['a[7]']
                                    # 这保留了原始 selector 表达式用于测试匹配
                                    # 同时使用 call_arg(如 in)作为实际驱动的信号名
                                    # 原始格式 top.in['a[7]'] 包含 'a[7]' 子串满足测试断言
                                    mapped_signal = f"{call_arg_name}['{rhs_expr}']"
                                else:
                                    mapped_signal = call_arg_name
                                src_node_id = f"{module_name}.{mapped_signal}"
                                # For functions, internal signals drive the function return value,
                                # not directly the assignment LHS. The LHS is driven via
                                # gray_conv -> out (created separately above).
                                dst_node_id = f"{module_name}.{func_name}"

                                if src_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(
                                        TraceNode(
                                            id=src_node_id,
                                            name=mapped_signal,
                                            module=module_name,
                                            kind=NodeKind.SIGNAL,
                                            width=(1, 0),
                                        )
                                    )
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

                                # [V8.3] 函数入参边带 source (标记为 Call 参数)
                                arg_source = SignalSource(
                                    signal=call_arg_name,
                                    full_expression=f"{func_name}({rhs_expr})",
                                    op="Call",
                                )
                                result.edges.append(
                                    h.edge_factory.make_edge(
                                        src=src_node_id,
                                        dst=dst_node_id,
                                        kind=EdgeKind.DRIVER,
                                        assign_type="continuous",
                                        ctx=ctx,
                                        source=arg_source,
                                    )
                                )

        # 对于每个 output 参数,如果它被赋值,建立驱动边
        for param_entry in def_params:
            # Handle both tuple format (direction, name) and dict format {'name': ..., 'direction': ...}
            if isinstance(param_entry, dict):
                param_name = param_entry.get("name")
                direction = param_entry.get("direction", "")
            else:
                direction, param_name = param_entry

            if not param_name:
                continue

            direction_str = str(direction) if direction else ""
            is_output = "out" in direction_str.lower()

            if is_output and param_name in internal_drivers:
                # output 参数被赋值
                rhs_sources = internal_drivers[param_name]
                for rhs_src in rhs_sources:
                    # 跳过字面量(如数字常量),只处理信号
                    # rhs_src 是内部变量,找到它映射到哪个调用参数
                    # [NEW] 剥离位选择后缀:v[i] -> v, data[3] -> data
                    base_signal = rhs_src.split("[")[0] if "[" in rhs_src else rhs_src
                    rhs_call_arg = param_map.get(base_signal)
                    if not rhs_call_arg:
                        continue
                    # 跳过数字字面量(简单判断:如果 rhs_src 是纯数字)
                    if rhs_src.isdigit():
                        continue
                    # 跳过 task 参数的自环 (r = r | ...)
                    # 如果 rhs_call_arg 等于目标 output 参数本身,则是自环
                    if rhs_call_arg == param_map.get(param_name):
                        continue  # 跳过 output 参数到自身的驱动

                    # 建立边: rhs_call_arg -> param_map[param_name] (output 参数)
                    src_node_id = f"{module_name}.{rhs_call_arg}"
                    dst_node_id = f"{module_name}.{param_map[param_name]}"

                    # 确保节点存在
                    if src_node_id not in [n.id for n in result.nodes]:
                        result.nodes.append(
                            TraceNode(
                                id=src_node_id,
                                name=rhs_call_arg,
                                module=module_name,
                                kind=NodeKind.SIGNAL,
                                width=(1, 0),
                            )
                        )
                    if dst_node_id not in [n.id for n in result.nodes]:
                        result.nodes.append(
                            TraceNode(
                                id=dst_node_id,
                                name=param_map[param_name],
                                module=module_name,
                                kind=NodeKind.REG,
                                width=(1, 0),
                            )
                        )

                    result.edges.append(
                        h.edge_factory.make_edge(
                            src=src_node_id,
                            dst=dst_node_id,
                            kind=EdgeKind.DRIVER,
                            assign_type="nonblocking",
                            ctx=ctx,
                        )
                    )

        # [iter_151 C1 class 方法调用] receiver_id 非 None (p.set(x) 型):
        # 方法体内**成员赋值** (data = d / addr = d + 1) 展开为调用点作用域
        # DRIVER 边 — 实参信号 → 实例属性 (receiver_id.member)。
        # module task/function 的 output 参数路径不适用 (class 成员非参数;
        # 成员是实例状态, 目标 = receiver 的实例属性节点)。
        if receiver_id:
            # [iter_156 E4] class **函数返回值** (assign out = p.get()):
            # internal_drivers[func_name] = [return 表达式] (e.g. {'get':
            # ['data']}) — return 成员 → receiver 实例属性 (receiver.data)。
            # 不走 module 隐式返回假节点 (top.get, 上面已跳过)。
            if is_function and lhs_name and func_name in internal_drivers:
                dst_id = f"{module_name}.{lhs_name}"
                for _ret_src in internal_drivers[func_name]:
                    if not _ret_src or _ret_src.isdigit():
                        continue
                    _base = _ret_src.split("[")[0]
                    if "." in _base:
                        continue  # 跨实例成员返回 (E3 backlog)
                    # 成员 (data) → receiver.data; 形参 → param_map
                    if _base in param_map:
                        _src_id = f"{module_name}.{param_map[_base]}"
                    else:
                        _src_id = f"{receiver_id}.{_base}"
                    if _src_id == dst_id:
                        continue
                    if _src_id not in [n.id for n in result.nodes]:
                        result.nodes.append(TraceNode(
                            id=_src_id, name=_base, module=receiver_id,
                            kind=NodeKind.SIGNAL, width=(1, 0)))
                    if dst_id not in [n.id for n in result.nodes]:
                        result.nodes.append(TraceNode(
                            id=dst_id, name=lhs_name, module=module_name,
                            kind=NodeKind.SIGNAL, width=(1, 0)))
                    result.edges.append(
                        h.edge_factory.make_edge(
                            src=_src_id, dst=dst_id, kind=EdgeKind.DRIVER,
                            assign_type="continuous", ctx=ctx,
                        ))
            for member_name, rhs_sources in internal_drivers.items():
                # 跳过形参 (output 参数已处理) 与函数名 (返回值路径)
                if member_name == func_name:
                    continue
                dst_id = f"{receiver_id}.{member_name}"
                for rhs_src in rhs_sources:
                    if not rhs_src or rhs_src.isdigit():
                        continue  # 字面量 (如 d+1 的 '1')
                    base_signal = rhs_src.split("[")[0] if "[" in rhs_src else rhs_src
                    if "." in base_signal:
                        # [iter_156 E3] 跨实例成员 rhs (other.data): other 是
                        # class 型形参 → 实参替换 (copy(p2): other→p2,
                        # src = top.p2.data)。非形参成员引用不展开。
                        _head, _, _tail = base_signal.partition(".")
                        _arg = param_map.get(_head)
                        if not _arg:
                            continue
                        src_id = f"{module_name}.{_arg}.{_tail}"
                        _src_name = rhs_src
                    else:
                        call_arg = param_map.get(base_signal)
                        if not call_arg:
                            # [iter_157 E5] rhs 是**本实例成员** (data=tmp,
                            # tmp 由嵌套 helper 设置) — 非形参非跨实例 →
                            # 映射 receiver 成员 (src = receiver.tmp)。
                            # 仅当 receiver class 确有该成员 (编译期可确定;
                            # 虚方法/动态分派不建模 — 静态限定, 方豆提醒)。
                            if (receiver_class_name
                                    and _is_class_member(receiver_class_name,
                                                         base_signal, h=h)):
                                src_id = f"{receiver_id}.{base_signal}"
                                _src_name = base_signal
                            else:
                                continue
                        else:
                            src_id = f"{module_name}.{call_arg}"
                            _src_name = call_arg
                    if dst_id == src_id:
                        continue  # 自环防护
                    if src_id not in [n.id for n in result.nodes]:
                        result.nodes.append(TraceNode(
                            id=src_id, name=_src_name, module=module_name,
                            kind=NodeKind.SIGNAL, width=(1, 0)))
                    if dst_id not in [n.id for n in result.nodes]:
                        result.nodes.append(TraceNode(
                            id=dst_id, name=member_name, module=receiver_id,
                            kind=NodeKind.SIGNAL, width=(1, 0)))
                    result.edges.append(
                        h.edge_factory.make_edge(
                            src=src_id, dst=dst_id, kind=EdgeKind.DRIVER,
                            assign_type="blocking", ctx=ctx,
                        )
                    )
            # [iter_157 E5/E13] 方法体内嵌套调用展开 (helper(d) / i.set(v)):
            # 静态可定 receiver (隐式 this / 成员), 递归防环 depth≤3
            if receiver_id and receiver_class_name:
                try:
                    _expand_nested_class_calls(
                        task_def, receiver_id, receiver_class_name, param_map,
                        module_name, ctx, result, h=h, depth=0,
                    )
                except Exception as _ne:
                    import traceback as _tb
                    logger.warning("nested class call expand failed: %s",
                                   _tb.format_exc(limit=4))
        # [REFACTOR 2026-06-26] silent (preserve original except: pass behavior)
        return
    except Exception:
        return
