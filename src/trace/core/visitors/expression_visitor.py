"""[ADD 2026-06-26 A-PR5] Expression visitor mixin for SignalExpressionVisitor.

[REFACTOR A-PR5 2026-06-26] 抽 1 @on handler (VariableDimension) + 49 visit_*/get_all_*
helper method (1024 行) 到独立 mixin.

主 class SignalExpressionVisitor 多继承此 mixin, 改 1 行平均 5 min → 30s.

内容:
- @on handler: VariableDimension (处理 bit/range select)
- visit_*: visit_scoped_name, visit_integer_literal, visit_member_access 等
  (legacy visit pattern, 跟 @on handler 并列, 内部用)
- get_all_*: get_all_conditional_op, get_all_concatenation 等
  (helper for visitor pattern)
- _helper: _get_param_map, _evaluate_expr, _is_literal 等
  (内部 helper, 跟前面互调)

Total: 53 method (1024 行)
"""
from typing import TYPE_CHECKING, Any

from ._decorators import on
from .signal_result import SignalResult

if TYPE_CHECKING:
    from .signal_expression_visitor import SignalExpressionVisitor


class ExpressionVisitor:
    """[ADD 2026-06-26 A-PR5] 抽 VariableDimension + visit_*/get_all_*/_helper method
    到独立 mixin.

    主 class SignalExpressionVisitor 多继承此 mixin, 行为不变.
    """

    @on("VariableDimension")
    def extract_variable_dimension(self, node) -> SignalResult:
        """[NOT TESTED] VariableDimension: variable dimension"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    def visit_scoped_name(self, node) -> str | None:
        """ScopedName: 点分路径

        结构: p.sub.data -> ScopedName(ScopedName(p, sub), data)
        """
        # DEAD CODE: migrated to @on handler - kept for reference only
        parts = self._extract_scoped_parts(node)
        if len(parts) >= 2:
            combined = ".".join(parts)
            return self.adapter.clean_name(combined)
        elif len(parts) == 1:
            return parts[0]
        return None

    def _extract_scoped_parts(self, node, parts=None) -> list[str]:
        """递归提取 ScopedName 的各部分

        Args:
            node: ScopedName AST 节点
            parts: 累积的部分列表

        Returns:
            点分路径的各部分
        """
        if parts is None:
            parts = []

        kind = getattr(node, "kind", None)
        if not kind:
            return parts

        kind_str = str(kind)

        if "ScopedName" in kind_str:
            left = getattr(node, "left", None)
            if left:
                self._extract_scoped_parts(left, parts)
            right = getattr(node, "right", None)
            if right:
                ri = getattr(right, "identifier", None)
                if ri:
                    rv = getattr(ri, "value", None)
                    if rv:
                        parts.append(str(rv).strip())
        elif "IdentifierName" in kind_str:
            ident = getattr(node, "identifier", None)
            if ident:
                # [FIX 2026-06-26] use _safe_str
                val = self._safe_str(getattr(ident, "value", None)).strip()
                if val:
                    parts.append(val)

        return parts

    # =========================================================================
    # [P0] 字面量 - 必须实现
    # =========================================================================

    def visit_integer_literal(self, node) -> str | None:
        """IntegerLiteral: 简单整数字面量 0, 1, 255 等"""
        val = getattr(node, "value", None)
        if val is not None:
            return str(val).strip()
        return str(node).strip()

    def visit_integer_vector(self, node) -> str | None:
        """IntegerVectorExpression: 带位宽的字面量 8'hAA, 16'd123"""
        import pyslang

        val = getattr(node, "value", None)
        if isinstance(val, pyslang.Token) and val.kind == pyslang.TokenKind.IntegerLiteral:
            return str(node).strip()
        return str(node).strip()

    # =========================================================================
    # [P1] 位选择 - 常用，必须实现
    # =========================================================================

    def visit_element_select(self, node) -> str | None:
        """ElementSelect: 位选择 data[5]

        结构: ElementSelect.value = data, selector = 5
        """
        # DEAD CODE: migrated to @on handler - kept for reference only
        value = getattr(node, "value", None)
        selector = getattr(node, "selector", None)

        if value and selector is not None:
            base_name = None
            if hasattr(value, "symbol"):
                sym = value.symbol
                # [Bug-fix 2026-06-13] sym.name 访问可能 raise UnicodeDecodeError
                # (pyslang elaboration 失败时), 整体 try/except 降级
                try:
                    if hasattr(sym, "name"):
                        base_name = self._safe_str(sym.name)
                except (UnicodeDecodeError, TypeError):
                    base_name = None

            if base_name:
                selector_val = getattr(selector, "value", None)
                if selector_val is not None:
                    return f"{base_name}[{selector_val}]"

        # 兜底: 递归获取基础信号
        if value:
            base = self.visit(value)
            if base:
                return base
        return None

    def visit_range_select(self, node) -> str | None:
        """RangeSelect: 范围选择 data[3:0]

        结构: RangeSelect.value = data, left = 3, right = 0
        """
        value = getattr(node, "value", None)
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)

        if value and left is not None and right is not None:
            base_signals = self.get_all_signals(value)
            if base_signals:
                base_name = base_signals[0]
                left_val = getattr(left, "value", None)
                right_val = getattr(right, "value", None)
                if left_val is not None and right_val is not None:
                    return f"{base_name}[{left_val}:{right_val}]"

        # 兜底
        if value:
            return self.visit(value)
        return None

    # =========================================================================
    # [P1] 表达式类型
    # =========================================================================

    def visit_conversion(self, node) -> str | None:
        """Conversion: 隐式类型转换

        例如: assign dout = data[5]; data[5] 是 ElementSelect,外面包了一层 Conversion
        """
        operand = getattr(node, "operand", None)
        if operand:
            return self.visit(operand)
        return None

    def visit_member_access(self, node) -> str | None:
        """MemberAccessExpression: class 成员访问 p.addr

        结构: member = p, member_sym = addr
        """
        # DEAD CODE: migrated to @on handler - kept for reference only
        value = getattr(node, "value", None) or getattr(node, "expression", None)
        member_sym = getattr(node, "member", None)

        if value and member_sym:
            base_name = self.visit(value)
            member_name = self._safe_get_name(member_sym, None)
            if member_name:
                member_name = self._safe_str(member_name).strip()
            else:
                member_name = self._safe_str(member_sym).strip()

            if base_name and member_name:
                return f"{base_name}.{member_name}"
        return None

    def visit_binary_expression(self, node) -> str | None:
        """BinaryExpression: 二元表达式 a + b, a & b 等

        默认返回左操作数
        """
        left = getattr(node, "left", None)
        if left:
            return self.visit(left)
        return None

    def visit_call(self, node) -> str | None:
        """Call/InvocationExpression: 函数调用

        结构: InvocationExpression.left = IdentifierName (函数名)
        """
        left = getattr(node, "left", None)
        if left:
            identifier = getattr(left, "identifier", None)
            if identifier:
                val = getattr(identifier, "value", None)
                if val:
                    return str(val).strip()
            return str(left).strip()
        return None

    def visit_parenthesized(self, node) -> str | None:
        """ParenthesizedExpression: (expr)"""
        expr = getattr(node, "expression", None)
        if expr:
            return self.visit(expr)
        return None

    def visit_unary(self, node) -> str | None:
        """UnaryExpression: ~a, -a, !a 等"""
        operand = getattr(node, "operand", None) or getattr(node, "expression", None)
        if operand:
            return self.visit(operand)
        return None

    # =========================================================================
    # [P1] 复合表达式 - 返回多个信号
    # =========================================================================

    def get_all_conditional_op(self, node) -> list[str]:
        """ConditionalOp: 三元运算符 sel ? a : b

        返回: [sel, a, b]
        """
        signals = []

        # predicate (condition)
        conditions = getattr(node, "conditions", None)
        if conditions and len(conditions) > 0:
            cond_expr = getattr(conditions[0], "expr", None)
            if cond_expr:
                signals.extend(self.get_all_signals(cond_expr))

        # Also try .predicate for compatibility
        pred = getattr(node, "predicate", None)
        if pred:
            signals.extend(self.get_all_signals(pred))

        # left (true branch)
        left = getattr(node, "left", None)
        if left:
            signals.extend(self.get_all_signals(left))

        # right (false branch)
        right = getattr(node, "right", None)
        if right:
            signals.extend(self.get_all_signals(right))

        return [s for s in signals if s]

    def get_signals_with_conditions(self, node, parent_conditions: list[str] = None) -> list[tuple[str, str]]:
        """提取三元运算符中的信号及其对应条件

        对于嵌套三元 `sel ? a : b ? c : d`:
        - sel 为真时: a 的条件是 sel
        - sel 为假且 b 为真时: c 的条件是 !sel && b
        - sel 为假且 b 为假时: d 的条件是 !sel && !b

        Args:
            node: AST 节点（可能是 ConditionalOp 或其他表达式）
            parent_conditions: 父级条件列表（用于组合嵌套条件）

        Returns:
            List[Tuple[str, str]]: [(signal_name, condition_str), ...]
        """
        if parent_conditions is None:
            parent_conditions = []

        if node is None:
            return []

        kind = getattr(node, "kind", None)
        if kind is None:
            return []

        kind_name = kind.name if hasattr(kind, "name") else str(kind)

        # [FIX] 别名处理: ConditionalExpression (Syntax AST) = ConditionalOp (Semantic AST)
        check_kind = kind_name
        if "ConditionalExpression" in kind_name and "ConditionalOp" not in kind_name:
            check_kind = "ConditionalOp"  # Treat ConditionalExpression as ConditionalOp

        # [FIX] 解包 ConversionExpression / Conversion
        if "Conversion" in kind_name:
            operand = getattr(node, "operand", None)
            if operand:
                return self.get_signals_with_conditions(operand, parent_conditions)

        # ConditionalOp: 三元运算符
        if "ConditionalOp" in check_kind:
            result = []

            # 提取当前层级的条件
            conditions = getattr(node, "conditions", None)
            current_cond = None
            if conditions and len(conditions) > 0:
                cond_expr = getattr(conditions[0], "expr", None)
                if cond_expr:
                    current_cond = self._expr_to_string(cond_expr)
                    # 条件信号本身也应作为驱动源返回（条件总是被检查的）
                    cond_signals = self.get_all_signals(cond_expr)
                    for sig in cond_signals:
                        if sig and not self._is_literal(sig):
                            result.append((sig, ""))

            if not current_cond:
                # 尝试 predicate
                pred = getattr(node, "predicate", None)
                if pred:
                    current_cond = self._expr_to_string(pred)
                    cond_signals = self.get_all_signals(pred)
                    for sig in cond_signals:
                        if sig and not self._is_literal(sig):
                            result.append((sig, ""))

            # True 分支 (left)
            left = getattr(node, "left", None)
            if left:
                # 检查 left 是否也是 ConditionalOp（嵌套情况）
                left_kind = getattr(left, "kind", None)
                left_kind_name = left_kind.name if hasattr(left_kind, "name") else str(left_kind) if left_kind else ""
                # [FIX] 使用与 kind_name 相同的别名处理
                if "ConditionalExpression" in left_kind_name and "ConditionalOp" not in left_kind_name:
                    left_kind_name = "ConditionalOp"  # Treat ConditionalExpression as ConditionalOp

                if "ConditionalOp" in left_kind_name:
                    # 嵌套三元: 传递当前条件作为父条件
                    true_conds = parent_conditions + [current_cond] if current_cond else parent_conditions
                    result.extend(self.get_signals_with_conditions(left, true_conds))
                else:
                    # 叶子节点: 提取信号并组合条件
                    left_signals = self.get_all_signals(left)
                    for sig in left_signals:
                        cond_str = (
                            " && ".join(parent_conditions + [current_cond])
                            if current_cond
                            else " && ".join(parent_conditions)
                        )
                        result.append((sig, cond_str))

            # False 分支 (right)
            right = getattr(node, "right", None)
            if right:
                right_kind = getattr(right, "kind", None)
                right_kind_name = (
                    right_kind.name if hasattr(right_kind, "name") else str(right_kind) if right_kind else ""
                )
                # [FIX] 使用与 kind_name 相同的别名处理
                if "ConditionalExpression" in right_kind_name and "ConditionalOp" not in right_kind_name:
                    right_kind_name = "ConditionalOp"  # Treat ConditionalExpression as ConditionalOp

                if "ConditionalOp" in right_kind_name:
                    # 嵌套三元: 条件取反后传递
                    if current_cond:
                        negated_cond = f"!({current_cond})"
                    else:
                        negated_cond = None
                    false_conds = parent_conditions + [negated_cond] if negated_cond else parent_conditions
                    result.extend(self.get_signals_with_conditions(right, false_conds))
                else:
                    # 叶子节点
                    right_signals = self.get_all_signals(right)
                    for sig in right_signals:
                        if current_cond:
                            negated_cond = f"!({current_cond})"
                            cond_str = " && ".join(parent_conditions + [negated_cond])
                        else:
                            cond_str = " && ".join(parent_conditions)
                        result.append((sig, cond_str))

            return result

        # 非三元表达式: 直接提取信号（条件为空）
        signals = self.get_all_signals(node)
        return [(sig, "") for sig in signals]

    def _expr_to_string(self, expr) -> str:
        """将表达式转换为可读字符串（用于条件显示）"""
        if expr is None:
            return ""

        kind = getattr(expr, "kind", None)
        if kind:
            kind_name = kind.name if hasattr(kind, "name") else str(kind)

            # BinaryExpression: a == b, a + b, etc.
            if "BinaryOp" in kind_name or "Binary" in kind_name:
                left = self._expr_to_string(getattr(expr, "left", None))
                right = self._expr_to_string(getattr(expr, "right", None))
                op = getattr(expr, "op", None) or getattr(expr, "operator", None)
                if op:
                    if hasattr(op, "name"):
                        op_name = op.name
                        # [FIX] 将操作符名称转换为标准符号
                        op_map = {
                            "Equality": "==",
                            "Inequality": "!=",
                            "LessThan": "<",
                            "LessEqual": "<=",
                            "GreaterThan": ">",
                            "GreaterEqual": ">=",
                            "LogicalAnd": "&&",
                            "LogicalOr": "||",
                            "BinaryAnd": "&",
                            "BinaryOr": "|",
                            "BinaryXor": "^",
                            "BinaryXnor": "~^",
                            "Add": "+",
                            "Subtract": "-",
                            "Multiply": "*",
                            "Divide": "/",
                            "Mod": "%",
                        }
                        op_str = op_map.get(op_name, f" {op_name.lower()} ")
                    else:
                        op_str = f" {str(op).strip()} "
                else:
                    op_str = " "
                return f"{left}{op_str}{right}"

            # [FIX] ConversionExpression: 递归解包获取底层表达式
            # 例如 2'b00 可能是 ConversionExpression，需要解包
            if "Conversion" in kind_name:
                operand = getattr(expr, "operand", None)
                if operand:
                    return self._expr_to_string(operand)

            # [FIX] ParenthesizedExpression: 递归解包获取内部表达式
            if "Parenthesized" in kind_name:
                inner = getattr(expr, "expression", None)
                if inner:
                    return f"({self._expr_to_string(inner)})"

            # [FIX] RangeSelect (Syntax AST): addr[5], wdata[7:0] 等位选/范围选择
            # Semantic AST RangeSelectExpression: .value = base signal, .left/.right = bounds
            # 也支持 .syntax (原始语法节点)
            if "Range" in kind_name or "ElementSelect" in kind_name:
                # Try value (Semantic AST)
                value = getattr(expr, "value", None)
                if value:
                    base_str = self._expr_to_string(value)
                else:
                    # Try syntax for base
                    syntax_node = getattr(expr, "syntax", None)
                    if syntax_node:
                        base_str = str(syntax_node).strip()
                    else:
                        base_str = str(expr).strip()

                # Get range/selection if present
                left = getattr(expr, "left", None)
                right = getattr(expr, "right", None)
                selector = getattr(expr, "selector", None) or getattr(expr, "select", None)

                if selector:
                    selector_str = self._expr_to_string(selector)
                    return f"{base_str}[{selector_str}]"
                elif left is not None and right is not None:
                    left_str = self._expr_to_string(left)
                    right_str = self._expr_to_string(right)
                    return f"{base_str}[{left_str}:{right_str}]"
                return base_str

            # [FIX] EqualityExpression / SimpleBinaryExpression (syntax): a == b, a + b
            if "Equality" in kind_name or "Binary" in kind_name:
                left = self._expr_to_string(getattr(expr, "left", None))
                right = self._expr_to_string(getattr(expr, "right", None))
                op = getattr(expr, "op", None) or getattr(expr, "operator", None)
                if op:
                    if hasattr(op, "name"):
                        op_str = f" {op.name.lower()} "
                    else:
                        op_str = f" {str(op).strip()} "
                else:
                    op_str = " "
                return f"{left}{op_str}{right}"

            # NamedValueExpression
            if hasattr(expr, "symbol"):
                sym = getattr(expr, "symbol", None)
                if sym:
                    try:
                        _name = sym.name
                    except (UnicodeDecodeError, TypeError, Exception):
                        _name = None
                    if _name:
                        return self._safe_str(_name).strip()

            # IdentifierNameSyntax
            if "IdentifierName" in kind_name:
                return str(expr).strip()

            # IntegerLiteralExpression (Semantic AST)
            if kind_name == "IntegerLiteral":
                # IntegerLiteral has .value attribute with the actual value like "2'b0"
                if hasattr(expr, "value"):
                    return str(expr.value)
                return str(expr).strip()

            # IntegerLiteralExpression (syntax)
            if "IntegerLiteral" in kind_name or "IntegerVector" in kind_name:
                return str(expr).strip()

        # 通用字符串转换
        return str(expr).strip()

    def get_all_concatenation(self, node) -> list[str]:
        """ConcatenationExpression: {a, b, c}

        返回: [a, b, c]
        """
        signals = []
        operands = getattr(node, "operands", None) or getattr(node, "expressions", None)

        if operands:
            for expr in operands:
                expr_kind = getattr(expr, "kind", None)
                if expr_kind and "Token" not in str(expr_kind):
                    signals.extend(self.get_all_signals(expr))

        return [s for s in signals if s]
    def get_all_range_select(self, node) -> list[str]:
        """RangeSelect: 范围选择

        返回: [base[left:right]]
        """
        result = self.visit(node)
        return [result] if result else []

    # =========================================================================
    # [P2] 特殊类型
    # =========================================================================

    def visit_identifier_select(self, node) -> str | None:
        """IdentifierSelect: data[3] 等带位选的标识符

        结构: identifier.value = "data", selectors = [ElementSelect]
        """
        base_name = None
        if hasattr(node, "identifier"):
            ident = node.identifier
            if hasattr(ident, "value"):
                base_name = str(ident.value).strip()
            else:
                base_name = str(ident).strip()

        if not base_name:
            base_name = str(node).strip().split("[")[0]

        # 获取位选索引
        selectors = getattr(node, "selectors", None)
        if selectors and hasattr(selectors, "__iter__"):
            for i in range(len(selectors)):
                sel = selectors[i]
                sel_kind = str(getattr(sel, "kind", ""))

                if "ElementSelect" in sel_kind:
                    bit_select = getattr(sel, "selector", None)
                    if bit_select:
                        bit_select_kind = str(getattr(bit_select, "kind", ""))

                        if "SimpleRange" in bit_select_kind:
                            # 范围选择
                            left_expr = getattr(bit_select, "left", None)
                            right_expr = getattr(bit_select, "right", None)

                            param_map = self._get_param_map()
                            left_val = self._evaluate_expr(left_expr, param_map) if left_expr else None
                            right_val = self._evaluate_expr(right_expr, param_map) if right_expr else None

                            if left_val is not None or right_val is not None:
                                left_str = str(left_val) if left_val is not None else "?"
                                right_str = str(right_val) if right_val is not None else "?"
                                return self.adapter.clean_name(f"{base_name}[{left_str}:{right_str}]")
                        else:
                            # 单位选择
                            selector_expr = getattr(bit_select, "expr", None)
                            if selector_expr:
                                param_map = self._get_param_map()
                                evaluated = self._evaluate_expr(selector_expr, param_map)
                                if evaluated is not None:
                                    return self.adapter.clean_name(f"{base_name}[{evaluated}]")

                elif "SimpleRangeSelect" in sel_kind:
                    range_sel = getattr(sel, "selector", None) or sel
                    left_expr = getattr(range_sel, "left", None)
                    right_expr = getattr(range_sel, "right", None)

                    if left_expr or right_expr:
                        param_map = self._get_param_map()
                        left_val = self._evaluate_expr(left_expr, param_map) if left_expr else None
                        right_val = self._evaluate_expr(right_expr, param_map) if right_expr else None

                        if left_val is not None or right_val is not None:
                            left_str = str(left_val) if left_val is not None else "?"
                            right_str = str(right_val) if right_val is not None else "?"
                            return self.adapter.clean_name(f"{base_name}[{left_str}:{right_str}]")

        return self.adapter.clean_name(base_name) if base_name else None

    def visit_hierarchical_value(self, node) -> str | None:
        """HierarchicalValueExpression: ifc.data (interface 成员访问)

        结构: HierarchicalValueExpression.syntax = ScopedNameSyntax
        """
        syntax = getattr(node, "syntax", None)
        if syntax and hasattr(syntax, "kind"):
            kind_str = str(syntax.kind)
            if "ScopedName" in kind_str:
                return self.visit_scoped_name(syntax)
        return None

    def visit_replication(self, node) -> str | None:
        """ReplicationExpression: {N{signal}}

        结构: ReplicationExpression.concat = ConcatenationExpression
        """
        concat = getattr(node, "concat", None)
        if concat and hasattr(concat, "operands"):
            operands = concat.operands
            if hasattr(operands, "__iter__") and not isinstance(operands, str):
                for expr_item in operands:
                    if hasattr(expr_item, "kind"):
                        result = self.visit(expr_item)
                        if result:
                            return result
            else:
                result = self.visit(operands)
                if result:
                    return result
        return None

    def visit_cast_expression(self, node) -> str | None:
        """CastExpression: type'(expr) or signed'(expr)

        返回: expr 的信号
        """
        # DEAD CODE: migrated to @on handler - kept for reference only
        expr = getattr(node, "expression", None) or getattr(node, "operand", None)
        if expr:
            return self.visit(expr)
        return None

    def visit_tagged_union_expression(self, node) -> str | None:
        """TaggedUnionExpression: tag'(expr)

        返回: expr 的信号
        """
        # DEAD CODE: migrated to @on handler - kept for reference only
        expr = getattr(node, "expression", None)
        if expr:
            return self.visit(expr)
        return None

    def visit_multiple_concatenation(self, node) -> str | None:
        """MultipleConcatenationExpression: {{n{expr}}

        返回: expr 的信号
        """
        expr = getattr(node, "expression", None)
        if expr:
            return self.visit(expr)
        return None

    def visit_stream_expression(self, node) -> str | None:
        """StreamExpression: {>>[type]{expr}} or {<<[type]{expr}}

        返回: expr 的信号
        """
        # DEAD CODE: migrated to @on handler - kept for reference only
        expr = getattr(node, "expression", None) or getattr(node, "body", None)
        if expr:
            return self.visit(expr)
        return None

    def visit_assignment_pattern(self, node) -> str | None:
        """AssignmentPatternExpression: '{a, b, c}

        返回: 第一个信号的名称
        """
        # DEAD CODE: migrated to @on handler - kept for reference only
        signals = []
        # AssignmentPattern may have 'patterns' or 'items'
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    sig = self.visit(p)
                    if sig:
                        signals.append(sig)
        return signals[0] if signals else None

    def visit_null_literal(self, node) -> str | None:
        """NullLiteralExpression: null

        返回: None (null 没有信号名)
        """
        return None

    def visit_string_literal(self, node) -> str | None:
        """StringLiteralExpression: "string"

        返回: None (字符串没有信号名)
        """
        return None

    def visit_clock_event(self, node) -> str | None:
        """ClockingEvent: @clk, @(posedge clk)

        提取事件控制中的信号名
        """
        # ClockingEvent may have 'clock' or 'event'
        event = getattr(node, "event", None) or getattr(node, "clock", None)
        if event:
            return self.visit(event)

        # Try expression for event control
        expr = getattr(node, "expression", None)
        if expr:
            return self.visit(expr)
        return None

    def visit_empty_argument(self, node) -> str | None:
        """EmptyArgument: 函数参数占位 ,,

        返回: None
        """
        return None

    def visit_data_type(self, node) -> str | None:
        """DataType: bit, logic, int 等类型声明

        返回: None (类型没有信号)
        """
        return None

    def visit_type_reference(self, node) -> str | None:
        """TypeReference: 类型引用

        返回: None
        """
        return None

    def visit_time_literal(self, node) -> str | None:
        """TimeLiteralExpression: 1ns, 1us 等

        返回: None (时间字面量没有信号)
        """
        return None

    def visit_real_literal(self, node) -> str | None:
        """RealLiteralExpression: 1.5, 3.14 等

        返回: None (实数没有信号)
        """
        return None

    def visit_unbased_unsized_integer_literal(self, node) -> str | None:
        """UnbasedUnsizedIntegerLiteral: '0, '1, 'x, 'z

        返回: None
        """
        return None

    def visit_unbounded_literal(self, node) -> str | None:
        """UnboundedLiteral: $

        返回: None
        """
        return None

    def visit_unary_operator(self, node) -> str | None:
        """UnaryOperator: 一元运算符表达式

        与 UnaryOp 相同处理
        """
        operand = getattr(node, "operand", None) or getattr(node, "expression", None)
        if operand:
            return self.visit(operand)
        return None

    def visit_binary_operator(self, node) -> str | None:
        """BinaryOperator: 二元运算符表达式

        与 BinaryOp 相同处理
        """
        left = getattr(node, "left", None)
        if left:
            return self.visit(left)
        return None

    def visit_assignment_expression(self, node) -> str | None:
        """AssignmentExpression: 赋值表达式 a = b

        默认返回左操作数
        """
        # DEAD CODE: migrated to @on handler - kept for reference only
        left = getattr(node, "left", None)
        if left:
            return self.visit(left)
        return None

    def visit_new_class(self, node) -> str | None:
        """NewClassExpression: new() 或 new(expr)

        返回: None (构造函数没有信号)
        """
        return None

    def visit_new_array(self, node) -> str | None:
        """NewArrayExpression: new[size]

        返回: size 中的信号
        """
        size = getattr(node, "size", None) or getattr(node, "expression", None)
        if size:
            return self.visit(size)
        return None

    def visit_new_covergroup(self, node) -> str | None:
        """NewCovergroupExpression: covergroup

        返回: None
        """
        return None

    def visit_copy_class(self, node) -> str | None:
        """CopyClassExpression: class.copy()

        返回: None
        """
        return None

    def visit_arbitrary_symbol(self, node) -> str | None:
        """ArbitrarySymbol: 未解析的符号

        返回符号名
        """
        name = getattr(node, "name", None)
        if name:
            return str(name).strip()
        return None

    def visit_l_value_reference(self, node) -> str | None:
        """LValueReference: 左值引用

        返回引用的信号
        """
        value = getattr(node, "value", None)
        if value:
            return self.visit(value)
        return None

    def visit_assertion_instance(self, node) -> str | None:
        """AssertionInstance: assert property 等

        返回: None
        """
        return None

    def visit_replicated_assignment_pattern(self, node) -> str | None:
        """ReplicatedAssignmentPattern: '{n{a, b, c}}

        提取模式中的信号
        """
        # DEAD CODE: migrated to @on handler - kept for reference only
        signals = []
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    sig = self.visit(p)
                    if sig:
                        signals.append(sig)
        return signals[0] if signals else None

    def get_all_replicated_assignment_pattern(self, node) -> list[str]:
        """ReplicatedAssignmentPattern: '{n{a, b, c}}

        递归提取所有模式中的信号
        """
        signals = []
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    signals.extend(self.get_all_signals(p))
        return [s for s in signals if s]

    def visit_simple_assignment_pattern(self, node) -> str | None:
        """SimpleAssignmentPattern: '{a, b, c}

        提取模式中的信号
        """
        # DEAD CODE: migrated to @on handler - kept for reference only
        signals = []
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    sig = self.visit(p)
                    if sig:
                        signals.append(sig)
        return signals[0] if signals else None

    def get_all_simple_assignment_pattern(self, node) -> list[str]:
        """SimpleAssignmentPattern: '{a, b, c}

        递归提取所有模式中的信号
        """
        signals = []
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    signals.extend(self.get_all_signals(p))
        return [s for s in signals if s]

    def visit_structured_assignment_pattern(self, node) -> str | None:
        """StructuredAssignmentPattern: '{a: x, b: y}

        提取模式中的信号
        """
        # DEAD CODE: migrated to @on handler - kept for reference only
        signals = []
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    sig = self.visit(p)
                    if sig:
                        signals.append(sig)
        return signals[0] if signals else None

    def get_all_structured_assignment_pattern(self, node) -> list[str]:
        """StructuredAssignmentPattern: '{a: x, b: y}

        递归提取所有模式中的信号
        """
        signals = []
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    signals.extend(self.get_all_signals(p))
        return [s for s in signals if s]

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _get_param_map(self) -> dict[str, int]:
        """获取模块参数映射"""
        param_map = {}
        try:
            if hasattr(self.adapter, "_current_module") and self.adapter._current_module:
                params = self.adapter.get_module_parameters(self.adapter._current_module)
                for p in params:
                    name = p.get("name")
                    value = p.get("value")
                    if name and value is not None:
                        try:
                            param_map[name] = int(value)
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass
        return param_map

    def _evaluate_expr(self, expr, param_map: dict[str, int]) -> Any | None:
        """评估表达式，解析参数"""
        if expr is None:
            return None

        try:
            # 尝试获取 value 属性
            val = getattr(expr, "value", None)
            if val is not None:
                # 检查是否是参数引用
                if hasattr(expr, "symbol"):
                    sym = expr.symbol
                    if sym:
                        try:
                            _name = sym.name
                        except (UnicodeDecodeError, TypeError, Exception):
                            _name = None
                        if _name:
                            name = self._safe_str(_name)
                        if name in param_map:
                            return param_map[name]
                return int(val) if isinstance(val, (int, float)) else val

            # 二元表达式
            if hasattr(expr, "left") and hasattr(expr, "right"):
                left = self._evaluate_expr(getattr(expr, "left", None), param_map)
                right = self._evaluate_expr(getattr(expr, "right", None), param_map)

                if left is not None and right is not None:
                    op = str(getattr(expr, "kind", ""))
                    if "Add" in op:
                        return left + right
                    elif "Subtract" in op:
                        return left - right
                    elif "Multiply" in op:
                        return left * right
                    elif "Divide" in op and right != 0:
                        return left // right

            return None
        except Exception:
            return None

    def _is_literal(self, sig: str) -> bool:
        """检查信号名是否为字面量常量"""
        if not sig:
            return False
        # 字面量以非字母开头，如 1'b0, 4'h0, 'hA5A5A5A5, 123
        return not sig[0].isalpha() and not sig.startswith("_")
