# ==============================================================================
# extractors/_common.py - 共享 helper 协议 + 共享纯函数
#
# [ARCHITECTURE_TODOLIST #1] 拆 driver_extractor.py 4101 行的共享基础设施.
# 所有 extractor (alias/assign/always/wire_init/...) 通过 callback 协议或
# 直接 import 共享函数使用这些 helper.
#
# 历史:
# 2026-08-27 20:38 — 创建, 加 Protocol + EdgeKind 重导出
# 2026-08-27 21:33 — [Step 3] 加 _BINOP_SYMBOL / fold_constant / get_signal
#                    三个共享 helper, 原因: _get_signal 在 driver_extractor 内
#                    被调 ~40 次, 是 assign/always/wire_init 都依赖的核心
#                    helper, 必须共享而非复制.
# ==============================================================================
from typing import Any, Callable, Optional, Protocol

# [Step 3] BinaryOperator -> 可读符号映射表
# 从 driver_extractor.py line 78-109 搬过来. 跟 pyslang AST BinaryOperator enum 对齐.
# 之前作为类属性 _BINOP_SYMBOL, 现在变成模块级常量, 所有 extractor 可共享.
try:
    from pyslang import BinaryOperator  # type: ignore
    _BINOP_SYMBOL: dict[Any, str] = {
        BinaryOperator.Add: "+",
        BinaryOperator.ArithmeticShiftLeft: "<<<",
        BinaryOperator.ArithmeticShiftRight: ">>>",
        BinaryOperator.BinaryAnd: "&",
        BinaryOperator.BinaryOr: "|",
        BinaryOperator.BinaryXnor: "~^",
        BinaryOperator.BinaryXor: "^",
        BinaryOperator.CaseEquality: "===",
        BinaryOperator.CaseInequality: "!==",
        BinaryOperator.Divide: "/",
        BinaryOperator.Equality: "==",
        BinaryOperator.GreaterThan: ">",
        BinaryOperator.GreaterThanEqual: ">=",
        BinaryOperator.Inequality: "!=",
        BinaryOperator.LessThan: "<",
        BinaryOperator.LessThanEqual: "<=",
        BinaryOperator.LogicalAnd: "&&",
        BinaryOperator.LogicalEquivalence: "<->",
        BinaryOperator.LogicalImplication: "->",
        BinaryOperator.LogicalOr: "||",
        BinaryOperator.LogicalShiftLeft: "<<",
        BinaryOperator.LogicalShiftRight: ">>",
        BinaryOperator.Mod: "%",
        BinaryOperator.Multiply: "*",
        BinaryOperator.Power: "**",
        BinaryOperator.Subtract: "-",
        BinaryOperator.WildcardEquality: "==?",
        BinaryOperator.WildcardInequality: "!=?",
    }
except ImportError:
    # pyslang 不在测试环境时 (e.g. lint-only CI) 仍能 import 这个模块
    _BINOP_SYMBOL = {}


class ExtractorHelpers(Protocol):
    """[2026-08-27 20:38] Extractor 共享的 helper 协议.

    driver_extractor.DriverExtractor 实例隐式满足该协议
    (它实现了 ensure_signal_node / append_edge).
    extractor 模块通过 receive 这些 callable 来工作, 不依赖 DriverExtractor 类.
    """

    def ensure_signal_node(
        self,
        result: Any,
        node_id: str,
        name: str,
        module_name: str,
        file: str = "",
        line: int = 0,
    ) -> None:
        """确保 result.nodes 包含指定 id 的 TraceNode. 已存在则跳过."""
        ...

    def append_edge(
        self,
        result: Any,
        src: str,
        dst: str,
        kind: Any = None,
        assign_type: str = "",
        **kwargs: Any,
    ) -> None:
        """统一入口: 走 edge factory 创建 TraceEdge 并 append 到 result.edges."""
        ...


EnsureSignalNodeFn = Callable[[Any, str, str, str, str, int], None]
AppendEdgeFn = Callable[..., None]


# ==============================================================================
# [Step 3 2026-08-27 21:33] 共享纯函数: fold_constant + get_signal
# 从 driver_extractor.py line 729-806 / line 528-728 搬过来.
# 完全无 self 依赖 (除 fold_constant 自身递归), 改纯函数化.
# get_signal 接收 current_module 参数替代原 self._current_module.
# ==============================================================================

def fold_constant(expr: Any, ctx: Optional[dict] = None) -> Optional[int]:
    """[Plan F1 2026-08-12] 对含 genvar substitute 后的表达式求 constant.

    [Step 3 2026-08-27] 从 driver_extractor._fold_constant 改为纯函数.

    处理:
    - IntegerLiteral (constant SVInt): 直接返 int
    - NamedValueExpression: 如果 name 在 ctx 里, 返 ctx[name]
    - BinaryOp (a + b / a - b): 递归 fold 两边, 应用 operator
    - UnaryOp (-a): fold operand, 应用 unary minus
    - 其他 (CallExpression 等): 返 None (不能 fold)

    Returns:
        int: 表达式求值后的 constant
        None: 不能 fold (例如含 function call)
    """
    if expr is None:
        return None
    ctx = ctx or {}
    sk = str(getattr(expr, "kind", ""))

    # IntegerLiteral
    if "IntegerLiteral" in sk or "Literal" in sk:
        val = getattr(expr, "value", None)
        if val is not None:
            try:
                return int(str(val))
            except (TypeError, ValueError):
                return None

    # NamedValue: name 在 ctx → substitute
    if "NamedValue" in sk:
        sym = getattr(expr, "symbol", None)
        if sym:
            name = getattr(sym, "name", None)
            if name and str(name) in ctx:
                return int(ctx[str(name)])

    # BinaryOp: 递归
    if "BinaryOp" in sk:
        left = getattr(expr, "left", None)
        right = getattr(expr, "right", None)
        op = getattr(expr, "op", None)
        lv = fold_constant(left, ctx)
        rv = fold_constant(right, ctx)
        if lv is None or rv is None:
            return None
        op_str = str(op).lower() if op else ""
        try:
            if op_str.endswith(".add") or op_str == "+":
                return lv + rv
            if op_str.endswith(".subtract") or op_str == "-":
                return lv - rv
            if op_str.endswith(".multiply") or op_str == "*":
                return lv * rv
            if op_str.endswith(".divide") or op_str == "/":
                return lv // rv if rv != 0 else None
            if op_str.endswith(".mod") or op_str == "%":
                return lv % rv if rv != 0 else None
            return None
        except (TypeError, ZeroDivisionError):
            return None

    # UnaryOp
    if "UnaryOp" in sk:
        operand = getattr(expr, "operand", None)
        ov = fold_constant(operand, ctx)
        if ov is None:
            return None
        return -ov

    # [Plan F1.1 2026-08-12] ConversionExpression (pyslang 包装类型转换)
    if "Conversion" in sk:
        operand = getattr(expr, "operand", None)
        return fold_constant(operand, ctx)

    return None


def get_signal(
    signal: Any,
    ctx: Optional[dict] = None,
    current_module: Any = None,
) -> Optional[str]:
    """[V6.9] 获取信号名 — 优先用 semantic API, fallback 到 str().

    [Step 3 2026-08-27] 从 driver_extractor._get_signal 改为纯函数.
    原 self 依赖:
      - self._BINOP_SYMBOL → 改用本模块 _BINOP_SYMBOL
      - self._fold_constant → 改用 fold_constant()
      - self._current_module → 改用 current_module 参数 (调用方传)

    syntax AST 节点的 str() 包含前导空格和换行符, 必须 strip() 后使用.

    [Plan F1 2026-08-12] genvar_ctx 参数:
    - 顶层 assigns 传 None 或 {}
    - generate for 内的 assigns 传 {genvar_name: entry.arrayIndex}
      e.g. gen_accum[1] 内的 assign → {'i': 1}
    - NamedValueExpression name 是 genvar → substitute 成 concrete value
    - BinaryOp (i+1) → 递归 substitute 子节点
    """
    if signal is None:
        return None
    ctx = ctx or {}
    # NamedValue: 通过 .symbol.name 获取 (不是 str())
    sk = str(getattr(signal, "kind", ""))
    if "NamedValue" in sk:
        sym = getattr(signal, "symbol", None)
        if sym:
            name = getattr(sym, "name", None)
            if name:
                name_str = str(name).strip()
                # [Plan F1] genvar substitute
                if name_str in ctx:
                    return str(ctx[name_str])
                return name_str
    # IdentifierName: 通过 .identifier.value 获取
    if "IdentifierName" in sk:
        ident = getattr(signal, "identifier", None)
        if ident:
            val = getattr(ident, "value", None) or str(ident)
            return str(val).strip()
    # BinaryOp: 递归展开为 "left op right" — 保留操作符
    if "BinaryOp" in sk:
        left = getattr(signal, "left", None)
        right = getattr(signal, "right", None)
        op = getattr(signal, "op", None)
        op_sym = _BINOP_SYMBOL.get(op, "?") if op else "?"
        ls = get_signal(left, ctx, current_module) if left else "?"
        rs = get_signal(right, ctx, current_module) if right else "?"
        if ls and rs:
            return f"{ls} {op_sym} {rs}"
        return ls or rs or None
    # UnaryOp: 递归展开为 "op operand" — 避免对象引用
    if "UnaryOp" in sk:
        operand = getattr(signal, "operand", None)
        op_str = get_signal(operand, ctx, current_module) if operand else "?"
        return f"!{op_str}" if op_str else None
    # Replication: {N{expr}} — 返回 "{N{expr}}"
    if "Replication" in sk:
        count = getattr(signal, "count", None)
        concat = getattr(signal, "concat", None)
        cnt_str = get_signal(count, ctx, current_module) if count else "?"
        concat_str = get_signal(concat, ctx, current_module) if concat else "?"
        if cnt_str and concat_str:
            return f"{{{cnt_str}{{{concat_str}}}}}"
        return None
    # Concatenation: {a, b, c} — 展开 operands
    if "Concatenation" in sk:
        operands = getattr(signal, "operands", None) or []
        parts = [get_signal(o, ctx, current_module) or str(o) for o in operands if o]
        return "{" + ", ".join(parts) + "}" if parts else None
    # ConversionExpression: type cast (e.g., 8'hAA → int literal)
    if "Conversion" in sk:
        operand = getattr(signal, "operand", None)
        if operand:
            ok = str(getattr(operand, "kind", ""))
            if "IntegerLiteral" in ok or "UnbasedUnsized" in ok:
                val = getattr(operand, "value", None)
                if val is not None:
                    return str(val)
            elif "NamedValue" in ok:
                return get_signal(operand, ctx, current_module)
            elif "Call" in ok or "Invocation" in ok:
                sub = getattr(operand, "subroutine", None) or getattr(operand, "name", None)
                if sub:
                    sname = getattr(sub, "name", None)
                    if sname:
                        return str(sname)
                    return str(sub).strip()
                return str(operand).strip()
            sig = get_signal(operand, ctx, current_module)
            if sig and not sig.startswith("Expression("):
                return sig
            return str(operand)
    # ElementSelect: data_out[0]
    if "ElementSelect" in sk:
        base = getattr(signal, "value", None) or getattr(signal, "base", None)
        selector = getattr(signal, "selector", None)
        base_name = get_signal(base, ctx, current_module) if base else None
        folded = fold_constant(selector, ctx)
        if folded is not None:
            sel_str = str(folded)
        else:
            sel_val = getattr(selector, "value", None) if selector else None
            if sel_val is not None:
                try:
                    sel_str = str(int(sel_val))
                except (TypeError, ValueError):
                    sel_str = get_signal(selector, ctx, current_module) or str(sel_val)
            else:
                sel_str = get_signal(selector, ctx, current_module) or "x"
        if base_name:
            return f"{base_name}[{sel_str}]"
        return None
    # RangeSelect: data[3:0]
    if "RangeSelect" in sk:
        base = getattr(signal, "value", None) or getattr(signal, "base", None)
        left = getattr(signal, "left", None)
        right = getattr(signal, "right", None)
        base_name = get_signal(base, ctx, current_module) if base else None
        lv = getattr(left, "value", None) if left else None
        rv = getattr(right, "value", None) if right else None
        if lv is not None:
            try:
                li = int(lv)
            except (TypeError, ValueError):
                li = get_signal(left, ctx, current_module) or str(lv)
        else:
            li = get_signal(left, ctx, current_module) or "x"
        if rv is not None:
            try:
                ri = int(rv)
            except (TypeError, ValueError):
                ri = get_signal(right, ctx, current_module) or str(rv)
        else:
            ri = get_signal(right, ctx, current_module) or "x"
        if base_name:
            return f"{base_name}[{li}:{ri}]"
        return None
    # MemberAccess: pkt.addr → base 信号 + .member
    if "MemberAccess" in sk:
        base = getattr(signal, "value", None) or getattr(signal, "base", None)
        member = getattr(signal, "member", None)
        member_str = str(getattr(member, "name", member)) if member else ""
        base_name = get_signal(base, ctx, current_module) if base else None
        if base_name and member_str:
            return f"{base_name}.{member_str}"
        return None
    # HierarchicalValue: tb.data / ifc.data → 从 semantic AST 解析分量路径
    if "HierarchicalValue" in sk:
        sym = getattr(signal, "symbol", None)
        if sym:
            sname = str(getattr(sym, "name", "")).strip()
            if sname:
                dd = getattr(sym, "declaringDefinition", None)
                defn_type = str(getattr(dd, "name", "")).strip() if dd else ""
                if defn_type and current_module:
                    body = getattr(current_module, "body", None)
                    if body:
                        for port in body:
                            pk = str(getattr(port, "kind", ""))
                            pn = str(getattr(port, "name", "")).strip()
                            if "InterfacePort" in pk:
                                idf = getattr(port, "interfaceDef", None)
                                if idf and str(getattr(idf, "name", "")) == defn_type:
                                    return f"{pn}.{sname}"
                            elif "Instance" in pk and getattr(port, "isInterface", False):
                                idef = getattr(port, "definition", None)
                                if idef and str(getattr(idef, "name", "")) == defn_type:
                                    return f"{pn}.{sname}"
                            elif "Instance" in pk:
                                idef = getattr(port, "definition", None)
                                if idef and str(getattr(idef, "name", "")) == defn_type:
                                    return f"{pn}.{sname}"
                    return sname
    # fallback: str() + strip()
    result_str = str(signal).strip()
    result_str = result_str.replace('\n', '').replace('\r', '').strip()
    if result_str.startswith("Expression(") or result_str.startswith("<"):
        val = getattr(signal, "value", None)
        if val is not None and not callable(val):
            vs = str(val).strip()
            if vs and not vs.startswith("Expression("):
                return vs
        sym = getattr(signal, "symbol", None)
        if sym:
            name = getattr(sym, "name", None)
            if name:
                return str(name).strip()
    return result_str if result_str else None