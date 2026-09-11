# _expr_helpers.py — 表达式信号抽取 helpers (iter_175 Step 3 拆分产物)
#
# 原 `SemanticAdapter._extract_signals_from_expr` 474 行 → 分派器 (类内) +
# 本模块的 16 个 kind 处理器 + `_fold_select_index`。
# 从 semantic_adapter.py 移出以便各域 mixin 复用 (避免循环 import)。
"""表达式信号抽取 helpers (纯粹基于 kind 字符串分派, adapter 传入以支持递归)."""
import logging

logger = logging.getLogger(__name__)
from ..._safe import _safe_attr, _safe_str  # noqa: F401  (供 helper 使用)



# =============================================================================
# [iter_174 Step 3] 表达式信号抽取 helpers
# 原 _extract_signals_from_expr 474 行 → 分派器 + 16 个分支处理器 (纯函数)
# 行为不变; 同时删除 2 个不可达重复分支 (Conversion/Conditional 各一)
# =============================================================================

def _fold_select_index(sel: object, ctx: dict):
    if sel is None:
        return None
    sk = str(getattr(sel, "kind", ""))
    if "Literal" in sk:
        v = _safe_attr(sel, "constant", None) or _safe_attr(sel, "value", None)
        if v is not None:
            # [iter_118] ConstantValue.integer 是对象不是 int —
            # 统一 int(str(...)) 解 (str(SVInt)='1')
            try:
                iv = v.integer if hasattr(v, "integer") else v
                return int(str(iv))
            except (ValueError, TypeError):
                return None
        return None
    if "NamedValue" in sk:
        sym = _safe_attr(sel, "symbol", None)
        nm = _safe_attr(sym, "name", None) or getattr(sel, "name", None)
        if nm is None:
            return None
        nm = str(nm)
        return ctx.get(nm) if nm in ctx else None
    if "BinaryOp" in sk:
        op = getattr(sel, "op", None)
        opn = str(getattr(op, "name", op)).lower()
        l = _fold_select_index(getattr(sel, "left", None), ctx)
        r = _fold_select_index(getattr(sel, "right", None), ctx)
        if l is None or r is None:
            return None
        try:
            if opn in ("add", "plus", "+"):
                return l + r
            if opn in ("subtract", "minus", "-"):
                return l - r
            if opn in ("multiply", "times", "*"):
                return l * r
            if opn in ("divide", "div", "/"):
                return int(l / r) if r else None
        except (ValueError, TypeError, ZeroDivisionError):
            return None
        return None
    if "Conversion" in sk:
        return _fold_select_index(getattr(sel, "operand", None), ctx)
    return None



def _expr_identifier_name(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] syntax IdentifierName"""
    signals: list[str] = []
    ident = getattr(expr, "identifier", None)
    if ident:
        val = getattr(ident, "value", None) or str(ident).strip()
        if val:
            signals.append(val.strip())
    return signals


def _expr_scoped_name(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] syntax ScopedName (a.b)"""
    signals: list[str] = []
    left = getattr(expr, "left", None)
    right = getattr(expr, "right", None)
    left_parts = []
    if left:
        left_parts = adapter._extract_signals_from_expr(left)
    if right:
        right_parts = adapter._extract_signals_from_expr(right)
    # Build dotted path: left_part.right_part
    if left_parts and right_parts:
        for lp in left_parts:
            for rp in right_parts:
                signals.append(f"{lp}.{rp}")
    elif right_parts:
        signals.extend(right_parts)
    return signals


def _expr_named_value(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] semantic NamedValue (含 genvar ctx)"""
    signals: list[str] = []
    sym = getattr(expr, "symbol", None)
    if sym:
        name = _safe_attr(sym, "name", None)
        if name:
            name_str = str(name)
            if name_str in ctx:
                signals.append(str(ctx[name_str]))
            else:
                signals.append(name_str)
    return signals


def _expr_conversion(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] semantic Conversion 壳"""
    signals: list[str] = []
    operand = getattr(expr, "operand", None)
    if operand:
        ok = str(getattr(operand, "kind", ""))
        # 跳过字面量 (IntegerLiteral, UnbasedUnsizedIntegerLiteral)
        if "IntegerLiteral" in ok or "UnbasedUnsized" in ok:
            return signals
        signals.extend(adapter._extract_signals_from_expr(operand, ctx))
    return signals


def _expr_inside(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] Inside 表达式"""
    signals: list[str] = []
    signals.extend(adapter._extract_signals_from_expr(getattr(expr, "left", None), ctx))
    rlist = getattr(expr, "rangeList", None)
    if rlist and hasattr(rlist, "__iter__"):
        for r in rlist:
            l = getattr(r, "left", None)  # noqa: E741
            if l:
                signals.extend(adapter._extract_signals_from_expr(l, ctx))
            rr = getattr(r, "right", None)
            if rr:
                signals.extend(adapter._extract_signals_from_expr(rr, ctx))
            if not l and not rr:
                signals.extend(adapter._extract_signals_from_expr(r, ctx))
    return signals


def _expr_dist(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] Dist 表达式"""
    signals: list[str] = []
    left = getattr(expr, "left", None)
    if left:
        signals.extend(adapter._extract_signals_from_expr(left, ctx))
    items = getattr(expr, "items", None)
    if items and hasattr(items, "__iter__"):
        for item in items:
            val = getattr(item, "value", None) or getattr(item, "left", None)
            if val:
                signals.extend(adapter._extract_signals_from_expr(val, ctx))
    return signals


def _expr_member_access(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] MemberAccess (结构/类成员)"""
    signals: list[str] = []
    # pyslang semantic AST: MemberAccessExpression has:
    #   .value: the base expression (e.g. NamedValueExpression for 'req')
    #   .member: ClassPropertySymbol (e.g. 'addr')
    #   .left: may be None in semantic AST (use .value instead)
    #   .syntax: ScopedNameSyntax for the full dotted name
    left = getattr(expr, "left", None) or getattr(expr, "value", None)
    member = getattr(expr, "member", None)
    member_name = None
    if member:
        # ClassPropertySymbol: .name gives the property name
        # [iter_141 CVA6] str(member) 兜底在非 utf8 时 pybind 解码炸 → safe_str
        member_name = (_safe_attr(member, "name", None)
                       or _safe_attr(member, "value", None)
                       or safe_str(member).strip())
        # Strip pyslang Symbol(...) wrapper if present
        if member_name.startswith("Symbol("):
            try:
                member_name = member_name.split('"')[1]
            except (IndexError, AttributeError) as _e:
                logger.debug("提取失败 ((IndexError, AttributeError)): %s", _e)
                pass
    if left and member_name:
        # Recurse into left to get the full dotted path parts
        # [G1 iter_038] recursion 传 ctx
        left_sigs = adapter._extract_signals_from_expr(left, ctx)
        if left_sigs:
            for ls in left_sigs:
                signals.append(f"{ls}.{member_name}")
        else:
            # [V6.9] left might be a NamedValueExpression
            # [iter_140 CVA6] _safe_attr(left,'symbol') 返回 symbol 对象
            # 非 str — f-string 拼接时 pyslang name 解码可能 UnicodeDecodeError
            # (大设计非 utf8 identifier) → safe_str 防护 (失败显式返回 '')
            lname = _safe_attr(left, "symbol", None) or str(getattr(left, "name", "")).strip()
            if lname:
                lname_s = safe_str(lname)
                member_s = safe_str(member_name)
                if lname_s and member_s:
                    signals.append(f"{lname_s}.{member_s}")
    return signals


def _expr_concatenation(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] Concatenation {a,b}"""
    signals: list[str] = []
    for op in getattr(expr, "operands", []):
        signals.extend(adapter._extract_signals_from_expr(op, ctx))
    return signals


def _expr_conditional(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] ternary"""
    signals: list[str] = []
    # Semantic AST: .conditions 列表 (Condition objects), .left/.right 是 AST 节点
    conditions = getattr(expr, "conditions", None)
    if conditions:
        for cond in conditions:
            ce = getattr(cond, "expr", None) or getattr(cond, "expression", None)
            # [G1 iter_038] recursion 传 ctx
            signals.extend(adapter._extract_signals_from_expr(ce, ctx))
    pred = getattr(expr, "predicate", None)
    if pred is not None and not isinstance(pred, str):
        # [G1 iter_038] recursion 传 ctx
        signals.extend(adapter._extract_signals_from_expr(pred, ctx))
    # Syntax AST: .left/.right 返回字符串, 需要遍历子节点
    left = getattr(expr, "left", None)
    right = getattr(expr, "right", None)
    if left is not None and not isinstance(left, str):
        # [G1 iter_038] recursion 传 ctx
        signals.extend(adapter._extract_signals_from_expr(left, ctx))
    if right is not None and not isinstance(right, str):
        # [G1 iter_038] recursion 传 ctx
        signals.extend(adapter._extract_signals_from_expr(right, ctx))
    # [V6.9] Syntax: 如果 left/right 是字符串, 遍历子节点提取 IdentifierName
    if (left is None or isinstance(left, str)) or (right is None or isinstance(right, str)):
        try:
            for child in expr:
                ck = str(getattr(child, "kind", ""))
                if "IdentifierName" in ck:
                    ident = getattr(child, "identifier", None)
                    if ident:
                        val = getattr(ident, "value", None) or str(ident).strip()
                        if val:
                            signals.append(val.strip())
                elif "ConditionalPredicate" in ck or "Predicate" in ck:
                    # 递归提取条件信号
                    try:
                        for pchild in child:
                            pck = str(getattr(pchild, "kind", ""))
                            if "IdentifierName" in pck:
                                pident = getattr(pchild, "identifier", None)
                                if pident:
                                    pval = getattr(pident, "value", None) or str(pident).strip()
                                    if pval:
                                        signals.append(pval.strip())
                    except (TypeError, AttributeError) as e:
                        logger.warning("提取失败: %s", e)
        except (TypeError, AttributeError) as e:
            logger.warning("提取失败: %s", e)
    return signals


def _expr_assignment(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] Assignment 表达式"""
    signals: list[str] = []
    # [G1 iter_038] 传 ctx 给 left/right recursion
    signals.extend(adapter._extract_signals_from_expr(getattr(expr, "left", None), ctx))
    signals.extend(adapter._extract_signals_from_expr(getattr(expr, "right", None), ctx))
    return signals


def _expr_binary(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] BinaryOp"""
    signals: list[str] = []
    # [G1 iter_038] 传 ctx 给 left/right recursion
    signals.extend(adapter._extract_signals_from_expr(getattr(expr, "left", None), ctx))
    signals.extend(adapter._extract_signals_from_expr(getattr(expr, "right", None), ctx))
    return signals


def _expr_unary(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] UnaryOp"""
    signals: list[str] = []
    # [G1 iter_038] 传 ctx 给 operand recursion
    signals.extend(adapter._extract_signals_from_expr(getattr(expr, "operand", None), ctx))
    return signals


def _expr_call(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] Call/Invocation"""
    signals: list[str] = []
    args = getattr(expr, "arguments", None) or getattr(expr, "args", None) or []
    if args and hasattr(args, "__iter__") and not isinstance(args, str):
        for arg in args:
            signals.extend(adapter._extract_signals_from_expr(arg))
    return signals


def _expr_element_select(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] ElementSelect (含 ctx 折叠)"""
    signals: list[str] = []
    # Get the base signal
    # [G1 iter_038] 传 ctx 给 base + selector recursion
    base_signals = adapter._extract_signals_from_expr(_safe_attr(expr, "value", None), ctx)
    # Get the selector (bit index)
    selector = getattr(expr, "selector", None)
    if selector and base_signals:
        # selector is an expression (IntegerLiteral or ParameterExpression)
        sel_kind = getattr(selector, "kind", None)
        if sel_kind:
            sel_kind_str = str(sel_kind)
            if "IntegerLiteral" in sel_kind_str:
                # Get the integer value
                # [G1 iter_038] pyslang 11.x folded selectors expose .constant (ConstantValue)
                #   not .value. Try .constant first, fallback to .value.
                sel_val = _safe_attr(selector, "constant", None)
                if sel_val is None:
                    sel_val = _safe_attr(selector, "value", None)
                if sel_val is not None and hasattr(sel_val, "integer"):
                    try:
                        sel_val = int(sel_val.integer)
                    except Exception:
                        sel_val = str(sel_val.integer)
                if sel_val is not None:
                    for base in base_signals:
                        signals.append(f"{base}[{sel_val}]")
                    return signals
            elif "Parameter" in sel_kind_str:
                # Parameter expression - try to get value
                try:
                    sel_val = str(selector)  # Fallback to string representation
                except Exception:
                    sel_val = _safe_attr(selector, "name", None) or str(selector)
                for base in base_signals:
                    signals.append(f"{base}[{sel_val}]")
                return signals
            else:
                # [iter_118] genvar-ctx 求值 (NamedValue 'i' / BinaryOp 'i-1'):
                # generate-for entry 内 RHS 位选 — 修 x[i-1] 错解析成整总线
                fold_idx = _fold_select_index(selector, ctx)
                if fold_idx is not None:
                    for base in base_signals:
                        signals.append(f"{base}[{fold_idx}]")
                    return signals
    # Fallback: just return base signal
    return base_signals


def _expr_range_select(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] RangeSelect"""
    signals: list[str] = []
    # Get the base signal
    # [G1 iter_038] 传 ctx 给 base recursion
    base_signals = adapter._extract_signals_from_expr(_safe_attr(expr, "value", None), ctx)
    # Get the range (left/right or selector with left/right)
    left = getattr(expr, "left", None)
    right = getattr(expr, "right", None)
    if not left or not right:
        # Maybe stored as selector with left/right
        selector = getattr(expr, "selector", None)
        if selector:
            left = getattr(selector, "left", None)
            right = getattr(selector, "right", None)
    if left and right:
        # [G1 iter_038] .constant fallback for pyslang 11.x folded selectors
        left_val = _safe_attr(left, "constant", None) or _safe_attr(left, "value", None)
        right_val = _safe_attr(right, "constant", None) or _safe_attr(right, "value", None)
        # .constant may be ConstantValue → unwrap .integer
        if hasattr(left_val, "integer"):
            try:
                left_val = int(left_val.integer)
            except Exception:
                left_val = str(left_val.integer)
        if hasattr(right_val, "integer"):
            try:
                right_val = int(right_val.integer)
            except Exception:
                right_val = str(right_val.integer)
        # [iter_118] genvar-ctx 求值 (generate entry 内 x[i*4+:4] 等范围)
        if left_val is None:
            left_val = _fold_select_index(left, ctx)
        if right_val is None:
            right_val = _fold_select_index(right, ctx)
        for base in base_signals:
            if left_val is not None and right_val is not None:
                signals.append(f"{base}[{left_val}:{right_val}]")
            else:
                signals.append(f"{base}[?:?]")
        return signals
    # Fallback: just return base signal
    return base_signals


def _expr_integer_literal(adapter: "SemanticAdapter", expr, ctx: dict) -> list[str]:
    """[iter_174 Step 3] IntegerLiteral (非信号)"""
    signals: list[str] = []
    return signals

