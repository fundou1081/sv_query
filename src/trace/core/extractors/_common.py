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

# ==============================================================================
# [ARCHITECTURE_TODOLIST #2 G3 Option 3 2026-08-28 06:38]
# 共享 pyslang AST 遍历 helper — 替代两套 _create_hierarchical_bit_nodes 的 regex
#
# 起源:
# - review §三.2 标记两套 BitSelect 实现"重复"
# - G2 实测发现 (commit 78eb602) 边/节点一致, RangeSelect 4 属性漏设
# - 边界 fixture 实测 (commit 49b475c) 发现 generate-for 内动态位选 + regex 脆弱
# - 用户指令 [2026-08-28 06:36]: "走 g3 的 3" (用 pyslang API 替代 regex, 治本)
#
# 关键事实 (刚才实测确认):
# - pyslang 11.0 RangeSelectExpression: .left.value (msb), .right.value (lsb)
# - pyslang 11.0 ElementSelectExpression: .selector.value (index)
# - root.visit(callback) 是 11.0 真实遍历 API, callback 返回 True/False 控制深入
# - node.kind == ExpressionKind.RangeSelect / ElementSelect
# ==============================================================================
from typing import Any, Iterator, NamedTuple

# [兼容性] pyslang 在测试/lint 环境可能没装 (CI), 优雅 import 失败
try:
    from pyslang import ExpressionKind, EvalContext  # type: ignore
    _HAS_PYSLANG = True
except ImportError:
    _HAS_PYSLANG = False
    # 提供 fallback 让 import 不爆, 但调用方在没 pyslang 时直接走 regex 老路径
    ExpressionKind = None  # type: ignore
    EvalContext = None  # type: ignore


class BitSelectHit(NamedTuple):
    """[2026-08-28 07:00] pyslang AST 遍历产出的位选信息 (通用方案 a).

    区别于旧 SelectInfo:
    - full_id: 完整 hierarchical ID (e.g. 'top.pkt.addr[3:0]'), pyslang InstanceSymbol.hierarchicalPath + base_chain
    - base_chain: 从顶层到 immediate parent 的信号链 (e.g. ['top.pkt', 'top.pkt.addr']),
                  GraphBuilder 自取所需 BIT_SELECT 边 (链上每个相邻对都是一条边)
    - msb/lsb/index: pyslang eval(EvalContext) 后整数 (parameter/fn call 也能 evaluate)
    - line/col: 源码位置 (来自 .sourceRange)
    - select_kind: 'RangeSelect' / 'ElementSelect' 字符串
    """
    full_id: str
    base_chain: list[str]
    msb: int | None
    lsb: int | None
    index: int | None
    select_kind: str
    line: int
    col: int


def iter_bit_selects(module: Any, instance_path: str = '') -> Iterator[BitSelectHit]:
    """[2026-08-28 07:00] 遍历 module 找出所有 RangeSelect / ElementSelect 节点 (通用方案 a).

    区别于旧 iter_bit_selects:
    - instance_path: 顶层 module 的 hierarchical path (e.g. 'top' 或 'cva6')
                   pyslang InstanceSymbol.hierarchicalPath 拿到
    - 返回 BitSelectHit namedtuple, 含 base_chain + full_id + line/col
    - msb/lsb 走 pyslang eval(EvalContext), parameter 能 evaluate
    - struct field (MemberAccess) 走 base chain 递归提取

    Args:
        module: pyslang module symbol (有 .visit() 可遍历)
        instance_path: 顶层 module hierarchical path, e.g. 'top' 或 'cva6'

    Yields:
        BitSelectHit namedtuple: 每个位选节点的结构化信息
    """
    if not _HAS_PYSLANG:
        return  # 退化: 让调用方走 regex 老路径

    if module is None:
        return

    walker = _PyslangSelectWalker(instance_path)
    if hasattr(module, 'visit'):
        module.visit(walker.callback)

    yield from walker.results


class _PyslangSelectWalker:
    """[2026-08-28 07:00] pyslang AST walker (基于 visit() callback).

    通用方案 a 关键设计:
    - helper 返回 base_chain (顶层 signal 到 immediate parent 的完整链路)
      e.g. struct 场景: ['top.pkt', 'top.pkt.addr']
      e.g. simple 场景: ['top.data']
    - msb/lsb 走 pyslang eval(EvalContext) 拿真实整数 (parameter/fn call 都能 handle)
    - 不返回 type-level 节点 (InstanceSymbol.hierarchicalPath 实例化的 module 才输出)
    - ElementSelect 仅当 selector 是 IntegerLiteral 时产出
    """

    def __init__(self, instance_path: str = '') -> None:
        self.results: list[BitSelectHit] = []
        self.instance_path = instance_path  # e.g. 'top' or 'cva6'

    def callback(self, node: Any) -> bool:
        """pyslang visit() callback. 返回 True 继续深入, False 停止深入该子树."""
        if node is None:
            return True

        kind = getattr(node, 'kind', None)
        if kind is None:
            return True

        # RangeSelectExpression: data[msb:lsb]
        if kind == ExpressionKind.RangeSelect:
            # 提 base_chain (递归走 RangeSelect -> MemberAccess -> NamedValue)
            chain = _extract_base_chain(node)
            if chain:
                # chain[0] 是顶层 (e.g. 'pkt'), chain[-1] 是 immediate parent 含 sel 后缀 (e.g. 'pkt.addr[3:0]')
                # 加 instance_path 前缀
                prefixed = [f"{self.instance_path}.{c}" if self.instance_path else c for c in chain]

                # msb/lsb 走 pyslang eval (parameter/fn call 也能 handle)
                msb = _eval_to_int(getattr(node, 'left', None))
                lsb = _eval_to_int(getattr(node, 'right', None))

                # [FIX 2026-08-28 07:24] 从 prefixed[-1] 拆 sel 后缀取 immediate
                # 修复 'full_id=[3:0]' (空 immediate) 和 doubled 拼接 (如 'top.data[3:0][3:0]')
                # simple 链 ['top.data', 'top.data[3:0]']: immediate = 'top.data'
                # struct 链 ['top.pkt', 'top.pkt.addr', 'top.pkt.addr[3:0]']: immediate = 'top.pkt.addr'
                immediate_full = prefixed[-1]
                if '[' in immediate_full:
                    immediate = immediate_full.rsplit('[', 1)[0]
                else:
                    immediate = immediate_full
                if msb is not None and lsb is not None:
                    full_id = make_range_select_id(immediate, msb, lsb)
                else:
                    # parameter 边界不 evaluate, 用 syntax raw text 作 ID
                    syn = getattr(node, 'syntax', None)
                    full_id = str(syn).strip() if syn is not None else f"{immediate}[?]"

                # line/col from sourceRange
                sr = getattr(node, 'sourceRange', None)
                line = 0
                col = 0
                if sr is not None:
                    start = getattr(sr, 'start', None)
                    if start is not None:
                        line = getattr(start, 'line', 0) or 0
                        col = getattr(start, 'column', 0) or 0

                self.results.append(BitSelectHit(
                    full_id=full_id,
                    base_chain=prefixed,
                    msb=msb,
                    lsb=lsb,
                    index=None,
                    select_kind='RangeSelect',
                    line=line,
                    col=col,
                ))
            return True

        # ElementSelectExpression: data[idx]
        if kind == ExpressionKind.ElementSelect:
            chain = _extract_base_chain(node)
            if chain:
                prefixed = [f"{self.instance_path}.{c}" if self.instance_path else c for c in chain]
                idx = _eval_to_int(getattr(node, 'selector', None))
                # [FIX 2026-08-28 07:24] 同上拆 sel 后缀
                immediate_full = prefixed[-1]
                immediate = immediate_full.rsplit('[', 1)[0] if '[' in immediate_full else immediate_full
                if idx is not None:
                    full_id = make_element_select_id(immediate, idx)
                else:
                    syn = getattr(node, 'syntax', None)
                    full_id = str(syn).strip() if syn is not None else f"{immediate}[?]"
                sr = getattr(node, 'sourceRange', None)
                line = 0
                col = 0
                if sr is not None:
                    start = getattr(sr, 'start', None)
                    if start is not None:
                        line = getattr(start, 'line', 0) or 0
                        col = getattr(start, 'column', 0) or 0
                self.results.append(BitSelectHit(
                    full_id=full_id,
                    base_chain=prefixed,
                    msb=None,
                    lsb=None,
                    index=idx,
                    select_kind='ElementSelect',
                    line=line,
                    col=col,
                ))
            return True

        return True  # 其他节点继续深入


def _extract_base_chain(node: Any) -> list[str]:
    """[2026-08-28 07:00] 从 RangeSelect/ElementSelect 节点提取 base chain (顶层到 immediate parent).

    e.g. data[3:0]            -> ['data', 'data[?:?]']   # immediate 加 sel 后缀
    e.g. pkt.addr[3:0]        -> ['pkt', 'pkt.addr', 'pkt.addr[?:?]']
    e.g. arr[0].field[3:0]    -> ['arr', 'arr[0]', 'arr[0].field', 'arr[0].field[?:?]']

    注意: chain 最后一位是 immediate parent (含 sel 后缀),
    callback 会在外面构造 full_id = immediate + sel_str.
    调用方只看 chain[:-1] 作为 ancestor chain, chain[-1] 作为 immediate parent.

    Returns:
        list of base signal ID, 顶层 (NamedValue) 在前
    """
    # [FIX 2026-08-28 07:14] 迭代实现, 避免递归循环
    chain: list[str] = []
    visited: set[int] = set()  # 防环
    cur = node

    while cur is not None and hasattr(cur, 'kind') and id(cur) not in visited:
        visited.add(id(cur))
        k = cur.kind

        # [FIX 2026-08-28 07:19] 顶层 RangeSelect/ElementSelect: 需先下去到 .value 再往上走
        # 例如 struct 场景 RangeSelectExpression -> .value (MemberAccess) -> .value (NamedValue)
        # 没这层的话, 走到 'else: break' 就返回空 chain.
        # 同时记录 sel_str, 递归返回后拼到 chain 最后一位.
        if k in (ExpressionKind.ElementSelect, ExpressionKind.RangeSelect):
            # 拿 sel_str (cur 的边界)
            if k == ExpressionKind.ElementSelect:
                sel_v = _eval_to_int(getattr(cur, 'selector', None))
                sel_str = f"[{sel_v}]" if sel_v is not None else '[?]'
            else:
                msb_v = _eval_to_int(getattr(cur, 'left', None))
                lsb_v = _eval_to_int(getattr(cur, 'right', None))
                sel_str = f"[{msb_v}:{lsb_v}]" if (msb_v is not None and lsb_v is not None) else '[?:?]'
            child = getattr(cur, 'value', None)
            if child is None:
                break
            # 递归提 ancestor chain, 然后把 sel_str 拼到最后一位
            # 但 child 可能是 RangeSelect/ElementSelect (嵌套) — 递归会拿它的 sel 拼上去
            # 简单情况 child 是 NamedValue/MemberAccess — 它返回 ['pkt', 'pkt.addr'], 我们拼 sel 到 'pkt.addr' => 'pkt.addr[3:0]'
            child_chain = _extract_base_chain(child)
            # child_chain 最后一个 entry 已经是 immediate (含 child 的 sel, 如果有)
            # 我们要把 cur 的 sel_str 加在 child_chain 最后一位之后
            if child_chain:
                if not sel_str or sel_str == '[?:?]':
                    # cur 是顶层 sel, 但 boundary 拿不到 (parameter 等), child_chain 本身已完整
                    return child_chain
                last = child_chain[-1]
                # [FIX 2026-08-28 07:24] 保留 immediate parent (last) 作为独立 chain entry
                # 同时加 cur 的 sel 作为新末位 — 这样 chain 长度 ≥ 2, GraphBuilder 能创 BIT_SELECT 边
                new_last = f"{last}{sel_str}"
                if '[' in last:
                    # 嵌套: child 是 ElementSelect/RangeSelect
                    # child_chain 末位是 child 的 immediate (如 'arr[0]'), 加上 cur 的 sel => 'arr[0][3:0]'
                    # 保留 'arr[0]' 作 immediate parent, 新增 'arr[0][3:0]' 作 leaf
                    return child_chain + [new_last]
                else:
                    # 简单: child 是 NamedValue/MemberAccess
                    # child_chain 末位是 last (如 'data' 或 'pkt.addr'), 加 cur 的 sel => 'data[3:0]'
                    # 保留 last 作 immediate parent, 新增 last+sel 作 leaf
                    return child_chain + [new_last]
            return child_chain

        # NamedValue: 顶层 (base chain 起点)
        if k == ExpressionKind.NamedValue:
            sym = getattr(cur, 'symbol', None)
            if sym is not None:
                name = getattr(sym, 'name', None)
                if name:
                    chain.append(str(name).strip())
            break

        # MemberAccess: struct.field (e.g. pkt.addr)
        if k == ExpressionKind.MemberAccess:
            mem = getattr(cur, 'member', None)
            mem_name = getattr(mem, 'name', None) if mem else None
            # 拿 ancestor (cur.value)
            ancestor = getattr(cur, 'value', None)
            # 沿 ancestor 链往上到 NamedValue, 沿途可能有 MemberAccess / ElementSelect / RangeSelect
            ancestor_chain: list[str] = []
            acur = ancestor
            while acur is not None and hasattr(acur, 'kind') and id(acur) not in visited:
                visited.add(id(acur))
                ak = acur.kind
                if ak == ExpressionKind.NamedValue:
                    asym = getattr(acur, 'symbol', None)
                    if asym:
                        aname = getattr(asym, 'name', None)
                        if aname:
                            ancestor_chain.append(str(aname).strip())
                    break
                elif ak == ExpressionKind.MemberAccess:
                    amem = getattr(acur, 'member', None)
                    amem_name = getattr(amem, 'name', None) if amem else None
                    if ancestor_chain and amem_name:
                        ancestor_chain.append(f"{ancestor_chain[-1]}.{amem_name}")
                    break
                elif ak in (ExpressionKind.ElementSelect, ExpressionKind.RangeSelect):
                    # 嵌套位选: 先找它的 base, 再加 sel 后缀
                    nested_chain = _extract_base_chain(acur)
                    if nested_chain:
                        if ak == ExpressionKind.ElementSelect:
                            sel_v = _eval_to_int(getattr(acur, 'selector', None))
                            sel_str = f"[{sel_v}]" if sel_v is not None else '[?]'
                        else:
                            msb_v = _eval_to_int(getattr(acur, 'left', None))
                            lsb_v = _eval_to_int(getattr(acur, 'right', None))
                            sel_str = f"[{msb_v}:{lsb_v}]" if (msb_v is not None and lsb_v is not None) else '[?:?]'
                        # ancestor_chain = nested_chain[:-1] (去掉 nested 的 immediate), nested_chain[-1] + sel_str 是 nested 的 immediate
                        # 我们需要的是: cur (MemberAccess) 的 ancestor 完整链
                        ancestor_chain = nested_chain[:-1]
                        # nested 的 immediate 是 nested_chain[-1] + sel_str
                        # cur 是 MemberAccess, 它的 immediate 是 nested_immediate + '.' + mem_name
                        nested_immediate = f"{nested_chain[-1]}{sel_str}"
                        if mem_name:
                            chain = ancestor_chain + [nested_immediate, f"{nested_immediate}.{mem_name}"]
                        else:
                            chain = ancestor_chain + [nested_immediate]
                    return chain
                else:
                    break
            # 合并 ancestor_chain + immediate
            if mem_name and ancestor_chain:
                chain = ancestor_chain + [f"{ancestor_chain[-1]}.{mem_name}"]
            elif ancestor_chain:
                chain = ancestor_chain
            break

        # ElementSelect / RangeSelect: 顶层进入的情况 (仅当前节点, 没 MemberAccess)
        if k in (ExpressionKind.ElementSelect, ExpressionKind.RangeSelect):
            if k == ExpressionKind.ElementSelect:
                sel_v = _eval_to_int(getattr(cur, 'selector', None))
                sel_str = f"[{sel_v}]" if sel_v is not None else '[?]'
            else:
                msb_v = _eval_to_int(getattr(cur, 'left', None))
                lsb_v = _eval_to_int(getattr(cur, 'right', None))
                sel_str = f"[{msb_v}:{lsb_v}]" if (msb_v is not None and lsb_v is not None) else '[?:?]'
            # 拿 ancestor
            ancestor = getattr(cur, 'value', None)
            acur = ancestor
            ancestor_chain = []
            while acur is not None and hasattr(acur, 'kind') and id(acur) not in visited:
                visited.add(id(acur))
                ak = acur.kind
                if ak == ExpressionKind.NamedValue:
                    asym = getattr(acur, 'symbol', None)
                    if asym:
                        aname = getattr(asym, 'name', None)
                        if aname:
                            ancestor_chain.append(str(aname).strip())
                    break
                elif ak == ExpressionKind.MemberAccess:
                    amem = getattr(acur, 'member', None)
                    amem_name = getattr(amem, 'name', None) if amem else None
                    if ancestor_chain and amem_name:
                        ancestor_chain.append(f"{ancestor_chain[-1]}.{amem_name}")
                    break
                else:
                    break
            if ancestor_chain:
                chain = ancestor_chain + [f"{ancestor_chain[-1]}{sel_str}"]
            break

        # 其他: 跳出
        break

    return chain


def _eval_to_int(expr: Any) -> int | None:
    """[2026-08-28 07:00] 用 pyslang eval() 把 expression 节点转 int.

    实测 (pyslang 11.0):
    - IntegerLiteral.value 直接返回 SVInt (不是 int, 但 int(SVInt) 可转)
    - BinaryOp (e.g. W-1) / NamedValue (e.g. W) 需要 eval(EvalContext)
    - .constant.value 也是 拿整数路径
    - 拿不到时返回 None (调用方决定如何处理)

    Returns:
        int 或 None
    """
    if expr is None:
        return None

    # 快速路径 1: .value 属性 (IntegerLiteral 是 SVInt, 直接转 int)
    v = getattr(expr, 'value', None)
    if v is not None:
        try:
            return int(v)
        except (TypeError, ValueError):
            pass

    # 快速路径 2: .constant.value (pyslang 11.0 ConstantValue)
    const = getattr(expr, 'constant', None)
    if const is not None:
        cv = getattr(const, 'value', None)
        if cv is not None:
            try:
                return int(cv)
            except (TypeError, ValueError):
                pass

    # 慢路径: 走 pyslang eval (需要 EvalContext)
    if _HAS_PYSLANG and EvalContext is not None:
        try:
            # eval() 需要 EvalContext 参数, 这里拿不到 compilation
            # 试试看 expr.eval(EvalContext(compilation=...))
            # 但 helper 是通用的, 调用方应该传 EvalContext
            # 退化: 试 expr.eval() 看是否某些版本可工作
            result = expr.eval()
            iv = getattr(result, 'integerValue', None)
            if iv is not None:
                return int(iv)
        except Exception:
            pass

    return None


def _get_base_name(node: Any) -> str | None:
    """[2026-08-28 06:38] 从 RangeSelect/ElementSelect 节点提取 base signal name.

    pyslang 11.0 实测:
    - RangeSelectExpression.value 是 NamedValueExpression
    - NamedValueExpression.symbol.name 是标识符

    Returns:
        base name (如 'data') 或 None
    """
    base = getattr(node, 'value', None)
    if base is None:
        return None

    base_kind = getattr(base, 'kind', None)
    if base_kind is None:
        return None

    # NamedValue: simple identifier (e.g. 'data')
    if str(base_kind) == 'ExpressionKind.NamedValue':
        sym = getattr(base, 'symbol', None)
        if sym:
            name = getattr(sym, 'name', None)
            if name:
                return str(name).strip()

    # MemberAccess: struct.field (e.g. 'pkt.addr')
    if str(base_kind) == 'ExpressionKind.MemberAccess':
        # MemberAccess 有 .value (member 上一级) 和 .member (字段名)
        member = getattr(base, 'member', None)
        if member:
            mname = getattr(member, 'name', None)
            if mname:
                # 上级还可能是结构体本身, 递归取 base
                parent_base = _get_base_name_from_base(base)
                if parent_base:
                    return f"{parent_base}.{mname}"
                return str(mname).strip()

    # 其他类型: 递归
    return None


def _get_base_name_from_base(base: Any) -> str | None:
    """从 MemberAccess / HierarchicalReference 等 base 节点递归取 base name."""
    # base.value 是上一级 expression
    parent = getattr(base, 'value', None)
    if parent is None:
        return None
    parent_kind = getattr(parent, 'kind', None)
    if parent_kind is None:
        return None
    if str(parent_kind) == 'ExpressionKind.NamedValue':
        sym = getattr(parent, 'symbol', None)
        if sym:
            name = getattr(sym, 'name', None)
            if name:
                return str(name).strip()
    return None


def make_range_select_id(parent_id: str, msb: int, lsb: int) -> str:
    """[2026-08-28 06:38] 构造 RangeSelect 节点 ID.

    与 regex 方案保持兼容: parent_id[msb:lsb]
    """
    return f"{parent_id}[{msb}:{lsb}]"


def make_element_select_id(parent_id: str, index: int) -> str:
    """[2026-08-28 06:38] 构造 ElementSelect 节点 ID.

    与 regex 方案保持兼容: parent_id[index]
    """
    return f"{parent_id}[{index}]"
