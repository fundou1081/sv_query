"""[ADD 2026-06-26 A-PR2] Operator visitor mixin for SignalExpressionVisitor.

[REFACTOR A-PR2 2026-06-26] 抽 153 @on handler 涵盖所有 operator (Binary/Unary/Logical/
Conditional/Range/Concatenation/Cast/Assignment/Expression 等) 到独立 mixin.

主 class SignalExpressionVisitor 多继承此 mixin, 改 1 行平均 5 min → 1-2 min.

Handler 类别:
- Binary arithmetic: Add/Subtract/Multiply/Divide/Mod/Power (~6)
- Binary bitwise: BinaryAnd/Or/Xor/Xnor/Shift (~8)
- Binary comparison: Equality/Inequality/Less/Greater/CaseEquality/... (~8)
- Logical: And/Or/Xor/Not/Nand/Nor (~6)
- Conditional: Conditional/If/ConditionalPattern (~9)
- Range/Select: ElementSelect/RangeSelect/MemberAccess (~6)
- Concat: Concatenation/MultipleConcat/Replication/Streaming (~10)
- Cast/Conversion: Cast/TaggedUnion/Conversion (~6)
- Assignment: AssignmentExpression/ProceduralAssignment/... (~22)
- Other: InsideExpression/Dist/ValueRange/MinTypMax (~70+)

Total: 153 @on handler (1632 行, 9-12 行 boilerplate each)
"""
from typing import TYPE_CHECKING

from ._decorators import on
from .signal_result import SignalResult

if TYPE_CHECKING:
    from .signal_expression_visitor import SignalExpressionVisitor


class OperatorVisitor:
    """[ADD 2026-06-26 A-PR2] 抽所有 operator @on handler 到独立 mixin.

    主 class SignalExpressionVisitor 多继承此 mixin, 行为不变.
    """

    @on("InsideExpression")
    def extract_inside(self, node) -> SignalResult:
        """[NOT TESTED] InsideExpression: expr inside {a, b, c}"""
        left = getattr(node, "left", None) or getattr(node, "condition", None)
        right = getattr(node, "right", None) or getattr(node, "range", None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)


    @on("MinTypMaxExpression")
    def extract_min_typ_max(self, node) -> SignalResult:
        """[NOT TESTED] MinTypMaxExpression: min:typ:max"""
        min_val = getattr(node, "min", None) or getattr(node, "left", None)
        typ_val = getattr(node, "typ", None) or getattr(node, "value", None)
        max_val = getattr(node, "max", None) or getattr(node, "right", None)
        result = SignalResult()
        if min_val:
            result = result.merge(self.extract(min_val))
        if typ_val:
            result = result.merge(self.extract(typ_val))
        if max_val:
            result = result.merge(self.extract(max_val))
        return result


    @on("ValueRangeExpression")
    def extract_value_range(self, node) -> SignalResult:
        """[NOT TESTED] ValueRangeExpression: [a:b] or [a..b]"""
        left = getattr(node, "left", None) or getattr(node, "low", None)
        right = getattr(node, "right", None) or getattr(node, "high", None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)


    @on("MultipleConcatenationExpression")
    def extract_multiple_concatenation(self, node) -> SignalResult:
        """[NOT TESTED] MultipleConcatenationExpression: {{n{expr}}"""
        expr = getattr(node, "expression", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("StreamExpression")
    def extract_stream_expression(self, node) -> SignalResult:
        """[NOT TESTED] StreamExpression: {>>[type]{expr}} or {<<[type]{expr}}"""
        expr = getattr(node, "expression", None) or getattr(node, "body", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("AssignmentPatternExpression")
    def extract_assignment_pattern(self, node) -> SignalResult:
        """[NOT TESTED] AssignmentPatternExpression: '{a, b, c}"""
        result = SignalResult()
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result


    @on("AssignmentExpression")
    def extract_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] AssignmentExpression: a = b"""
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)


    @on("NewClassExpression")
    def extract_new_class(self, node) -> SignalResult:
        """[NOT TESTED] NewClassExpression: new()"""
        return SignalResult()


    @on("NewArrayExpression")
    def extract_new_array(self, node) -> SignalResult:
        """[NOT TESTED] NewArrayExpression: new[size]"""
        size = getattr(node, "size", None) or getattr(node, "expression", None)
        if size:
            return self.extract(size)
        return SignalResult()


    @on("CopyClassExpression")
    def extract_copy_class(self, node) -> SignalResult:
        """[NOT TESTED] CopyClassExpression: class.copy()"""
        return SignalResult()


    @on("ConcatenationExpression")
    def extract_concatenation(self, node) -> SignalResult:
        """ConcatenationExpression: {a, b, c}

        返回完整的拼接表达式字符串
        """
        # 使用 str(node) 获取完整的拼接表达式 {a, b, c}
        # [FIX] Semantic 层的 ConcatenationExpression str() 返回 'Expression(ExpressionKind.Concatenation)'
        # 需要通过 operands 构建实际表达式
        expr_str = str(node).strip()
        if expr_str and not expr_str.startswith("Expression("):
            return SignalResult.single(expr_str)

        # [FIX] Semantic 节点: 通过 operands 构建表达式
        operands = getattr(node, "operands", None) or getattr(node, "expressions", None)
        if operands:
            parts = []
            for expr in operands:
                expr_kind = getattr(expr, "kind", None)
                if expr_kind and "Token" not in str(expr_kind):
                    part = self.visit(expr)
                    if part:
                        parts.append(part)
            if parts:
                return SignalResult.single("{" + ", ".join(parts) + "}")

        # Fallback: 提取操作数
        result = SignalResult()
        if operands:
            for expr in operands:
                expr_kind = getattr(expr, "kind", None)
                if expr_kind and "Token" not in str(expr_kind):
                    result = result.merge(self.extract(expr))
        return result

    def visit_concatenation_expression(self, node) -> str | None:
        """visit 方法: ConcatenationExpression -> 完整拼接表达式字符串"""
        result = self.extract_concatenation(node)
        return result.primary if result else None

    # 别名: Semantic 层 ExpressionKind.Concatenation 也使用同一方法
    visit_concatenation = visit_concatenation_expression


    @on("ElementSelectExpression")
    def extract_element_select(self, node) -> SignalResult:
        """[MIGRATED] ElementSelectExpression: data[5] bit select

        From visit_element_select - handles symbol-based selectors
        """
        value = getattr(node, "value", None) or getattr(node, "base", None) or getattr(node, "left", None)
        selector = getattr(node, "selector", None)

        if value and selector is not None:
            base_name = None
            # Try to get name from symbol
            if hasattr(value, "symbol"):
                sym = value.symbol
                # [Bug-fix 2026-06-13] 同上, try/except 防 UnicodeDecodeError
                try:
                    if hasattr(sym, "name"):
                        base_name = self._safe_str(sym.name)
                except (UnicodeDecodeError, TypeError):
                    base_name = None

            if base_name:
                selector_val = getattr(selector, "value", None)
                if selector_val is not None:
                    return SignalResult(primary=f"{base_name}[{selector_val}]")

        # Fall back to extracting from base
        if value:
            return self.extract(value)
        return SignalResult()

    @on("CastExpression")
    def extract_cast_expression(self, node) -> SignalResult:
        """[NOT TESTED] CastExpression: type'(expr)"""
        expr = getattr(node, "expression", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("TaggedUnionExpression")
    def extract_tagged_union_expression(self, node) -> SignalResult:
        """[NOT TESTED] TaggedUnionExpression: tag'(expr)"""
        expr = getattr(node, "expression", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("IntegerVectorExpression")
    def extract_integer_vector(self, node) -> SignalResult:
        """[NOT TESTED] IntegerVectorExpression: 带位宽的字面量"""
        return SignalResult()


    @on("ReplicatedAssignmentPattern")
    def extract_replicated_assignment_pattern(self, node) -> SignalResult:
        """[NOT TESTED] ReplicatedAssignmentPattern: '{n{a, b, c}}"""
        result = SignalResult()
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result


    @on("SimpleAssignmentPattern")
    def extract_simple_assignment_pattern(self, node) -> SignalResult:
        """[NOT TESTED] SimpleAssignmentPattern: 简单赋值模式"""
        result = SignalResult()
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result


    @on("StructuredAssignmentPattern")
    def extract_structured_assignment_pattern(self, node) -> SignalResult:
        """[NOT TESTED] StructuredAssignmentPattern: 结构化赋值模式"""
        result = SignalResult()
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result


    @on("MemberAccessExpression")
    def extract_member_access(self, node) -> SignalResult:
        """[MIGRATED] MemberAccessExpression: p.addr class member access

        From visit_member_access - extracts compound signal name
        """
        value = getattr(node, "value", None) or getattr(node, "expression", None)
        member_sym = getattr(node, "member", None)

        if value and member_sym:
            base_result = self.extract(value)
            base_name = base_result.primary

            member_name = self._safe_get_name(member_sym, None)
            if member_name:
                member_name = self._safe_str(member_name).strip()
            else:
                member_name = self._safe_str(member_sym).strip()

            if base_name and member_name:
                return SignalResult(primary=f"{base_name}.{member_name}")

        return SignalResult()

    @on("ExpressionConstraint")
    def extract_expression_constraint(self, node) -> SignalResult:
        """[NOT TESTED] ExpressionConstraint: expression constraint"""
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("ConditionalPattern")
    def extract_conditional_pattern(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalPattern: pattern if cond"""
        result = SignalResult()
        pattern = getattr(node, "pattern", None)
        if pattern:
            result = result.merge(self.extract(pattern))
        cond = getattr(node, "condition", None) or getattr(node, "cond", None)
        if cond:
            result = result.merge(self.extract(cond))
        return result


    @on("UnaryPropertyExpr")
    def extract_unary_property_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryPropertyExpression: unary property"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("ConditionalExpression")
    def extract_conditional_expression(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalExpression: cond ? expr1 : expr2"""
        result = SignalResult()
        cond = getattr(node, "condition", None) or getattr(node, "cond", None)
        if cond:
            result = result.merge(self.extract(cond))
        true_expr = getattr(node, "true_expr", None) or getattr(node, "expr1", None)
        if true_expr:
            result = result.merge(self.extract(true_expr))
        false_expr = getattr(node, "false_expr", None) or getattr(node, "expr2", None)
        if false_expr:
            result = result.merge(self.extract(false_expr))
        return result


    @on("ExpressionStatement")
    def extract_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ExpressionStatement: expression statement"""
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("ConditionalStatement")
    def extract_conditional_statement(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalStatement: conditional statement"""
        result = SignalResult()
        cond = getattr(node, "condition", None) or getattr(node, "cond", None)
        if cond:
            result = result.merge(self.extract(cond))
        true_body = getattr(node, "true_body", None) or getattr(node, "body", None)
        if true_body:
            result = result.merge(self.extract(true_body))
        false_body = getattr(node, "false_body", None) or getattr(node, "else_body", None)
        if false_body:
            result = result.merge(self.extract(false_body))
        return result

    # Constraint kinds

    @on("UnaryBinsSelectExpr")
    def extract_unary_bins_select_expr(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBinsSelectExpr: unary bins select expression"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("BinaryBinsSelectExpr")
    def extract_binary_bins_select_expr(self, node) -> SignalResult:
        """[NOT TESTED] BinaryBinsSelectExpr: binary bins select expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("AddExpression")
    def extract_add_expression(self, node) -> SignalResult:
        """[NOT TESTED] AddExpression: addition expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("SubtractExpression")
    def extract_subtract_expression(self, node) -> SignalResult:
        """[NOT TESTED] SubtractExpression: subtraction expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("MultiplyExpression")
    def extract_multiply_expression(self, node) -> SignalResult:
        """[NOT TESTED] MultiplyExpression: multiplication expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("DivideExpression")
    def extract_divide_expression(self, node) -> SignalResult:
        """[NOT TESTED] DivideExpression: division expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("BinaryAndExpression")
    def extract_binary_and_expression(self, node) -> SignalResult:
        """[NOT TESTED] BinaryAndExpression: binary and expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("BinaryOrExpression")
    def extract_binary_or_expression(self, node) -> SignalResult:
        """[NOT TESTED] BinaryOrExpression: binary or expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("BinaryXorExpression")
    def extract_binary_xor_expression(self, node) -> SignalResult:
        """[NOT TESTED] BinaryXorExpression: binary xor expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("BinaryXnorExpression")
    def extract_binary_xnor_expression(self, node) -> SignalResult:
        """[NOT TESTED] BinaryXnorExpression: binary xnor expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("EqualityExpression")
    def extract_equality_expression(self, node) -> SignalResult:
        """[NOT TESTED] EqualityExpression: equality expression =="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("InequalityExpression")
    def extract_inequality_expression(self, node) -> SignalResult:
        """[NOT TESTED] InequalityExpression: inequality expression !="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("CaseEqualityExpression")
    def extract_case_equality_expression(self, node) -> SignalResult:
        """[NOT TESTED] CaseEqualityExpression: case equality expression ==="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("CaseInequalityExpression")
    def extract_case_inequality_expression(self, node) -> SignalResult:
        """[NOT TESTED] CaseInequalityExpression: case inequality expression !=="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("LessThanExpression")
    def extract_less_than_expression(self, node) -> SignalResult:
        """[NOT TESTED] LessThanExpression: less than expression <"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("GreaterThanExpression")
    def extract_greater_than_expression(self, node) -> SignalResult:
        """[NOT TESTED] GreaterThanExpression: greater than expression >"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("WildcardEqualityExpression")
    def extract_wildcard_equality_expression(self, node) -> SignalResult:
        """[NOT TESTED] WildcardEqualityExpression: wildcard equality expression ==?"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("WildcardInequalityExpression")
    def extract_wildcard_inequality_expression(self, node) -> SignalResult:
        """[NOT TESTED] WildcardInequalityExpression: wildcard inequality expression !=?"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("ArithmeticShiftLeftExpression")
    def extract_arithmetic_shift_left_expression(self, node) -> SignalResult:
        """[NOT TESTED] ArithmeticShiftLeftExpression: arithmetic shift left <<<"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("ArithmeticShiftRightExpression")
    def extract_arithmetic_shift_right_expression(self, node) -> SignalResult:
        """[NOT TESTED] ArithmeticShiftRightExpression: arithmetic shift right >>>"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("PowerExpression")
    def extract_power_expression(self, node) -> SignalResult:
        """[NOT TESTED] PowerExpression: power expression **"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("AddAssignmentExpression")
    def extract_add_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] AddAssignmentExpression: add assignment +="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("SubtractAssignmentExpression")
    def extract_subtract_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] SubtractAssignmentExpression: subtract assignment -="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("AndAssignmentExpression")
    def extract_and_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] AndAssignmentExpression: and assignment &="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("OrAssignmentExpression")
    def extract_or_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] OrAssignmentExpression: or assignment |="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("XorAssignmentExpression")
    def extract_xor_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] XorAssignmentExpression: xor assignment ^="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("ArithmeticLeftShiftAssignmentExpression")
    def extract_arithmetic_left_shift_assignment(self, node) -> SignalResult:
        """[NOT TESTED] ArithmeticLeftShiftAssignmentExpression: <<<="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("ArithmeticRightShiftAssignmentExpression")
    def extract_arithmetic_right_shift_assignment(self, node) -> SignalResult:
        """[NOT TESTED] ArithmeticRightShiftAssignmentExpression: >>>="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("LogicalLeftShiftAssignmentExpression")
    def extract_logical_left_shift_assignment(self, node) -> SignalResult:
        """[NOT TESTED] LogicalLeftShiftAssignmentExpression: <<="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("LogicalRightShiftAssignmentExpression")
    def extract_logical_right_shift_assignment(self, node) -> SignalResult:
        """[NOT TESTED] LogicalRightShiftAssignmentExpression: >>="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("MultiplyAssignmentExpression")
    def extract_multiply_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] MultiplyAssignmentExpression: *="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("DivideAssignmentExpression")
    def extract_divide_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] DivideAssignmentExpression: /="""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("ArrayOrRandomizeMethodExpression")
    def extract_array_randomize_method_expr(self, node) -> SignalResult:
        """[Phase 1 Day 1 2026-07-07 FIXED + TESTED] ArrayOrRandomizeMethodExpression: array.randomize() with method

        pyslang attrs (verified 2026-07-07):
          - method    : InvocationExpressionSyntax (the .randomize() call)
          - constraints : ConstraintBlockSyntax (the `with { ... }` block) — optional

        NOTE: 旧实现用 getattr(node, "array") / "with" 但 pyslang 实际是 "method" / "constraints".
        """
        result = SignalResult()
        # .randomize() call (array.randomize())
        method = getattr(node, "method", None) or getattr(node, "array", None) or getattr(node, "expr", None)
        if method:
            result = result.merge(self.extract(method))
        # with { ... } inline constraint block
        constraints = getattr(node, "constraints", None) or getattr(node, "with", None) or getattr(node, "expr2", None)
        if constraints:
            result = result.merge(self.extract(constraints))
        return result

    # Bins selection

    @on("BinsSelection")
    def extract_bins_selection(self, node) -> SignalResult:
        """[NOT TESTED] BinsSelection: bins selection"""
        result = SignalResult()
        bins = getattr(node, "bins", None) or getattr(node, "expr", None)
        if bins:
            result = result.merge(self.extract(bins))
        select = getattr(node, "select", None) or getattr(node, "expr2", None)
        if select:
            result = result.merge(self.extract(select))
        return result


    @on("BinsSelectConditionExpr")
    def extract_bins_select_condition_expr(self, node) -> SignalResult:
        """[NOT TESTED] BinsSelectConditionExpr: bins select condition expression"""
        result = SignalResult()
        cond = getattr(node, "condition", None) or getattr(node, "cond", None)
        if cond:
            result = result.merge(self.extract(cond))
        return result


    @on("BinSelectWithFilterExpr")
    def extract_bin_select_with_filter_expr(self, node) -> SignalResult:
        """[NOT TESTED] BinSelectWithFilterExpr: bin select with filter expression"""
        result = SignalResult()
        bins = getattr(node, "bins", None) or getattr(node, "expr", None)
        if bins:
            result = result.merge(self.extract(bins))
        filter_expr = getattr(node, "filter", None) or getattr(node, "expr2", None)
        if filter_expr:
            result = result.merge(self.extract(filter_expr))
        return result

    # Bit select

    @on("BitSelect")
    def extract_bit_select(self, node) -> SignalResult:
        """[NOT TESTED] BitSelect: bit select"""
        result = SignalResult()
        base = getattr(node, "base", None) or getattr(node, "expr", None)
        if base:
            result = result.merge(self.extract(base))
        index = getattr(node, "index", None) or getattr(node, "expr2", None)
        if index:
            result = result.merge(self.extract(index))
        return result

    # Range select

    @on("AscendingRangeSelect")
    def extract_ascending_range_select(self, node) -> SignalResult:
        """[NOT TESTED] AscendingRangeSelect: ascending range select"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("DescendingRangeSelect")
    def extract_descending_range_select(self, node) -> SignalResult:
        """[NOT TESTED] DescendingRangeSelect: descending range select"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    # Class expressions

    @on("ConditionalConstraint")
    def extract_conditional_constraint(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalConstraint: conditional constraint"""
        result = SignalResult()
        cond = getattr(node, "condition", None) or getattr(node, "cond", None)
        if cond:
            result = result.merge(self.extract(cond))
        true_body = getattr(node, "true_body", None) or getattr(node, "constraint", None)
        if true_body:
            result = result.merge(self.extract(true_body))
        false_body = getattr(node, "false_body", None)
        if false_body:
            result = result.merge(self.extract(false_body))
        return result


    @on("DistConstraintList")
    def extract_dist_constraint_list(self, node) -> SignalResult:
        """[NOT TESTED] DistConstraintList: dist constraint list"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result


    @on("ExpressionCoverageBinInitializer")
    def extract_expression_coverage_bin_initializer(self, node) -> SignalResult:
        """[NOT TESTED] ExpressionCoverageBinInitializer: expression coverage bin initializer"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    # ElabSystemTask

    @on("BadExpression")
    def extract_bad_expression(self, node) -> SignalResult:
        """[NOT TESTED] BadExpression: bad expression"""
        return SignalResult()

    # Binary block event expression

    @on("BinaryBlockEventExpression")
    def extract_binary_block_event_expression(self, node) -> SignalResult:
        """[NOT TESTED] BinaryBlockEventExpression: binary block event expression"""
        return SignalResult()


    @on("BinaryEventExpression")
    def extract_binary_event_expression(self, node) -> SignalResult:
        """[NOT TESTED] BinaryEventExpression: binary event expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    # Blocking event trigger

    @on("AssignmentPatternItem")
    def extract_assignment_pattern_item(self, node) -> SignalResult:
        """[NOT TESTED] AssignmentPatternItem: assignment pattern item"""
        result = SignalResult()
        pattern = getattr(node, "pattern", None)
        if pattern:
            result = result.merge(self.extract(pattern))
        init = getattr(node, "init", None) or getattr(node, "value", None)
        if init:
            result = result.merge(self.extract(init))
        return result

    # Anonymous program

    @on("ParenthesizedExpression")
    def extract_parenthesized_expression(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedExpression: parenthesized expression"""
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            return self.extract(expr)
        return SignalResult()

    # Conditional directive expressions

    @on("BinaryConditionalDirectiveExpression")
    def extract_binary_conditional_directive_expr(self, node) -> SignalResult:
        """[NOT TESTED] BinaryConditionalDirectiveExpression: binary conditional directive expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("DefaultPatternKeyExpression")
    def extract_default_pattern_key_expression(self, node) -> SignalResult:
        """[NOT TESTED] DefaultPatternKeyExpression: default pattern key expression"""
        return SignalResult()

    # Function return type

    @on("DistWeight")
    def extract_dist_weight(self, node) -> SignalResult:
        """[NOT TESTED] DistWeight: dist weight"""
        result = SignalResult()
        weight = getattr(node, "weight", None) or getattr(node, "expr", None)
        if weight:
            result = result.merge(self.extract(weight))
        value = getattr(node, "value", None) or getattr(node, "expr2", None)
        if value:
            result = result.merge(self.extract(value))
        return result

    # Let expression

    @on("ModExpression")
    def extract_mod_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ModExpression: mod expression %"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("ConditionalPropertyExpr")
    def extract_conditional_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalPropertyExpr: conditional property expression"""
        result = SignalResult()
        cond = getattr(node, "condition", None) or getattr(node, "expr", None)
        if cond:
            result = result.merge(self.extract(cond))
        prop = getattr(node, "property", None) or getattr(node, "true_body", None)
        if prop:
            result = result.merge(self.extract(prop))
        else_body = getattr(node, "else_body", None) or getattr(node, "false_body", None)
        if else_body:
            result = result.merge(self.extract(else_body))
        return result


    @on("UnarySelectPropertyExpr")
    def extract_unary_select_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] UnarySelectPropertyExpr: unary select property expression"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result


    @on("InvocationExpression")
    def extract_invocation_expression(self, node) -> SignalResult:
        """[NOT TESTED] InvocationExpression: invocation expression"""
        result = SignalResult()
        args = getattr(node, "arguments", None)
        if args and hasattr(args, "__iter__"):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result


    @on("VoidCastedCallStatement")
    def extract_void_casted_call_statement(self, node) -> SignalResult:
        """[NOT TESTED] VoidCastedCallStatement: void casted call statement"""
        result = SignalResult()
        call = getattr(node, "call", None) or getattr(node, "expr", None)
        if call:
            result = result.merge(self.extract(call))
        return result

    # Declaration-related expressions

    @on("ExpressionPattern")
    def extract_expression_pattern(self, node) -> SignalResult:
        """[NOT TESTED] ExpressionPattern: expression pattern"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "pattern", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result


    @on("StreamingConcatenationExpression")
    def extract_streaming_concatenation_expression(self, node) -> SignalResult:
        """[NOT TESTED] StreamingConcatenationExpression: streaming concatenation expression"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "streams", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result


    @on("StreamExpressionWithRange")
    def extract_stream_expression_with_range(self, node) -> SignalResult:
        """[NOT TESTED] StreamExpressionWithRange: stream expression with range"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "expr", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    # Expression with clauses

    @on("ExpressionOrDist")
    def extract_expression_or_dist(self, node) -> SignalResult:
        """[NOT TESTED] ExpressionOrDist: expression or dist expression"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            result = result.merge(self.extract(expr))
        dist = getattr(node, "dist", None)
        if dist:
            result = result.merge(self.extract(dist))
        return result


    @on("EmptyQueueExpression")
    def extract_empty_queue_expression(self, node) -> SignalResult:
        """[NOT TESTED] EmptyQueueExpression: empty queue expression {}"""
        return SignalResult()


    @on("WildcardLiteralExpression")
    def extract_wildcard_literal_expression(self, node) -> SignalResult:
        """[NOT TESTED] WildcardLiteralExpression: wildcard literal expression"""
        return SignalResult()


    @on("NullLiteralExpression")
    def extract_null_literal_expression(self, node) -> SignalResult:
        """[NOT TESTED] NullLiteralExpression: null literal expression"""
        return SignalResult()


    @on("StringLiteralExpression")
    def extract_string_literal_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] StringLiteralExpression: string literal expression"""
        return SignalResult()


    @on("TimeLiteralExpression")
    def extract_time_literal_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] TimeLiteralExpression: time literal expression"""
        return SignalResult()


    @on("RealLiteralExpression")
    def extract_real_literal_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] RealLiteralExpression: real literal expression"""
        return SignalResult()


    @on("IntegerLiteralExpression")
    def extract_integer_literal_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] IntegerLiteralExpression: integer literal expression"""
        return SignalResult()


    @on("UnbasedUnsizedLiteralExpression")
    def extract_unbased_unsized_literal_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] UnbasedUnsizedLiteralExpression: unbased unsized literal expression"""
        return SignalResult()

    # Signed cast expression

    @on("SignedCastExpression")
    def extract_signed_cast_expression(self, node) -> SignalResult:
        """[NOT TESTED] SignedCastExpression: signed cast expression"""
        result = SignalResult()
        expr = getattr(node, "expr", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    # Unary operators

    @on("UnaryPlusExpression")
    def extract_unary_plus_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] UnaryPlusExpression: unary plus expression +"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("UnaryMinusExpression")
    def extract_unary_minus_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] UnaryMinusExpression: unary minus expression -"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("UnaryBitwiseNotExpression")
    def extract_unary_bitwise_not_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseNotExpression: unary bitwise not expression ~"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("UnaryLogicalNotExpression")
    def extract_unary_logical_not_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryLogicalNotExpression: unary logical not expression !"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("UnaryBitwiseAndExpression")
    def extract_unary_bitwise_and_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseAndExpression: unary bitwise and expression &"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("UnaryBitwiseOrExpression")
    def extract_unary_bitwise_or_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseOrExpression: unary bitwise or expression |"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("UnaryBitwiseXorExpression")
    def extract_unary_bitwise_xor_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseXorExpression: unary bitwise xor expression ^"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("UnaryBitwiseNandExpression")
    def extract_unary_bitwise_nand_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseNandExpression: unary bitwise nand expression ~&"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("UnaryBitwiseNorExpression")
    def extract_unary_bitwise_nor_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseNorExpression: unary bitwise nor expression ~|"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("UnaryBitwiseXnorExpression")
    def extract_unary_bitwise_xnor_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseXnorExpression: unary bitwise xnor expression ^~"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("UnaryPreincrementExpression")
    def extract_unary_preincrement_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryPreincrementExpression: pre-increment expression ++expr"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("UnaryPredecrementExpression")
    def extract_unary_predecrement_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryPredecrementExpression: pre-decrement expression --expr"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("PostincrementExpression")
    def extract_postincrement_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] PostincrementExpression: post-increment expression expr++"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()


    @on("PostdecrementExpression")
    def extract_postdecrement_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] PostdecrementExpression: post-decrement expression expr--"""
        expr = getattr(node, "expr", None) or getattr(node, "operand", None)
        if expr:
            return self.extract(expr)
        return SignalResult()

    # Comparison expressions (missing)

    @on("LessThanEqualExpression")
    def extract_less_than_equal_expression(self, node) -> SignalResult:
        """[NOT TESTED] LessThanEqualExpression: <= expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("GreaterThanEqualExpression")
    def extract_greater_than_equal_expression(self, node) -> SignalResult:
        """[NOT TESTED] GreaterThanEqualExpression: >= expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    # Logical expressions

    @on("LogicalAndExpression")
    def extract_logical_and_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] LogicalAndExpression: && expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("LogicalOrExpression")
    def extract_logical_or_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] LogicalOrExpression: || expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("LogicalEquivalenceExpression")
    def extract_logical_equivalence_expression(self, node) -> SignalResult:
        """[NOT TESTED] LogicalEquivalenceExpression: <-> expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("LogicalImplicationExpression")
    def extract_logical_implication_expression(self, node) -> SignalResult:
        """[NOT TESTED] LogicalImplicationExpression: -> expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    # Logical shift expressions

    @on("LogicalShiftLeftExpression")
    def extract_logical_shift_left_expression(self, node) -> SignalResult:
        """[NOT TESTED] LogicalShiftLeftExpression: << expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("LogicalShiftRightExpression")
    def extract_logical_shift_right_expression(self, node) -> SignalResult:
        """[NOT TESTED] LogicalShiftRightExpression: >> expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    # Pragma expressions

    @on("SimplePragmaExpression")
    def extract_simple_pragma_expression(self, node) -> SignalResult:
        """[NOT TESTED] SimplePragmaExpression: simple pragma expression"""
        return SignalResult()


    @on("NumberPragmaExpression")
    def extract_number_pragma_expression(self, node) -> SignalResult:
        """[NOT TESTED] NumberPragmaExpression: number pragma expression"""
        return SignalResult()


    @on("NameValuePragmaExpression")
    def extract_name_value_pragma_expression(self, node) -> SignalResult:
        """[NOT TESTED] NameValuePragmaExpression: name value pragma expression"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "value", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result


    @on("ParenPragmaExpression")
    def extract_paren_pragma_expression(self, node) -> SignalResult:
        """[NOT TESTED] ParenPragmaExpression: parenthesized pragma expression"""
        result = SignalResult()
        expr = getattr(node, "expr", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    # Paren expression list

    @on("ParenExpressionList")
    def extract_paren_expression_list(self, node) -> SignalResult:
        """[NOT TESTED] ParenExpressionList: parenthesized expression list"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    # Event control expressions

    @on("EventControlWithExpression")
    def extract_event_control_with_expression(self, node) -> SignalResult:
        """[NOT TESTED] EventControlWithExpression: event control with expression"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "condition", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result


    @on("SignalEventExpression")
    def extract_signal_event_expression(self, node) -> SignalResult:
        """[NOT TESTED] SignalEventExpression: signal event expression"""
        result = SignalResult()
        signal = getattr(node, "signal", None) or getattr(node, "expr", None)
        if signal:
            result = result.merge(self.extract(signal))
        return result


    @on("PrimaryBlockEventExpression")
    def extract_primary_block_event_expression(self, node) -> SignalResult:
        """[NOT TESTED] PrimaryBlockEventExpression: primary block event expression"""
        return SignalResult()

    # Case items

    @on("ConditionalPathDeclaration")
    def extract_conditional_path_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalPathDeclaration: conditional path declaration"""
        return SignalResult()


    @on("SimpleBinsSelectExpr")
    def extract_simple_bins_select_expr(self, node) -> SignalResult:
        """[NOT TESTED] SimpleBinsSelectExpr: simple bins select expression"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result


    @on("ParenthesizedBinsSelectExpr")
    def extract_parenthesized_bins_select_expr(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedBinsSelectExpr: parenthesized bins select expression"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "bins", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result


    @on("ColonExpressionClause")
    def extract_colon_expression_clause(self, node) -> SignalResult:
        """[NOT TESTED] ColonExpressionClause: colon expression clause"""
        result = SignalResult()
        expr = getattr(node, "expr", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result


    @on("ExpressionTimingCheckArg")
    def extract_expression_timing_check_arg(self, node) -> SignalResult:
        """[NOT TESTED] ExpressionTimingCheckArg: expression timing check arg"""
        result = SignalResult()
        expr = getattr(node, "expr", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result


    @on("ModAssignmentExpression")
    def extract_mod_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] ModAssignmentExpression: mod assignment expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("NonblockingAssignmentExpression")
    def extract_nonblocking_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] NonblockingAssignmentExpression: nonblocking assignment expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    # Last 21 missing handlers

    @on("ParenthesizedConditionalDirectiveExpression")
    def extract_parenthesized_conditional_directive_expression(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedConditionalDirectiveExpression: parenthesized conditional directive expression"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result


    @on("ParenthesizedEventExpression")
    def extract_parenthesized_event_expression(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedEventExpression: parenthesized event expression"""
        result = SignalResult()
        event = getattr(node, "event", None) or getattr(node, "expr", None)
        if event:
            result = result.merge(self.extract(event))
        return result


    @on("SuperNewDefaultedArgsExpression")
    def extract_super_new_defaulted_args_expression(self, node) -> SignalResult:
        """[NOT TESTED] SuperNewDefaultedArgsExpression: super.new with defaulted args expression"""
        return SignalResult()


    @on("TimingControlExpression")
    def extract_timing_control_expression(self, node) -> SignalResult:
        """[NOT TESTED] TimingControlExpression: timing control expression"""
        return SignalResult()


    @on("UnaryConditionalDirectiveExpression")
    def extract_unary_conditional_directive_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryConditionalDirectiveExpression: unary conditional directive expression"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result


    @on("TransRange")
    def extract_transrange(self, node) -> SignalResult:
        """[NOT TESTED] TransRange: Transrange"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("TransRepeatRange")
    def extract_transrepeatrange(self, node) -> SignalResult:
        """[NOT TESTED] TransRepeatRange: Transrepeatrange"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("TypeAssignment")
    def extract_typeassignment(self, node) -> SignalResult:
        """[NOT TESTED] TypeAssignment: Typeassignment"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("RangeCoverageBinInitializer")
    def extract_rangecoveragebininitializer(self, node) -> SignalResult:
        """[NOT TESTED] RangeCoverageBinInitializer: Rangecoveragebininitializer"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("RangeDimensionSpecifier")
    def extract_rangedimensionspecifier(self, node) -> SignalResult:
        """[NOT TESTED] RangeDimensionSpecifier: Rangedimensionspecifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("RangeList")
    def extract_rangelist(self, node) -> SignalResult:
        """[NOT TESTED] RangeList: Rangelist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("SimpleRangeSelect")
    def extract_simplerangeselect(self, node) -> SignalResult:
        """[NOT TESTED] SimpleRangeSelect: Simplerangeselect"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("NamedParamAssignment")
    def extract_namedparamassignment(self, node) -> SignalResult:
        """[NOT TESTED] NamedParamAssignment: Namedparamassignment"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("OrderedParamAssignment")
    def extract_orderedparamassignment(self, node) -> SignalResult:
        """[NOT TESTED] OrderedParamAssignment: Orderedparamassignment"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("ParameterValueAssignment")
    def extract_parametervalueassignment(self, node) -> SignalResult:
        """[NOT TESTED] ParameterValueAssignment: Parametervalueassignment"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("PortConcatenation")
    def extract_portconcatenation(self, node) -> SignalResult:
        """[NOT TESTED] PortConcatenation: Portconcatenation"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("NamedConditionalDirectiveExpression")
    def extract_namedconditionaldirectiveexpression(self, node) -> SignalResult:
        """[NOT TESTED] NamedConditionalDirectiveExpression: Namedconditionaldirectiveexpression"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("DefaultDistItem")
    def extract_defaultdistitem(self, node) -> SignalResult:
        """[NOT TESTED] DefaultDistItem: Defaultdistitem"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("DelayModeDistributedDirective")
    def extract_delaymodedistributeddirective(self, node) -> SignalResult:
        """[NOT TESTED] DelayModeDistributedDirective: Delaymodedistributeddirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("DistItem")
    def extract_distitem(self, node) -> SignalResult:
        """[NOT TESTED] DistItem: Distitem"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("ElementSelect")
    def extract_elementselect(self, node) -> SignalResult:
        """[NOT TESTED] ElementSelect: Elementselect"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("ConditionalPredicate")
    def extract_conditionalpredicate(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalPredicate: Conditionalpredicate"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("DefParamAssignment")
    def extract_defparamassignment(self, node) -> SignalResult:
        """[NOT TESTED] DefParamAssignment: Defparamassignment"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


