# connections.py — SemanticAdapter 的 connections 域 mixin (iter_176 分域搬迁)
#
# 方法名/签名与原 SemanticAdapter 完全一致 (API 面冻结测试锁定);
# `self` 即 SemanticAdapter 实例 (状态: _root/_compiler/_target_module/
# _fixed_names/_genvar_context/_spec_members 等), 无独立状态。
"""connections 域: 实例连接/表达式→信号名/索引求值"""
import logging
from typing import Callable, Iterator

import pyslang

from ..._safe import _safe_attr, _safe_str, clean_name, safe_attr, safe_str
from ..ast_utils import is_syntax_list, iter_syntax_list

logger = logging.getLogger(__name__)


class ConnectionsMixin:
    """connections 域方法集 (mixin — 由 SemanticAdapter 组合)"""

    def _eval_select_index(self, sel, gidx: int | None) -> int | None:
        """[iter_109] 位选/元素选索引求值 (generate-for 连接表达式).

        支持: Literal (常量) / Conversion (解包) / NamedValue (generate entry 内
        视为 loop var → gidx) / BinaryOp (+/- 折叠). 求不出返回 None (调用方
        落 '?' 占位, 不静默丢连接).
        """
        if sel is None:
            return None
        k = str(getattr(sel, "kind", ""))
        try:
            if "Literal" in k:
                # pyslang IntegerLiteral: str() 是类名, 数值在 .value (SVInt)
                _v = getattr(sel, "value", None)
                if _v is not None:
                    try:
                        return int(str(_v))
                    except (ValueError, TypeError):
                        return None
                try:
                    return int(str(sel))
                except (ValueError, TypeError):
                    return None
            if "Conversion" in k:
                for _a in ("operand", "value", "inner", "expr"):
                    _v = getattr(sel, _a, None)
                    if _v is not None:
                        return self._eval_select_index(_v, gidx)
                return None
            if "NamedValue" in k:
                # generate entry 内 NamedValue selector 视为 loop var → gidx
                return gidx
            if "BinaryOp" in k:
                l = self._eval_select_index(getattr(sel, "left", None), gidx)
                r = self._eval_select_index(getattr(sel, "right", None), gidx)
                if l is None or r is None:
                    return None
                op = str(getattr(sel, "op", ""))
                if "Add" in op or "+" in op:
                    return l + r
                if "Sub" in op or "-" in op:
                    return l - r
                if "Mul" in op or "*" in op:
                    return l * r
            return None
        except Exception:
            return None



    def _conn_expr_to_signal(self, expr, instance) -> str | None:
        """[iter_109] 解开实例端口连接表达式 → 信号名 (含数组元素/位选).

        处理: NamedValue (直接信号名) / ElementSelect·RangeSelect (base[sel]).
        ElementSelect 的 selector 若是 genvar NamedValue ('i'), 用实例 hp 的
        generate entry 索引替换 (arr[i] → arr[2]); 非 genvar/无法解析 → '?' 占位
        (保持图节点存在, 不静默丢连接).
        """
        if expr is None:
            return None
        k = str(getattr(expr, "kind", ""))
        try:
            if "RangeSelect" in k:
                # [iter_119] semantic RangeSelectExpression: left/right 在 expr 上
                # (无 .selector), selectionKind 区分 +: (IndexedUp) / -: (IndexedDown)
                # / 普通 [msb:lsb] (Simple). iter_118 S2 四级嵌套 .a(a[i*4+:4]) /
                # .y(y[j*2+:2]) 因此恒 '?' 占位 — 逐界 _eval_select_index 求值,
                # +:/ -: 换算成 [hi:lo] (msb:lsb) 命名。
                val = getattr(expr, "value", None)
                base = None
                if val is not None and hasattr(val, "symbol") and val.symbol is not None:
                    try:
                        base = str(val.symbol.name)
                    except (UnicodeDecodeError, TypeError):
                        base = None
                if base is None:
                    base = self._conn_expr_to_signal(val, instance)
                if base is None:
                    return None
                _gi = self._genvar_index_from_hp(instance)
                a = self._eval_select_index(getattr(expr, "left", None), _gi)
                b = self._eval_select_index(getattr(expr, "right", None), _gi)
                if a is None or b is None:
                    return f"{base}[?]"
                selkind = str(getattr(expr, "selectionKind", ""))
                if "IndexedUp" in selkind:
                    # [base+:width] → 位 [base+width-1 : base]
                    hi, lo = a + b - 1, a
                elif "IndexedDown" in selkind:
                    # [base-:width] → 位 [base : base-width+1]
                    hi, lo = a, a - b + 1
                else:
                    hi, lo = max(a, b), min(a, b)
                return f"{base}[{hi}:{lo}]"
            if "ElementSelect" in k:
                val = getattr(expr, "value", None)
                sel = getattr(expr, "selector", None)
                # base: value 的 symbol 名 (也可能是嵌套 select → 递归)
                base = None
                if val is not None and hasattr(val, "symbol") and val.symbol is not None:
                    try:
                        base = str(val.symbol.name)
                    except (UnicodeDecodeError, TypeError):
                        base = None
                if base is None:
                    base = self._conn_expr_to_signal(val, instance)
                if base is None:
                    return None
                # selector → 索引文本 (支持 genvar i / i±k / 常量; 解析失败 → '?')
                idx = "?"
                if sel is not None:
                    _gi = self._genvar_index_from_hp(instance)
                    _val = self._eval_select_index(sel, _gi)
                    if _val is not None:
                        idx = str(_val)
                return f"{base}[{idx}]"
            # NamedValue / Identifier: 直接信号名
            if "NamedValue" in k or "Identifier" in k:
                if hasattr(expr, "symbol") and expr.symbol is not None:
                    try:
                        return str(expr.symbol.name)
                    except (UnicodeDecodeError, TypeError):
                        return None
            return None
        except Exception:
            return None



    def get_instance_connection(self, instance) -> list:
        """获取实例的端口连接

        Semantic AST: 从 InstanceSymbol.portConnections 获取
        Returns:
            [(port_name, signal_name), ...]
        """
        connections = []

        # 如果是包装器,从 _symbol 获取
        if hasattr(instance, "_symbol"):
            inst_sym = instance._symbol
        else:
            inst_sym = instance

        # [D5] v11 InstanceSymbol always has portConnections
        for conn in inst_sym.portConnections:
            # port 属性有 name
            port_name = "?"
            if hasattr(conn, "port"):
                try:
                    port_name = str(conn.port.name)
                except (UnicodeDecodeError, TypeError):
                    port_name = "<id:non-utf8>"

            # expression 是 NamedValue,其 symbol 是信号
            # 也可能是 Assignment 表达式 (用于 output 端口连接，如 .q(signal))
            signal_name = "?"
            if hasattr(conn, "expression") and hasattr(conn.expression, "symbol"):
                # NamedValue expression
                try:
                    signal_name = str(conn.expression.symbol.name)
                except (UnicodeDecodeError, TypeError):
                    signal_name = "<id:non-utf8>"
            elif hasattr(conn, "expression"):
                expr = conn.expression
                # Check if it's an Assignment expression (output port connection)
                expr_kind = str(getattr(expr, "kind", ""))
                if "Assignment" in expr_kind:
                    # For Assignment expression (.q(signal)), signal is in left side
                    left = getattr(expr, "left", None)
                    if left:
                        # [iter_109] left 可能是 ElementSelect (如 .xo(arr[i+1])) —
                        # 原有 left.symbol 直接取 base 名会丢索引且 ElementSelect 无 symbol.
                        sig = self._conn_expr_to_signal(left, instance)
                        if sig:
                            signal_name = sig
                        elif hasattr(left, "symbol"):
                            try:
                                signal_name = str(left.symbol.name)
                            except (UnicodeDecodeError, TypeError):
                                signal_name = "<id:non-utf8>"
                # [iter_109] 顶层 ElementSelect/RangeSelect (如 .x(arr[i])):
                # 之前未处理 → signal_name 停留 "?" → 整条 conn 被丢 (generate-for
                # 数组元素实例连接全灭, verilog_cordic_core 暴露).
                elif "ElementSelect" in expr_kind or "RangeSelect" in expr_kind:
                    sig = self._conn_expr_to_signal(expr, instance)
                    if sig:
                        signal_name = sig
                # [iter_136] Conversion 壳 (端口位宽 ≠ 连接位宽 / 类型转换时,
                # pyslang 给 input 表达式包 Conversion, operand 才是真表达式):
                # 不剥壳 → signal_name 停留 "?" → 整条 conn 静默丢 (无 warning,
                # 违反 AGENTS.md §2) — iter_119 观察真身: leafm `input a` 1 位接
                # a[j*2+:2] 2 位切片, 嵌套 fixture 4/4 input 连接全缺, fanin 断
                # 在 u_leaf.a。output 侧是 Assignment(left=RangeSelect) 不受影响。
                elif "Conversion" in expr_kind:
                    operand = getattr(expr, "operand", None)
                    # 链式剥壳 (防 Conversion(Conversion(...)))
                    while (operand is not None
                           and "Conversion" in str(getattr(operand, "kind", ""))):
                        operand = getattr(operand, "operand", None)
                    if operand is not None:
                        sig = self._conn_expr_to_signal(operand, instance)
                        if sig:
                            signal_name = sig
                # [V15.2 2026-08-13] 方向 A: pyslang semantic AST 处理 ConcatenationExpression
                # 当 .port(expr) 的 expr 是 {a, b, c} 时, 原逻辑 (NamedValue/Assignment)
                # 不命中 → 整条 conn 被丢弃. 现在走 semantic AST 的 ConcatenationExpression.operands,
                # 每个 operand emit 一条 (port_name, signal_name) conn.
                # 例: .din({3'b0, offsetted}) → ('din', 'offsetted') (跳过 IntegerLiteral const)
                #     让 connection_extractor 生成 offsetted → u_clamp_u.din 跨实例连线
                elif "Concatenation" in expr_kind and hasattr(expr, "operands"):
                    for operand in expr.operands:
                        op_kind_str = str(getattr(operand, "kind", ""))
                        # 跳过 const literals (IntegerLiteral, RealLiteral, etc.)
                        if "Literal" in op_kind_str:
                            continue
                        # NamedValueExpression: operand.symbol.name
                        if hasattr(operand, "symbol") and operand.symbol is not None:
                            try:
                                connections.append((port_name, str(operand.symbol.name)))
                                continue
                            except (UnicodeDecodeError, TypeError) as e:
                                logger.warning("提取失败: %s", e)
                        # ElementSelect / RangeSelect (e.g. din[7:0]):
                        # operand.expr 是 inner NamedValue
                        inner = getattr(operand, "expr", None)
                        if inner is not None and hasattr(inner, "symbol") and inner.symbol is not None:
                            try:
                                connections.append((port_name, str(inner.symbol.name)))
                            except (UnicodeDecodeError, TypeError) as e:
                                logger.warning("提取失败: %s", e)

            if port_name != "?" and signal_name != "?":
                connections.append((port_name, signal_name))

        return connections

    # =========================================================================
    # 端口相关
    # =========================================================================



    def get_signal_name(self, signal) -> str:
        """获取信号名称

        DataDeclaration: signal.declarators[0].name.value
        VariableSymbol: signal.name
        """
        # Handle DataDeclaration (syntax tree)
        if hasattr(signal, "declarators"):
            decls = signal.declarators
            if hasattr(decls, "__iter__") and not isinstance(decls, str):
                decl_list = list(decls)
                if decl_list:
                    first_decl = decl_list[0]
                    name = _safe_attr(first_decl, "name", None)
                    if name:
                        # [Bug-fix 2026-06-13] safe_str() 防 binary garbage
                        return _safe_str(name)
                    # [Bug-fix 2026-06-25] name is None (declarator name 解析失败),
                    # 返 f-string 避免 'cannot access local variable' UnboundLocalError.
                    # Vortex.sv 触发 (partial AST).
                    loc = getattr(first_decl, "location", None)
                    if loc is not None:
                        return f"<id@{getattr(loc, 'line', '?')}:{getattr(loc, 'column', '?')}>"
                    return "<id:unknown>"
                # decl_list 为空 (e.g. empty struct)
                return "<id:empty-decl>"
            elif hasattr(decls, "name"):
                try:
                    return str(decls.name)
                except (UnicodeDecodeError, TypeError):
                    return "<id:non-utf8>"

        # Handle VariableSymbol (semantic AST)
        if hasattr(signal, "name"):
            try:
                return str(signal.name)
            except (UnicodeDecodeError, TypeError):
                return "<id:non-utf8>"
        return "unknown"
