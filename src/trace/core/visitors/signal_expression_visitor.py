# signal_expression_visitor.py - 信号/表达式提取 Visitor
"""
[铁律15] Visitor 模式
[铁律26] 必须使用 Visitor 模式，禁止 if-elif 链

职责:
1. 提取信号名 (visit_identifier_name, visit_scoped_name, etc.)
2. 提取表达式中的所有信号 (visit_conditional_op, visit_concatenation, etc.)

对应 graph_builder.py 中的:
- _get_signal()
- _get_all_signals()
"""

import logging
from typing import Any, Callable, ClassVar

from ._decorators import on
from .base_visitor import BaseVisitor
from .member_visitor import MemberVisitor
from .expression_visitor import ExpressionVisitor
from .generate_visitor import GenerateVisitor
from .operator_visitor import OperatorVisitor
from .signal_result import SignalResult

logger = logging.getLogger(__name__)


class SignalExpressionVisitor(BaseVisitor, OperatorVisitor, MemberVisitor, GenerateVisitor, ExpressionVisitor):
    """信号/表达式提取 Visitor

    负责将 AST 节点转换为信号名或信号列表。
    使用 Visitor 模式，每个语法类型对应独立的 visit 方法。

    单 dispatch 重构:
        使用 @on 装饰器注册 handler，
        extract() 统一入口分派到对应的 handler。

    使用方式:
        visitor = SignalExpressionVisitor(adapter)
        signal_name = visitor.visit(node)
        all_signals = visitor.get_all_signals(node)
        result = visitor.extract(node)  # 统一入口 (推荐)
    """

    # 单 dispatch: handler 注册表
    _HANDLERS: ClassVar[dict[str, Callable]] = {}

    # 双轨控制: True=新 handler, False=旧方法回退
    _dispatch_enabled: bool = True

    def __init__(self, adapter):
        """初始化

        Args:
            adapter: PyslangAdapter 实例，用于清理名称和访问模块参数
        """
        super().__init__()
        self.adapter = adapter

        # 收集 @on 装饰的 handler
        self._collect_handlers()

    @staticmethod
    def _safe_str(obj) -> str:
        """安全的 str() 调用,容忍非 utf-8 字节 (e.g. escape 序列)"""
        if obj is None:
            return ""
        try:
            return str(obj)
        except (UnicodeDecodeError, TypeError):
            try:
                if hasattr(obj, 'rawText'):
                    raw = bytes(obj.rawText) if hasattr(obj.rawText, '__bytes__') else b''
                elif hasattr(obj, '__bytes__'):
                    raw = bytes(obj)
                else:
                    raw = b''
                return f"<id:0x{raw.hex()[:16]}>"
            except Exception:
                return "<id:non-utf8>"


    def _safe_get_name(self, sym, default=None):
        """[Bug-fix 2026-06-13] 防御 sym.name 访问触发 UnicodeDecodeError."""
        if sym is None:
            return default
        try:
            return getattr(sym, "name", default)
        except (UnicodeDecodeError, TypeError, Exception):
            return default
    def _collect_handlers(self):
        """收集所有 @on 装饰的 handler 到 _HANDLERS"""
        for name in dir(self):
            if name.startswith("_"):
                continue
            method = getattr(self, name, None)
            if callable(method) and hasattr(method, "_kind_name"):
                kind_name = method._kind_name
                self._HANDLERS[kind_name] = method
                logger.debug(f"Registered handler: {kind_name} -> {name}")

    def _get_kind_name(self, node) -> str | None:
        """获取节点的 kind 名称"""
        if node is None:
            return None
        # [Stage 6] v11: SyntaxList 包装拆开变为 plain list, 统一走 SyntaxList handler
        if isinstance(node, list):
            return "SyntaxList"
        kind = getattr(node, "kind", None)
        if kind and hasattr(kind, "name"):
            return kind.name
        return None

    # =========================================================================
    # 主入口方法
    # =========================================================================

    def visit(self, node) -> str | None:
        """主入口：分发到对应的 visit 方法

        Args:
            node: AST 节点

        Returns:
            信号名字符串，或 None
        """
        if node is None:
            return None

        kind = getattr(node, "kind", None)
        if kind is None:
            return None

        kind_name = kind.name if hasattr(kind, "name") else None
        if kind_name:
            import re

            # 首先尝试直接转换 (IdentifierName -> visit_identifier_name)
            method_name = "visit_" + re.sub(r"(?<!^)(?=[A-Z])", "_", kind_name).lower()
            if hasattr(self, method_name):
                return getattr(self, method_name)(node)

            # 别名映射 (Syntax AST <-> Semantic AST 命名差异)
            # BinaryOp -> binary_expression, UnaryOp -> unary
            alias_map = {
                "BinaryOp": "binary_expression",
                "UnaryOp": "unary",
                "ConditionalExpression": "conditional_op",
                # [FIX] Semantic ExpressionKind vs SyntaxKind 命名差异
                "Concatenation": "concatenation_expression",
                "Replication": "multiple_concatenation",
            }
            if kind_name in alias_map:
                method_name = "visit_" + alias_map[kind_name]
                if hasattr(self, method_name):
                    return getattr(self, method_name)(node)

        return self.generic_visit(node)

    def extract(self, node) -> SignalResult:
        """统一提取信号

        替代 visit() + get_all_signals() 的双接口。
        返回 SignalResult，包含丰富信息。

        单 dispatch 架构:
            1. 如果 _dispatch_enabled=True 且存在 handler，从 _HANDLERS 分派
            2. 否则使用旧的 visit() + get_all_signals() fallback

        Args:
            node: AST 节点

        Returns:
            SignalResult(primary=信号名, all_signals=[信号列表], kind_name=..., op_name=..., source_range=...)
        """

        if node is None:
            return SignalResult.empty()

        kind_name = self._get_kind_name(node)
        if not kind_name:
            return SignalResult.empty()

        # === 新路径: 使用 _HANDLERS 单 dispatch ===
        if self._dispatch_enabled and kind_name in self._HANDLERS:
            # method 是已绑定的实例方法, 不再传 self
            return self._HANDLERS[kind_name](node)

        # === 旧路径 fallback: visit() + get_all_signals() ===
        import re

        # === Step 1: Try to find explicit extract_ method ===
        method_name = "extract_" + re.sub(r"(?<!^)(?=[A-Z])", "_", kind_name).lower()
        if hasattr(self, method_name):
            return getattr(self, method_name)(node)

        # === Step 2: Extract rich metadata ===
        op_name = None
        if hasattr(node, "op") and node.op:
            op_name = getattr(node.op, "name", None) or str(node.op)

        source_range = None
        if hasattr(node, "sourceRange") and node.sourceRange:
            sr = node.sourceRange
            try:
                source_range = ((sr.start.line, sr.start.column), (sr.end.line, sr.end.column))
            except Exception:
                pass

        # === Step 3: Extract primary signal (like visit()) ===
        primary = self.visit(node)

        # === Step 4: Extract all signals (like get_all_signals()) ===
        all_signals = self.get_all_signals(node)

        if not all_signals:
            all_signals = self._extract_all_signals_fallback(node)

        return SignalResult(
            primary=primary, all_signals=all_signals, kind_name=kind_name, op_name=op_name, source_range=source_range
        )

    def _extract_all_signals_fallback(self, node) -> list[str]:
        """Fallback for extracting all signals when no explicit handler exists"""
        if node is None:
            return []

        signals = []

        # Binary expression: left + right
        if hasattr(node, "left") and hasattr(node, "right"):
            left = getattr(node, "left", None)
            right = getattr(node, "right", None)
            if left:
                signals.extend(self.get_all_signals(left))
            if right:
                signals.extend(self.get_all_signals(right))
            return [s for s in signals if s]

        # General recursive fallback: try all child attributes
        for attr_name in dir(node):
            if attr_name.startswith("_"):
                continue
            try:
                attr = getattr(node, attr_name, None)
                if attr is None:
                    continue
                if callable(attr):
                    continue
                if isinstance(attr, list):
                    for item in attr:
                        if hasattr(item, "kind"):
                            signals.extend(self.get_all_signals(item))
                elif hasattr(attr, "kind"):
                    signals.extend(self.get_all_signals(attr))
            except Exception:
                pass

        return [s for s in signals if s]

    def get_all_signals(self, node) -> list[str]:
        """提取表达式中的所有信号名

        用于三元、拼接等返回多个信号的表达式。

        Args:
            node: AST 节点

        Returns:
            信号名列表
        """
        if node is None:
            return []

        kind = getattr(node, "kind", None)
        if kind is None:
            return []

        kind_name = kind.name if hasattr(kind, "name") else None

        # 处理返回多个信号的表达式类型
        if kind_name:
            method_name = f"get_all_{kind_name}"
            if hasattr(self, method_name):
                return getattr(self, method_name)(node)

            # 别名映射 (Syntax AST <-> Semantic AST 命名差异)
            alias_map = {
                "ConditionalExpression": "ConditionalOp",
                "ConcatenationExpression": "Concatenation",
                "BinaryOp": "binary_expression",
                "UnaryOp": "unary",
            }
            if kind_name in alias_map:
                alias = alias_map[kind_name]
                # [FIX] 方法名是 snake_case: ConditionalOp -> conditional_op
                import re

                snake_alias = re.sub(r"(?<!^)(?=[A-Z])", "_", alias).lower()
                method_name = f"get_all_{snake_alias}"
                if hasattr(self, method_name):
                    return getattr(self, method_name)(node)

            # [FIX] _Name 后缀去除: IdentifierSelectName -> IdentifierSelect
            # 对于 visit 方法分发，将 kind_name 的 '_Name' 后缀去掉后尝试
            if kind_name.endswith("Name"):
                alias = kind_name[:-4]  # 'IdentifierSelectName' -> 'IdentifierSelect'
                import re

                snake_alias = re.sub(r"(?<!^)(?=[A-Z])", "_", alias).lower()
                method_name = f"visit_{snake_alias}"
                if hasattr(self, method_name):
                    return getattr(self, method_name)(node)

            # [FIX] CamelCase kind_name 直接映射到 snake_case 方法
            # 例如: ConditionalOp -> get_all_conditional_op
            # 注意: 上面的 direct lookup already tried get_all_ConditionalOp (exact match)
            # 这里处理 CamelCase kind_name 转换为 snake_case 的情况
            import re

            snake_kind = re.sub(r"(?<!^)(?=[A-Z])", "_", kind_name).lower()
            method_name = f"get_all_{snake_kind}"
            if hasattr(self, method_name):
                return getattr(self, method_name)(node)

            # [FIX] ConditionalPredicate/Pattern 处理 - 从 conditions 提取
            if kind_name in ("ConditionalPredicate", "ConditionalPattern"):
                # ConditionalPattern 有 expr 属性
                if kind_name == "ConditionalPattern":
                    expr = getattr(node, "expr", None)
                    if expr:
                        return self.get_all_signals(expr)
                    return []
                # ConditionalPredicate 有 conditions 属性
                if kind_name == "ConditionalPredicate":
                    conditions = getattr(node, "conditions", None)
                    if conditions:
                        signals = []
                        for cond in conditions:
                            signals.extend(self.get_all_signals(cond))
                        return [s for s in signals if s]
                    return []

        # 兜底: 递归提取所有子节点信号 (用于二元、位选等表达式)
        return self.get_all_signals_fallback(node)

    def generic_visit(self, node) -> str | None:
        """默认递归进入子节点

        对于未实现的类型，尝试递归提取左操作数。
        [铁律26] 禁止 if-elif 链，使用 hasattr 检查
        """
        # [FIX] 二元表达式: left + right, left - right, etc.
        # 对于 get_all_signals，generic_visit 不会被调用（由调用方处理）
        # 对于 visit(单信号)，返回 left
        if hasattr(node, "left") and hasattr(node, "right"):
            left = getattr(node, "left", None)
            if left:
                return self.visit(left)

        # [FIX] NamedValue 等类型有 symbol 属性
        if hasattr(node, "symbol"):
            sym = getattr(node, "symbol", None)
            if sym:
                try:
                    _name = sym.name
                except (UnicodeDecodeError, TypeError, Exception):
                    _name = None
                if _name:
                    return self._safe_str(_name).strip()

        # [FIX] IntegerLiteralExpression: 直接返回字符串表示
        # [FIX 2026-06-26] use _safe_str to handle pyslang binary garbage
        kind = getattr(node, "kind", None)
        if kind and "IntegerLiteral" in str(kind):
            return self._safe_str(node).strip()

        return None

    def get_all_binary_expression(self, node) -> list[str]:
        """BinaryExpression: a + b, a & b 等

        递归提取左右操作数中的所有信号
        """
        signals = []
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            signals.extend(self.get_all_signals(left))
        if right:
            signals.extend(self.get_all_signals(right))
        return [s for s in signals if s]

    def get_all_unary(self, node) -> list[str]:
        """UnaryExpression: ~a, -a, !a 等

        递归提取操作数中的所有信号
        """
        operand = getattr(node, "operand", None) or getattr(node, "expression", None)
        if operand:
            return self.get_all_signals(operand)
        return []

    def get_all_streaming(self, node) -> list[str]:
        """StreamingExpression: {>>[a:b]} or {<<[a:b]}

        递归提取流操作符内的信号
        """
        # StreamingExpression has 'expression' or 'body' attribute
        expr = getattr(node, "expression", None) or getattr(node, "body", None)
        if expr:
            return self.get_all_signals(expr)
        return []

    def get_all_inside(self, node) -> list[str]:
        """InsideExpression: expr inside {a, b, c}

        递归提取左右操作数中的信号
        """
        signals = []
        left = getattr(node, "left", None) or getattr(node, "condition", None)
        right = getattr(node, "right", None) or getattr(node, "range", None)
        if left:
            signals.extend(self.get_all_signals(left))
        if right:
            signals.extend(self.get_all_signals(right))
        return [s for s in signals if s]

    def get_all_min_typ_max(self, node) -> list[str]:
        """MinTypMaxExpression: min:typ:max

        递归提取所有分支中的信号
        """
        signals = []
        min_val = getattr(node, "min", None) or getattr(node, "left", None)
        typ_val = getattr(node, "typ", None) or getattr(node, "value", None)
        max_val = getattr(node, "max", None) or getattr(node, "right", None)
        if min_val:
            signals.extend(self.get_all_signals(min_val))
        if typ_val:
            signals.extend(self.get_all_signals(typ_val))
        if max_val:
            signals.extend(self.get_all_signals(max_val))
        return [s for s in signals if s]

    def get_all_dist(self, node) -> list[str]:
        """DistExpression: a dist {[/=]:1, [:=]:2}

        递归提取分布项中的信号
        """
        signals = []
        # DistExpression may have 'items' or 'dist_items'
        items = getattr(node, "items", None) or getattr(node, "dist_items", None)
        if items:
            for item in items:
                # Each dist item may have 'value' and 'weight'
                val = getattr(item, "value", None) or getattr(item, "expr", None)
                if val:
                    signals.extend(self.get_all_signals(val))
        return [s for s in signals if s]

    def get_all_value_range(self, node) -> list[str]:
        """ValueRangeExpression: [a:b] or [a..b]

        递归提取范围边界中的信号
        """
        signals = []
        left = getattr(node, "left", None) or getattr(node, "low", None)
        right = getattr(node, "right", None) or getattr(node, "high", None)
        if left:
            signals.extend(self.get_all_signals(left))
        if right:
            signals.extend(self.get_all_signals(right))
        return [s for s in signals if s]

    def get_all_multiple_concatenation(self, node) -> list[str]:
        """MultipleConcatenationExpression: {{n{expr}}

        递归提取表达式中的信号
        """
        expr = getattr(node, "expression", None)
        if expr:
            return self.get_all_signals(expr)
        return []

    def get_all_stream_expression(self, node) -> list[str]:
        """StreamExpression: {>>[type]{expr}} or {<<[type]{expr}}

        递归提取表达式中的信号
        """
        expr = getattr(node, "expression", None) or getattr(node, "body", None)
        if expr:
            return self.get_all_signals(expr)
        return []

    def get_all_assignment_pattern(self, node) -> list[str]:
        """AssignmentPatternExpression: '{a, b, c}

        递归提取所有模式中的信号
        """
        signals = []
        patterns = getattr(node, "patterns", None) or getattr(node, "items", None)
        if patterns and hasattr(patterns, "__iter__") and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    signals.extend(self.get_all_signals(p))
        return [s for s in signals if s]

    def get_all_call(self, node) -> list[str]:
        """Call: 函数调用参数

        返回: [arg1, arg2, ...]
        """
        signals = []
        args = getattr(node, "arguments", None)

        if args:
            # Handle OrderedArgument vs NamedArgument
            for arg in args:
                if arg is None:
                    continue
                # NamedArgument has .name and .expr
                expr = getattr(arg, "expr", None) or getattr(arg, "value", None)
                if expr:
                    signals.extend(self.get_all_signals(expr))
                else:
                    # Maybe it's just an expression directly
                    signals.extend(self.get_all_signals(arg))

        return [s for s in signals if s]

    def get_all_element_select(self, node) -> list[str]:
        """ElementSelect: 位选择

        返回: [base[index]]
        """
        result = self.visit(node)
        return [result] if result else []

    def get_all_null_literal(self, node) -> list[str]:
        """NullLiteralExpression: null

        返回: []
        """
        return []

    def get_all_string_literal(self, node) -> list[str]:
        """StringLiteralExpression: "string"

        返回: []
        """
        return []

    def get_all_clock_event(self, node) -> list[str]:
        """ClockingEvent: @clk, @(posedge clk)

        提取事件控制中的所有信号
        """
        signals = []
        event = getattr(node, "event", None) or getattr(node, "clock", None)
        if event:
            signals.extend(self.get_all_signals(event))

        expr = getattr(node, "expression", None)
        if expr:
            signals.extend(self.get_all_signals(expr))

        return [s for s in signals if s]

    def get_all_empty_argument(self, node) -> list[str]:
        """EmptyArgument: 函数参数占位

        返回: []
        """
        return []

    def get_all_data_type(self, node) -> list[str]:
        """DataType: bit, logic, int

        返回: []
        """
        return []

    def get_all_type_reference(self, node) -> list[str]:
        """TypeReference: 类型引用

        返回: []
        """
        return []

    def get_all_time_literal(self, node) -> list[str]:
        """TimeLiteralExpression: 1ns, 1us

        返回: []
        """
        return []

    def get_all_real_literal(self, node) -> list[str]:
        """RealLiteralExpression: 1.5, 3.14

        返回: []
        """
        return []

    def get_all_unbased_unsized_integer_literal(self, node) -> list[str]:
        """UnbasedUnsizedIntegerLiteral: '0, '1, 'x, 'z

        返回: []
        """
        return []

    def get_all_unbounded_literal(self, node) -> list[str]:
        """UnboundedLiteral: $

        返回: []
        """
        return []

    def get_all_unary_operator(self, node) -> list[str]:
        """UnaryOperator: 一元运算符

        递归提取操作数
        """
        operand = getattr(node, "operand", None) or getattr(node, "expression", None)
        if operand:
            return self.get_all_signals(operand)
        return []

    def get_all_binary_operator(self, node) -> list[str]:
        """BinaryOperator: 二元运算符

        递归提取左右操作数
        """
        signals = []
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            signals.extend(self.get_all_signals(left))
        if right:
            signals.extend(self.get_all_signals(right))
        return [s for s in signals if s]

    def get_all_assignment_expression(self, node) -> list[str]:
        """AssignmentExpression: a = b

        递归提取左右操作数
        """
        signals = []
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            signals.extend(self.get_all_signals(left))
        if right:
            signals.extend(self.get_all_signals(right))
        return [s for s in signals if s]

    def get_all_new_class(self, node) -> list[str]:
        """NewClassExpression: new()

        返回: []
        """
        return []

    def get_all_new_array(self, node) -> list[str]:
        """NewArrayExpression: new[size]

        返回 size 中的信号
        """
        signals = []
        size = getattr(node, "size", None) or getattr(node, "expression", None)
        if size:
            signals.extend(self.get_all_signals(size))
        return [s for s in signals if s]

    def get_all_new_covergroup(self, node) -> list[str]:
        """NewCovergroupExpression: covergroup

        返回: []
        """
        return []

    def get_all_copy_class(self, node) -> list[str]:
        """CopyClassExpression: class.copy()

        返回: []
        """
        return []

    def get_all_arbitrary_symbol(self, node) -> list[str]:
        """ArbitrarySymbol: 未解析的符号

        返回符号名
        """
        name = getattr(node, "name", None)
        if name:
            return [str(name).strip()]
        return []

    def get_all_l_value_reference(self, node) -> list[str]:
        """LValueReference: 左值引用

        递归提取引用的信号
        """
        value = getattr(node, "value", None)
        if value:
            return self.get_all_signals(value)
        return []

    def get_all_assertion_instance(self, node) -> list[str]:
        """AssertionInstance: assert property

        返回: []
        """
        return []

    def get_all_invalid(self, node) -> list[str]:
        """Invalid: 无效节点

        返回: []
        """
        return []

    def get_all_member_access(self, node) -> list[str]:
        """MemberAccessExpression: p.addr -> 返回完整复合名 [p.addr]

        与 visit_member_access 保持一致，返回 base.member 格式。
        """
        value = getattr(node, "value", None) or getattr(node, "expression", None)
        member_sym = getattr(node, "member", None)

        if value and member_sym:
            base_signals = self.get_all_signals(value)
            base_name = base_signals[0] if base_signals else self.visit(value)

            member_name = self._safe_get_name(member_sym, None)
            if member_name:
                member_name = self._safe_str(member_name).strip()
            else:
                member_name = self._safe_str(member_sym).strip()

            if base_name and member_name:
                return [f"{base_name}.{member_name}"]

        if value:
            return self.get_all_signals(value)
        return []

    def get_all_signals_fallback(self, node) -> list[str]:
        """Fallback for get_all_signals when no specific method exists

        递归提取所有子节点的信号（用于二元、位选等表达式）
        """
        if node is None:
            return []

        signals = []

        # Binary expression: left + right
        if hasattr(node, "left") and hasattr(node, "right"):
            left = getattr(node, "left", None)
            right = getattr(node, "right", None)
            if left:
                signals.extend(self.get_all_signals(left))
            if right:
                signals.extend(self.get_all_signals(right))
            if signals:
                return [s for s in signals if s]

        # ElementSelect: data[5] -> recursively get signals from value
        if hasattr(node, "value"):
            value = getattr(node, "value", None)
            if value:
                signals.extend(self.get_all_signals(value))
                if signals:
                    return [s for s in signals if s]

        # Unary expression: operand (e.g., |a, &b, ~c)
        if hasattr(node, "operand"):
            operand = getattr(node, "operand", None)
            if operand:
                signals.extend(self.get_all_signals(operand))
                if signals:
                    return [s for s in signals if s]

        # InvocationExpression/Call: $floor(a), func(b) -> get arguments
        if hasattr(node, "arguments"):
            args = getattr(node, "arguments", None)
            if args:
                # ArgumentListSyntax has .parameters, not iterable directly
                params = getattr(args, "parameters", None)
                if params is not None:
                    # OrderedArgumentSyntax/ NamedArgumentSyntax
                    for p in params if hasattr(params, "__iter__") else [params]:
                        expr = getattr(p, "expr", None)
                        if expr:
                            signals.extend(self.get_all_signals(expr))
                else:
                    for arg in args:
                        if arg:
                            signals.extend(self.get_all_signals(arg))
                if signals:
                    return [s for s in signals if s]

        # Single signal fallback
        single = self.visit(node)
        return [single] if single else []

    # =========================================================================
    # [P0] 基础标识符 - 最常用，必须实现
    # =========================================================================

    def visit_identifier_name(self, node) -> str | None:
        """IdentifierName: 简单信号名

        结构: IdentifierName.identifier.value = "clk"
        """
        # [FIX 2026-06-26] pyslang partial elaboration: identifier.value is binary garbage
        ident = getattr(node, "identifier", None)
        if ident is None:
            logger.debug("[FALLBACK] IdentifierName missing 'identifier' attr")
            return None

        try:
            val = getattr(ident, "value", None)
        except (UnicodeDecodeError, RuntimeError) as e:
            if "mutex" in str(e).lower() or isinstance(e, UnicodeDecodeError):
                logger.debug("[FALLBACK] identifier.value lock/encoding fail")
                return None
            raise
        if val is None:
            logger.debug("[FALLBACK] IdentifierName.identifier missing 'value' attr")
            return None

        try:
            return self.adapter.clean_name(str(val).strip())
        except (UnicodeDecodeError, TypeError):
            logger.debug("[FALLBACK] identifier value not decodable")
            return None

    def visit_named_value(self, node) -> str | None:
        """NamedValue: 简单变量引用 din, data 等

        结构: NamedValueExpression.symbol = NetSymbol/VariableSymbol, 有 .name 属性
        """
        sym = getattr(node, "symbol", None)
        if sym:
            try:
                _name = sym.name
            except (UnicodeDecodeError, TypeError, Exception):
                _name = None
            if _name:
                return self._safe_str(_name).strip()
        # 兜底: symbol 没 name 则尝试直接转字符串
        if sym:
            try:
                name = str(sym).strip()
            except (UnicodeDecodeError, TypeError):
                return "<id:non-utf8>"
            # 可能是 "Symbol(SymbolKind.Net, \"data\")" 格式
            if "Symbol" in name and '"' in name:
                import re

                m = re.search(r'"([^"]+)"', name)
                if m:
                    return m.group(1)
            return name
        return None

    @on("EmptyArgument")
    def extract_empty_argument(self, node) -> SignalResult:
        """[NOT TESTED] EmptyArgument: 函数参数占位"""
        return SignalResult()

    @on("TypeReference")
    def extract_type_reference(self, node) -> SignalResult:
        """[NOT TESTED] TypeReference: 类型引用"""
        return SignalResult()

    @on("DelayControl")
    def extract_delay_control(self, node) -> SignalResult:
        """[NOT TESTED] DelayControl: #1delay"""
        expr = getattr(node, "expression", None)
        if expr:
            return self.extract(expr)
        return SignalResult()

    @on("EventControl")
    def extract_event_control(self, node) -> SignalResult:
        """[NOT TESTED] EventControl: @event"""
        event = getattr(node, "event", None)
        if event:
            return self.extract(event)
        return SignalResult()

    @on("DisableConstraint")
    def extract_disable_constraint(self, node) -> SignalResult:
        """[NOT TESTED] DisableConstraint: disable constraint"""
        expr = getattr(node, "expr", None) or getattr(node, "constraint", None)
        if expr:
            return self.extract(expr)
        return SignalResult()

    @on("SolveBeforeConstraint")
    def extract_solve_before_constraint(self, node) -> SignalResult:
        """[NOT TESTED] SolveBeforeConstraint: solve before constraint"""
        result = SignalResult()
        before = getattr(node, "before", None)
        after = getattr(node, "after", None)
        if before:
            result = result.merge(self.extract(before))
        if after:
            result = result.merge(self.extract(after))
        return result

    @on("WildcardPattern")
    def extract_wildcard_pattern(self, node) -> SignalResult:
        """[NOT TESTED] WildcardPattern: wildcard pattern"""
        return SignalResult()

    @on("TaggedPattern")
    def extract_tagged_pattern(self, node) -> SignalResult:
        """[NOT TESTED] TaggedPattern: tagged pattern"""
        result = SignalResult()
        pattern = getattr(node, "pattern", None)
        if pattern:
            result = result.merge(self.extract(pattern))
        return result

    @on("EmptyStatement")
    def extract_empty_statement(self, node) -> SignalResult:
        """[NOT TESTED] EmptyStatement: empty statement"""
        return SignalResult()

    @on("SequenceRepetition")
    def extract_sequence_repetition(self, node) -> SignalResult:
        """[NOT TESTED] SequenceRepetition: seq[*1:3]"""
        seq = getattr(node, "sequence", None) or getattr(node, "operand", None)
        if seq:
            return self.extract(seq)
        return SignalResult()

    @on("LetDeclaration")
    def extract_let_declaration(self, node) -> SignalResult:
        """[NOT TESTED] LetDeclaration: let declaration"""
        result = SignalResult()
        args = getattr(node, "arguments", None)
        if args and hasattr(args, "__iter__"):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        body = getattr(node, "body", None) or getattr(node, "expr", None)
        if body:
            result = result.merge(self.extract(body))
        return result

    @on("ProceduralAssignStatement")
    def extract_procedural_assign_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ProceduralAssignStatement: procedural assign"""
        result = SignalResult()
        lvalue = getattr(node, "lvalue", None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, "rvalue", None) or getattr(node, "expr", None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result

    @on("ProceduralForceStatement")
    def extract_procedural_force_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ProceduralForceStatement: procedural force"""
        lvalue = getattr(node, "lvalue", None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()

    @on("ImplicitEventControl")
    def extract_implicit_event_control(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitEventControl: @@"""
        return SignalResult()

    @on("WaitForkStatement")
    def extract_wait_fork_statement(self, node) -> SignalResult:
        """[NOT TESTED] WaitForkStatement: wait fork"""
        return SignalResult()

    @on("WaitOrderStatement")
    def extract_wait_order_statement(self, node) -> SignalResult:
        """[NOT TESTED] WaitOrderStatement: wait order"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("ProceduralDeassignStatement")
    def extract_procedural_deassign_statement(self, node) -> SignalResult:
        """[NOT TESTED] ProceduralDeassignStatement: procedural deassign"""
        lvalue = getattr(node, "lvalue", None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()

    @on("RandCaseStatement")
    def extract_rand_case_statement(self, node) -> SignalResult:
        """[NOT TESTED] RandCaseStatement: rand case"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("RandCaseItem")
    def extract_rand_case_item(self, node) -> SignalResult:
        """[NOT TESTED] RandCaseItem: rand case item"""
        result = SignalResult()
        cond = getattr(node, "condition", None) or getattr(node, "weight", None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, "body", None) or getattr(node, "statement", None)
        if body:
            result = result.merge(self.extract(body))
        return result

    @on("VariablePattern")
    def extract_variable_pattern(self, node) -> SignalResult:
        """[NOT TESTED] VariablePattern: variable pattern"""
        var = getattr(node, "var", None) or getattr(node, "expr", None)
        if var:
            return self.extract(var)
        return SignalResult()

    @on("StructurePattern")
    def extract_structure_pattern(self, node) -> SignalResult:
        """[NOT TESTED] StructurePattern: structure pattern"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "patterns", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    # Assertion expr kinds
    @on("AndSequenceExpr")
    def extract_and_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] AndSequenceExpr: and sequence expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    @on("OrSequenceExpr")
    def extract_or_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] OrSequenceExpr: or sequence expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    @on("FirstMatchSequenceExpr")
    def extract_first_match_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] FirstMatchSequenceExpr: first_match sequence expression"""
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            return self.extract(seq)
        return SignalResult()

    @on("ClockingSequenceExpr")
    def extract_clocking_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] ClockingSequenceExpr: clocking sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            result = result.merge(self.extract(seq))
        clock = getattr(node, "clock", None)
        if clock:
            result = result.merge(self.extract(clock))
        return result

    # More SyntaxKind expression handlers
    @on("BitType")
    def extract_bit_type(self, node) -> SignalResult:
        """[NOT TESTED] BitType: bit type"""
        return SignalResult()

    @on("ByteType")
    def extract_byte_type(self, node) -> SignalResult:
        """[NOT TESTED] ByteType: byte type"""
        return SignalResult()

    @on("CHandleType")
    def extract_chandle_type(self, node) -> SignalResult:
        """[NOT TESTED] CHandleType: chandle type"""
        return SignalResult()

    @on("IntType")
    def extract_int_type(self, node) -> SignalResult:
        """[NOT TESTED] IntType: int type"""
        return SignalResult()

    @on("LongIntType")
    def extract_long_int_type(self, node) -> SignalResult:
        """[NOT TESTED] LongIntType: longint type"""
        return SignalResult()

    @on("ShortIntType")
    def extract_short_int_type(self, node) -> SignalResult:
        """[NOT TESTED] ShortIntType: shortint type"""
        return SignalResult()

    @on("IntegerType")
    def extract_integer_type(self, node) -> SignalResult:
        """[NOT TESTED] IntegerType: integer type"""
        return SignalResult()

    @on("LogicType")
    def extract_logic_type(self, node) -> SignalResult:
        """[NOT TESTED] LogicType: logic type"""
        return SignalResult()

    @on("RegType")
    def extract_reg_type(self, node) -> SignalResult:
        """[NOT TESTED] RegType: reg type"""
        return SignalResult()

    @on("StringType")
    def extract_string_type(self, node) -> SignalResult:
        """[NOT TESTED] StringType: string type"""
        return SignalResult()

    @on("EventType")
    def extract_event_type(self, node) -> SignalResult:
        """[NOT TESTED] EventType: event type"""
        return SignalResult()

    @on("VoidType")
    def extract_void_type(self, node) -> SignalResult:
        """[NOT TESTED] VoidType: void type"""
        return SignalResult()

    @on("RealType")
    def extract_real_type(self, node) -> SignalResult:
        """[NOT TESTED] RealType: real type"""
        return SignalResult()

    @on("ShortRealType")
    def extract_short_real_type(self, node) -> SignalResult:
        """[NOT TESTED] ShortRealType: shortreal type"""
        return SignalResult()

    @on("SequenceType")
    def extract_sequence_type(self, node) -> SignalResult:
        """[NOT TESTED] SequenceType: sequence type"""
        return SignalResult()

    # Statement-related
    @on("CoverSequenceStatement")
    def extract_cover_sequence_statement(self, node) -> SignalResult:
        """[NOT TESTED] CoverSequenceStatement: cover sequence statement"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            result = result.merge(self.extract(seq))
        return result

    @on("WithinSequenceExpr")
    def extract_within_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] WithinSequenceExpr: within sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            result = result.merge(self.extract(seq))
        within = getattr(node, "within", None) or getattr(node, "expr2", None)
        if within:
            result = result.merge(self.extract(within))
        return result

    @on("ThroughoutSequenceExpr")
    def extract_throughout_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] ThroughoutSequenceExpr: throughout sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            result = result.merge(self.extract(seq))
        throughout = getattr(node, "throughout", None) or getattr(node, "expr2", None)
        if throughout:
            result = result.merge(self.extract(throughout))
        return result

    @on("ConstraintBlock")
    def extract_constraint_block(self, node) -> SignalResult:
        """[NOT TESTED] ConstraintBlock: constraint block"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "constraints", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("ConstraintDeclaration")
    def extract_constraint_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ConstraintDeclaration: constraint declaration"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "constraints", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("ConstraintPrototype")
    def extract_constraint_prototype(self, node) -> SignalResult:
        """[NOT TESTED] ConstraintPrototype: constraint prototype"""
        return SignalResult()

    # Class-related expressions
    @on("CheckerDeclaration")
    def extract_checker_declaration(self, node) -> SignalResult:
        """[NOT TESTED] CheckerDeclaration: checker declaration"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("CheckerInstantiation")
    def extract_checker_instantiation(self, node) -> SignalResult:
        """[NOT TESTED] CheckerInstantiation: checker instantiation"""
        result = SignalResult()
        args = getattr(node, "arguments", None)
        if args and hasattr(args, "__iter__"):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result

    @on("CheckerDataDeclaration")
    def extract_checker_data_declaration(self, node) -> SignalResult:
        """[NOT TESTED] CheckerDataDeclaration: checker data declaration"""
        return SignalResult()

    # Coverage-related
    @on("CoverageBins")
    def extract_coverage_bins(self, node) -> SignalResult:
        """[NOT TESTED] CoverageBins: coverage bins"""
        result = SignalResult()
        value = getattr(node, "value", None) or getattr(node, "expr", None)
        if value:
            result = result.merge(self.extract(value))
        return result

    @on("CoverageBinsArraySize")
    def extract_coverage_bins_array_size(self, node) -> SignalResult:
        """[NOT TESTED] CoverageBinsArraySize: coverage bins array size"""
        result = SignalResult()
        size = getattr(node, "size", None) or getattr(node, "expr", None)
        if size:
            result = result.merge(self.extract(size))
        return result

    @on("DefaultCoverageBinInitializer")
    def extract_default_coverage_bin_initializer(self, node) -> SignalResult:
        """[NOT TESTED] DefaultCoverageBinInitializer: default coverage bin initializer"""
        return SignalResult()

    @on("ElabSystemTask")
    def extract_elab_system_task(self, node) -> SignalResult:
        """[NOT TESTED] ElabSystemTask: elaboration system task"""
        result = SignalResult()
        args = getattr(node, "arguments", None)
        if args and hasattr(args, "__iter__"):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result

    # Bind directive
    @on("BindDirective")
    def extract_bind_directive(self, node) -> SignalResult:
        """[NOT TESTED] BindDirective: bind directive"""
        result = SignalResult()
        target = getattr(node, "target", None) or getattr(node, "expr", None)
        if target:
            result = result.merge(self.extract(target))
        return result

    @on("BindTargetList")
    def extract_bind_target_list(self, node) -> SignalResult:
        """[NOT TESTED] BindTargetList: bind target list"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    # Default function port
    @on("DefaultFunctionPort")
    def extract_default_function_port(self, node) -> SignalResult:
        """[NOT TESTED] DefaultFunctionPort: default function port"""
        return SignalResult()

    # Case and generate constructs
    @on("CaseStatement")
    def extract_case_statement_stmt(self, node) -> SignalResult:
        """[NOT TESTED] CaseStatement: case statement"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "condition", None)
        if expr:
            result = result.merge(self.extract(expr))
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("DefaultCaseItem")
    def extract_default_case_item(self, node) -> SignalResult:
        """[NOT TESTED] DefaultCaseItem: default case item"""
        result = SignalResult()
        stmts = getattr(node, "statements", None) or getattr(node, "body", None)
        if stmts and hasattr(stmts, "__iter__"):
            for stmt in stmts:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("AssertionItemPort")
    def extract_assertion_item_port(self, node) -> SignalResult:
        """[NOT TESTED] AssertionItemPort: assertion item port"""
        return SignalResult()

    @on("AssertionItemPortList")
    def extract_assertion_item_port_list(self, node) -> SignalResult:
        """[NOT TESTED] AssertionItemPortList: assertion item port list"""
        return SignalResult()

    @on("CovergroupDeclaration")
    def extract_covergroup_declaration(self, node) -> SignalResult:
        """[NOT TESTED] CovergroupDeclaration: covergroup declaration"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "coverpoints", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("Coverpoint")
    def extract_coverpoint(self, node) -> SignalResult:
        """[NOT TESTED] Coverpoint: coverpoint"""
        result = SignalResult()
        transition = getattr(node, "transition", None) or getattr(node, "expr", None)
        if transition:
            result = result.merge(self.extract(transition))
        return result

    @on("CoverCross")
    def extract_cover_cross(self, node) -> SignalResult:
        """[NOT TESTED] CoverCross: cover cross"""
        return SignalResult()

    @on("CoverageOption")
    def extract_coverage_option(self, node) -> SignalResult:
        """[NOT TESTED] CoverageOption: coverage option"""
        return SignalResult()

    @on("CoverageIffClause")
    def extract_coverage_iff_clause(self, node) -> SignalResult:
        """[NOT TESTED] CoverageIffClause: coverage iff clause"""
        expr = getattr(node, "expr", None) or getattr(node, "condition", None)
        if expr:
            return self.extract(expr)
        return SignalResult()

    @on("BlockCoverageEvent")
    def extract_block_coverage_event(self, node) -> SignalResult:
        """[NOT TESTED] BlockCoverageEvent: block coverage event"""
        return SignalResult()

    # Bad and invalid expressions
    @on("BlockingEventTriggerStatement")
    def extract_blocking_event_trigger_statement(self, node) -> SignalResult:
        """[NOT TESTED] BlockingEventTriggerStatement: blocking event trigger"""
        event = getattr(node, "event", None) or getattr(node, "expr", None)
        if event:
            return self.extract(event)
        return SignalResult()

    # Default disable declaration
    @on("DefaultDisableDeclaration")
    def extract_default_disable_declaration(self, node) -> SignalResult:
        """[NOT TESTED] DefaultDisableDeclaration: default disable declaration"""
        expr = getattr(node, "expr", None) or getattr(node, "disable", None)
        if expr:
            return self.extract(expr)
        return SignalResult()

    # Conditional pattern
    @on("AnonymousProgram")
    def extract_anonymous_program(self, node) -> SignalResult:
        """[NOT TESTED] AnonymousProgram: anonymous program"""
        return SignalResult()

    # Extern interface method
    @on("ModportDeclaration")
    def extract_modport_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ModportDeclaration: modport declaration"""
        return SignalResult()

    @on("ModportItem")
    def extract_modport_item(self, node) -> SignalResult:
        """[NOT TESTED] ModportItem: modport item"""
        result = SignalResult()
        signal = getattr(node, "signal", None) or getattr(node, "expr", None)
        if signal:
            result = result.merge(self.extract(signal))
        return result

    @on("FunctionDeclaration")
    def extract_function_declaration(self, node) -> SignalResult:
        """[NOT TESTED] FunctionDeclaration: function declaration"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("TaskDeclaration")
    def extract_task_declaration(self, node) -> SignalResult:
        """[NOT TESTED] TaskDeclaration: task declaration"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("FunctionPrototype")
    def extract_function_prototype(self, node) -> SignalResult:
        """[NOT TESTED] FunctionPrototype: function prototype"""
        return SignalResult()

    @on("ModuleDeclaration")
    def extract_module_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ModuleDeclaration: module declaration"""
        return SignalResult()

    @on("InterfaceDeclaration")
    def extract_interface_declaration(self, node) -> SignalResult:
        """[NOT TESTED] InterfaceDeclaration: interface declaration"""
        return SignalResult()

    @on("ProgramDeclaration")
    def extract_program_declaration_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ProgramDeclaration: program declaration"""
        return SignalResult()

    # Generate constructs
    @on("ContinuousAssign")
    def extract_continuous_assign(self, node) -> SignalResult:
        """[NOT TESTED] ContinuousAssign: continuous assignment"""
        result = SignalResult()
        lvalue = getattr(node, "lvalue", None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, "rvalue", None) or getattr(node, "expr", None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result

    @on("PortDeclaration")
    def extract_port_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PortDeclaration: port declaration"""
        result = SignalResult()
        init = getattr(node, "init", None) or getattr(node, "value", None)
        if init:
            result = result.merge(self.extract(init))
        return result

    @on("ReturnStatement")
    def extract_return_statement(self, node) -> SignalResult:
        """[NOT TESTED] ReturnStatement: return statement"""
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            return self.extract(expr)
        return SignalResult()

    @on("DisableStatement")
    def extract_disable_statement(self, node) -> SignalResult:
        """[NOT TESTED] DisableStatement: disable statement"""
        return SignalResult()

    # Wait statements
    @on("WaitStatement")
    def extract_wait_statement_stmt(self, node) -> SignalResult:
        """[NOT TESTED] WaitStatement: wait statement"""
        cond = getattr(node, "cond", None) or getattr(node, "expression", None)
        if cond:
            return self.extract(cond)
        return SignalResult()

    @on("RandSequenceStatement")
    def extract_rand_sequence_statement(self, node) -> SignalResult:
        """[NOT TESTED] RandSequenceStatement: rand sequence statement"""
        return SignalResult()

    # Immediate assertion statements
    @on("ImmediateAssertStatement")
    def extract_immediate_assert_statement(self, node) -> SignalResult:
        """[NOT TESTED] ImmediateAssertStatement: immediate assert statement"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, "action", None)
        if action:
            result = result.merge(self.extract(action))
        return result

    @on("ImmediateAssumeStatement")
    def extract_immediate_assume_statement(self, node) -> SignalResult:
        """[NOT TESTED] ImmediateAssumeStatement: immediate assume statement"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result

    @on("ImmediateCoverStatement")
    def extract_immediate_cover_statement(self, node) -> SignalResult:
        """[NOT TESTED] ImmediateCoverStatement: immediate cover statement"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result

    # Deferred assertion statements
    @on("ForVariableDeclaration")
    def extract_for_variable_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ForVariableDeclaration: for loop variable declaration"""
        result = SignalResult()
        var = getattr(node, "variable", None) or getattr(node, "var", None)
        if var:
            result = result.merge(self.extract(var))
        init = getattr(node, "init", None) or getattr(node, "expr", None)
        if init:
            result = result.merge(self.extract(init))
        return result

    @on("ForeverStatement")
    def extract_forever_statement(self, node) -> SignalResult:
        """[NOT TESTED] ForeverStatement: forever statement"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statement", None)
        if body:
            result = result.merge(self.extract(body))
        return result

    @on("LoopConstraint")
    def extract_loop_constraint_stmt(self, node) -> SignalResult:
        """[NOT TESTED] LoopConstraint: loop constraint"""
        result = SignalResult()
        vars_ = getattr(node, "variables", None) or getattr(node, "loop_vars", None)
        if vars_ and hasattr(vars_, "__iter__"):
            for v in vars_:
                if v:
                    result = result.merge(self.extract(v))
        constraint = getattr(node, "constraint", None) or getattr(node, "body", None)
        if constraint:
            result = result.merge(self.extract(constraint))
        return result

    # Jump statements
    @on("JumpStatement")
    def extract_jump_statement(self, node) -> SignalResult:
        """[NOT TESTED] JumpStatement: break, continue, return, disable statements"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "value", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    # Return statement
    @on("DisableForkStatement")
    def extract_disable_fork_statement(self, node) -> SignalResult:
        """[NOT TESTED] DisableForkStatement: disable fork statement"""
        return SignalResult()

    # Wait statement
    @on("ProceduralReleaseStatement")
    def extract_procedural_release_statement(self, node) -> SignalResult:
        """[NOT TESTED] ProceduralReleaseStatement: procedural release statement"""
        return SignalResult()

    # Event trigger statements
    @on("NonblockingEventTriggerStatement")
    def extract_nonblocking_event_trigger_statement(self, node) -> SignalResult:
        """[NOT TESTED] NonblockingEventTriggerStatement: nonblocking event trigger ->>"""
        return SignalResult()

    # Property expressions
    @on("SimpleSequenceExpr")
    def extract_simple_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] SimpleSequenceExpr: simple sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            return self.extract(seq)
        return result

    @on("DelayedSequenceExpr")
    def extract_delayed_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] DelayedSequenceExpr: delayed sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            result = result.merge(self.extract(seq))
        return result

    @on("DelayedSequenceElement")
    def extract_delayed_sequence_element(self, node) -> SignalResult:
        """[NOT TESTED] DelayedSequenceElement: delayed sequence element"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("SequenceMatchList")
    def extract_sequence_match_list(self, node) -> SignalResult:
        """[NOT TESTED] SequenceMatchList: sequence match list"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("IntersectSequenceExpr")
    def extract_intersect_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] IntersectSequenceExpr: intersect sequence expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    @on("ParenthesizedSequenceExpr")
    def extract_parenthesized_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedSequenceExpr: parenthesized sequence expression"""
        result = SignalResult()
        seq = getattr(node, "sequence", None) or getattr(node, "expr", None)
        if seq:
            return self.extract(seq)
        return result

    @on("SequenceDeclaration")
    def extract_sequence_declaration_stmt(self, node) -> SignalResult:
        """[NOT TESTED] SequenceDeclaration: sequence declaration"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "body", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("DataDeclaration")
    def extract_data_declaration(self, node) -> SignalResult:
        """[NOT TESTED] DataDeclaration: data declaration (variables, nets)"""
        result = SignalResult()
        items = getattr(node, "declarators", None) or getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("NetDeclaration")
    def extract_net_declaration(self, node) -> SignalResult:
        """[NOT TESTED] NetDeclaration: net declaration"""
        result = SignalResult()
        items = getattr(node, "declarators", None) or getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("TypedefDeclaration")
    def extract_typedef_declaration_stmt(self, node) -> SignalResult:
        """[NOT TESTED] TypedefDeclaration: typedef declaration"""
        return SignalResult()

    @on("ForwardTypedefDeclaration")
    def extract_forward_typedef_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ForwardTypedefDeclaration: forward typedef declaration"""
        return SignalResult()

    @on("FunctionPort")
    def extract_function_port(self, node) -> SignalResult:
        """[NOT TESTED] FunctionPort: function port"""
        result = SignalResult()
        var = getattr(node, "variable", None) or getattr(node, "var", None)
        if var:
            result = result.merge(self.extract(var))
        return result

    @on("FunctionPortList")
    def extract_function_port_list(self, node) -> SignalResult:
        """[NOT TESTED] FunctionPortList: function port list"""
        result = SignalResult()
        ports = getattr(node, "ports", None)
        if ports and hasattr(ports, "__iter__"):
            for port in ports:
                if port:
                    result = result.merge(self.extract(port))
        return result

    @on("LocalVariableDeclaration")
    def extract_local_variable_declaration(self, node) -> SignalResult:
        """[NOT TESTED] LocalVariableDeclaration: local variable declaration"""
        result = SignalResult()
        var = getattr(node, "variable", None) or getattr(node, "var", None)
        if var:
            result = result.merge(self.extract(var))
        return result

    @on("GenvarDeclaration")
    def extract_genvar_declaration(self, node) -> SignalResult:
        """[NOT TESTED] GenvarDeclaration: genvar declaration"""
        return SignalResult()

    @on("NetTypeDeclaration")
    def extract_net_type_declaration(self, node) -> SignalResult:
        """[NOT TESTED] NetTypeDeclaration: net type declaration"""
        return SignalResult()

    @on("ClockingDeclaration")
    def extract_clocking_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ClockingDeclaration: clocking block declaration"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("ClockingDirection")
    def extract_clocking_direction(self, node) -> SignalResult:
        """[NOT TESTED] ClockingDirection: clocking direction"""
        return SignalResult()

    @on("ClockingItem")
    def extract_clocking_item(self, node) -> SignalResult:
        """[NOT TESTED] ClockingItem: clocking item"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "body", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("ClockingSkew")
    def extract_clocking_skew(self, node) -> SignalResult:
        """[NOT TESTED] ClockingSkew: clocking skew"""
        return SignalResult()

    @on("DefaultClockingReference")
    def extract_default_clocking_reference(self, node) -> SignalResult:
        """[NOT TESTED] DefaultClockingReference: default clocking reference"""
        return SignalResult()

    @on("TimeUnitsDeclaration")
    def extract_time_units_declaration(self, node) -> SignalResult:
        """[NOT TESTED] TimeUnitsDeclaration: time units declaration"""
        return SignalResult()

    # Modport declarations
    @on("ModportSimplePortList")
    def extract_modport_simple_port_list(self, node) -> SignalResult:
        """[NOT TESTED] ModportSimplePortList: modport simple port list"""
        result = SignalResult()
        ports = getattr(node, "ports", None)
        if ports and hasattr(ports, "__iter__"):
            for port in ports:
                if port:
                    result = result.merge(self.extract(port))
        return result

    @on("ModportSubroutinePortList")
    def extract_modport_subroutine_port_list(self, node) -> SignalResult:
        """[NOT TESTED] ModportSubroutinePortList: modport subroutine port list"""
        result = SignalResult()
        ports = getattr(node, "ports", None)
        if ports and hasattr(ports, "__iter__"):
            for port in ports:
                if port:
                    result = result.merge(self.extract(port))
        return result

    @on("ModportClockingPort")
    def extract_modport_clocking_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportClockingPort: modport clocking port"""
        return SignalResult()

    @on("ModportExplicitPort")
    def extract_modport_explicit_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportExplicitPort: modport explicit port"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "signal", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    @on("ModportNamedPort")
    def extract_modport_named_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportNamedPort: modport named port"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "signal", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    # Interface port header
    @on("InterfacePortHeader")
    def extract_interface_port_header(self, node) -> SignalResult:
        """[NOT TESTED] InterfacePortHeader: interface port header"""
        return SignalResult()

    @on("InterfaceHeader")
    def extract_interface_header_stmt(self, node) -> SignalResult:
        """[NOT TESTED] InterfaceHeader: interface header"""
        return SignalResult()

    @on("ModuleHeader")
    def extract_module_header(self, node) -> SignalResult:
        """[NOT TESTED] ModuleHeader: module header"""
        result = SignalResult()
        params = getattr(node, "parameters", None)
        if params and hasattr(params, "__iter__"):
            for p in params:
                if p:
                    result = result.merge(self.extract(p))
        return result

    @on("ProgramHeader")
    def extract_program_header(self, node) -> SignalResult:
        """[NOT TESTED] ProgramHeader: program header"""
        return SignalResult()

    # Block statements
    @on("AlwaysBlock")
    def extract_always_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysBlock: always block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("AlwaysCombBlock")
    def extract_always_comb_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysCombBlock: always_comb block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("AlwaysFFBlock")
    def extract_always_ff_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysFFBlock: always_ff block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("AlwaysLatchBlock")
    def extract_always_latch_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysLatchBlock: always_latch block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("InitialBlock")
    def extract_initial_block(self, node) -> SignalResult:
        """[NOT TESTED] InitialBlock: initial block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("FinalBlock")
    def extract_final_block(self, node) -> SignalResult:
        """[NOT TESTED] FinalBlock: final block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("SequentialBlockStatement")
    def extract_sequential_block_statement(self, node) -> SignalResult:
        """[NOT TESTED] SequentialBlockStatement: sequential block statement"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("ParallelBlockStatement")
    def extract_parallel_block_statement(self, node) -> SignalResult:
        """[NOT TESTED] ParallelBlockStatement: parallel block statement"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("ActionBlock")
    def extract_action_block(self, node) -> SignalResult:
        """[NOT TESTED] ActionBlock: action block"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statement", None)
        if body:
            result = result.merge(self.extract(body))
        return result

    @on("RsCodeBlock")
    def extract_rs_code_block(self, node) -> SignalResult:
        """[NOT TESTED] RsCodeBlock: randsequence code block"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("RsCase")
    def extract_rs_case(self, node) -> SignalResult:
        """[NOT TESTED] RsCase: randsequence case"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("RsElseClause")
    def extract_rs_else_clause(self, node) -> SignalResult:
        """[NOT TESTED] RsElseClause: randsequence else clause"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "block", None)
        if body:
            result = result.merge(self.extract(body))
        return result

    @on("RsWeightClause")
    def extract_rs_weight_clause(self, node) -> SignalResult:
        """[NOT TESTED] RsWeightClause: randsequence weight clause"""
        return SignalResult()

    # Expression patterns
    @on("PatternCaseItem")
    def extract_pattern_case_item(self, node) -> SignalResult:
        """[NOT TESTED] PatternCaseItem: pattern case item"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "patterns", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    # Streaming expressions
    @on("WithClause")
    def extract_with_clause(self, node) -> SignalResult:
        """[NOT TESTED] WithClause: with clause"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "function", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    @on("WithFunctionClause")
    def extract_with_function_clause(self, node) -> SignalResult:
        """[NOT TESTED] WithFunctionClause: with function clause"""
        result = SignalResult()
        func = getattr(node, "function", None) or getattr(node, "expr", None)
        if func:
            result = result.merge(self.extract(func))
        return result

    @on("WithFunctionSample")
    def extract_with_function_sample(self, node) -> SignalResult:
        """[NOT TESTED] WithFunctionSample: with function sample"""
        return SignalResult()

    # Queue and literal expressions
    @on("StandardCaseItem")
    def extract_standard_case_item(self, node) -> SignalResult:
        """[NOT TESTED] StandardCaseItem: standard case item"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("DefaultRsCaseItem")
    def extract_default_rs_case_item(self, node) -> SignalResult:
        """[NOT TESTED] DefaultRsCaseItem: default randsequence case item"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "block", None)
        if body:
            result = result.merge(self.extract(body))
        return result

    @on("StandardRsCaseItem")
    def extract_standard_rs_case_item(self, node) -> SignalResult:
        """[NOT TESTED] StandardRsCaseItem: standard randsequence case item"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    # Clause expressions
    @on("IntersectClause")
    def extract_intersect_clause(self, node) -> SignalResult:
        """[NOT TESTED] IntersectClause: intersect clause"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("EqualsTypeClause")
    def extract_equals_type_clause(self, node) -> SignalResult:
        """[NOT TESTED] EqualsTypeClause: equals type clause"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "type", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("EqualsValueClause")
    def extract_equals_value_clause(self, node) -> SignalResult:
        """[NOT TESTED] EqualsValueClause: equals value clause"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "value", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    # More clauses and expressions
    @on("ElseClause")
    def extract_else_clause(self, node) -> SignalResult:
        """[NOT TESTED] ElseClause: else clause"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statement", None)
        if body:
            result = result.merge(self.extract(body))
        return result

    @on("ElseConstraintClause")
    def extract_else_constraint_clause(self, node) -> SignalResult:
        """[NOT TESTED] ElseConstraintClause: else constraint clause"""
        result = SignalResult()
        constraint = getattr(node, "constraint", None) or getattr(node, "body", None)
        if constraint:
            result = result.merge(self.extract(constraint))
        return result

    @on("ImplementsClause")
    def extract_implements_clause(self, node) -> SignalResult:
        """[NOT TESTED] ImplementsClause: implements clause"""
        return SignalResult()

    @on("ExtendsClause")
    def extract_extends_clause(self, node) -> SignalResult:
        """[NOT TESTED] ExtendsClause: extends clause"""
        return SignalResult()

    @on("IfNonePathDeclaration")
    def extract_if_none_path_declaration(self, node) -> SignalResult:
        """[NOT TESTED] IfNonePathDeclaration: ifnone path declaration"""
        return SignalResult()

    @on("PathDeclaration")
    def extract_path_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PathDeclaration: path declaration"""
        return SignalResult()

    @on("PulseStyleDeclaration")
    def extract_pulse_style_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PulseStyleDeclaration: pulse style declaration"""
        return SignalResult()

    @on("MatchesClause")
    def extract_matches_clause(self, node) -> SignalResult:
        """[NOT TESTED] MatchesClause: matches clause"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("EqualsAssertionArgClause")
    def extract_equals_assertion_arg_clause(self, node) -> SignalResult:
        """[NOT TESTED] EqualsAssertionArgClause: equals assertion arg clause"""
        return SignalResult()

    @on("IffEventClause")
    def extract_iff_event_clause(self, node) -> SignalResult:
        """[NOT TESTED] IffEventClause: iff event clause"""
        return SignalResult()

    @on("NamedBlockClause")
    def extract_named_block_clause(self, node) -> SignalResult:
        """[NOT TESTED] NamedBlockClause: named block clause"""
        return SignalResult()

    @on("DividerClause")
    def extract_divider_clause(self, node) -> SignalResult:
        """[NOT TESTED] DividerClause: divider clause"""
        return SignalResult()

    @on("RandJoinClause")
    def extract_rand_join_clause(self, node) -> SignalResult:
        """[NOT TESTED] RandJoinClause: rand join clause"""
        return SignalResult()

    @on("DefaultExtendsClauseArg")
    def extract_default_extends_clause_arg(self, node) -> SignalResult:
        """[NOT TESTED] DefaultExtendsClauseArg: default extends clause arg"""
        return SignalResult()

    @on("TimingCheckEventArg")
    def extract_timing_check_event_arg(self, node) -> SignalResult:
        """[NOT TESTED] TimingCheckEventArg: timing check event arg"""
        return SignalResult()

    @on("TimingCheckEventCondition")
    def extract_timing_check_event_condition(self, node) -> SignalResult:
        """[NOT TESTED] TimingCheckEventCondition: timing check event condition"""
        return SignalResult()

    @on("ConfigDeclaration")
    def extract_config_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ConfigDeclaration: config declaration"""
        return SignalResult()

    @on("ConfigUseClause")
    def extract_config_use_clause(self, node) -> SignalResult:
        """[NOT TESTED] ConfigUseClause: config use clause"""
        return SignalResult()

    @on("ExternModuleDecl")
    def extract_extern_module_decl(self, node) -> SignalResult:
        """[NOT TESTED] ExternModuleDecl: extern module declaration"""
        return SignalResult()

    @on("IdWithExprCoverageBinInitializer")
    def extract_id_with_expr_coverage_bin_initializer(self, node) -> SignalResult:
        """[NOT TESTED] IdWithExprCoverageBinInitializer: id with expr coverage bin initializer"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    @on("ImplicationConstraint")
    def extract_implication_constraint(self, node) -> SignalResult:
        """[NOT TESTED] ImplicationConstraint: implication constraint"""
        result = SignalResult()
        left = getattr(node, "left", None) or getattr(node, "condition", None)
        right = getattr(node, "right", None) or getattr(node, "constraint", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result

    @on("LibraryDeclaration")
    def extract_library_declaration(self, node) -> SignalResult:
        """[NOT TESTED] LibraryDeclaration: library declaration"""
        return SignalResult()

    @on("LibraryIncDirClause")
    def extract_library_inc_dir_clause(self, node) -> SignalResult:
        """[NOT TESTED] LibraryIncDirClause: library include directory clause"""
        return SignalResult()

    @on("ModportSubroutinePort")
    def extract_modport_subroutine_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportSubroutinePort: modport subroutine port"""
        return SignalResult()

    @on("SpecifyBlock")
    def extract_specify_block(self, node) -> SignalResult:
        """[NOT TESTED] SpecifyBlock: specify block"""
        return SignalResult()

    @on("SpecparamDeclaration")
    def extract_specparam_declaration(self, node) -> SignalResult:
        """[NOT TESTED] SpecparamDeclaration: specparam declaration"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "value", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    @on("TimingControlStatement")
    def extract_timing_control_statement(self, node) -> SignalResult:
        """[NOT TESTED] TimingControlStatement: timing control statement"""
        return SignalResult()

    @on("UdpDeclaration")
    def extract_udp_declaration(self, node) -> SignalResult:
        """[NOT TESTED] UdpDeclaration: UDP declaration (Verilog primitive)"""
        return SignalResult()

    @on("UniquenessConstraint")
    def extract_uniqueness_constraint(self, node) -> SignalResult:
        """[NOT TESTED] UniquenessConstraint: uniqueness constraint"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("UserDefinedNetDeclaration")
    def extract_user_defined_net_declaration(self, node) -> SignalResult:
        """[NOT TESTED] UserDefinedNetDeclaration: user defined net declaration"""
        return SignalResult()

    @on("VirtualInterfaceType")
    def extract_virtual_interface_type(self, node) -> SignalResult:
        """[NOT TESTED] VirtualInterfaceType: virtual interface type"""
        return SignalResult()

    @on("UnconnectedDriveDirective")
    def extract_unconnecteddrivedirective(self, node) -> SignalResult:
        """[NOT TESTED] UnconnectedDriveDirective: Unconnecteddrivedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UndefDirective")
    def extract_undefdirective(self, node) -> SignalResult:
        """[NOT TESTED] UndefDirective: Undefdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UndefineAllDirective")
    def extract_undefinealldirective(self, node) -> SignalResult:
        """[NOT TESTED] UndefineAllDirective: Undefinealldirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UnionType")
    def extract_uniontype(self, node) -> SignalResult:
        """[NOT TESTED] UnionType: Uniontype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("Unknown")
    def extract_unknown(self, node) -> SignalResult:
        """[NOT TESTED] Unknown: Unknown"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("Untyped")
    def extract_untyped(self, node) -> SignalResult:
        """[NOT TESTED] Untyped: Untyped"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("VariablePortHeader")
    def extract_variableportheader(self, node) -> SignalResult:
        """[NOT TESTED] VariablePortHeader: Variableportheader"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("WildcardDimensionSpecifier")
    def extract_wildcarddimensionspecifier(self, node) -> SignalResult:
        """[NOT TESTED] WildcardDimensionSpecifier: Wildcarddimensionspecifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("WildcardPortConnection")
    def extract_wildcardportconnection(self, node) -> SignalResult:
        """[NOT TESTED] WildcardPortConnection: Wildcardportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("WildcardPortList")
    def extract_wildcardportlist(self, node) -> SignalResult:
        """[NOT TESTED] WildcardPortList: Wildcardportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("WildcardUdpPortList")
    def extract_wildcardudpportlist(self, node) -> SignalResult:
        """[NOT TESTED] WildcardUdpPortList: Wildcardudpportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("StructType")
    def extract_structtype(self, node) -> SignalResult:
        """[NOT TESTED] StructType: Structtype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("SuperHandle")
    def extract_superhandle(self, node) -> SignalResult:
        """[NOT TESTED] SuperHandle: Superhandle"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("SystemName")
    def extract_systemname(self, node) -> SignalResult:
        """[NOT TESTED] SystemName: Systemname"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("SystemTimingCheck")
    def extract_systemtimingcheck(self, node) -> SignalResult:
        """[NOT TESTED] SystemTimingCheck: Systemtimingcheck"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ThisHandle")
    def extract_thishandle(self, node) -> SignalResult:
        """[NOT TESTED] ThisHandle: Thishandle"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("TimeScaleDirective")
    def extract_timescaledirective(self, node) -> SignalResult:
        """[NOT TESTED] TimeScaleDirective: Timescaledirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("TimeType")
    def extract_timetype(self, node) -> SignalResult:
        """[NOT TESTED] TimeType: Timetype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("TokenList")
    def extract_tokenlist(self, node) -> SignalResult:
        """[NOT TESTED] TokenList: Tokenlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("TransListCoverageBinInitializer")
    def extract_translistcoveragebininitializer(self, node) -> SignalResult:
        """[NOT TESTED] TransListCoverageBinInitializer: Translistcoveragebininitializer"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("TransSet")
    def extract_transset(self, node) -> SignalResult:
        """[NOT TESTED] TransSet: Transset"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UdpBody")
    def extract_udpbody(self, node) -> SignalResult:
        """[NOT TESTED] UdpBody: Udpbody"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UdpEntry")
    def extract_udpentry(self, node) -> SignalResult:
        """[NOT TESTED] UdpEntry: Udpentry"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UdpInitialStmt")
    def extract_udpinitialstmt(self, node) -> SignalResult:
        """[NOT TESTED] UdpInitialStmt: Udpinitialstmt"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UdpInputPortDecl")
    def extract_udpinputportdecl(self, node) -> SignalResult:
        """[NOT TESTED] UdpInputPortDecl: Udpinputportdecl"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UdpOutputPortDecl")
    def extract_udpoutputportdecl(self, node) -> SignalResult:
        """[NOT TESTED] UdpOutputPortDecl: Udpoutputportdecl"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("PragmaDirective")
    def extract_pragmadirective(self, node) -> SignalResult:
        """[NOT TESTED] PragmaDirective: Pragmadirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("PrimitiveInstantiation")
    def extract_primitiveinstantiation(self, node) -> SignalResult:
        """[NOT TESTED] PrimitiveInstantiation: Primitiveinstantiation"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("Production")
    def extract_production(self, node) -> SignalResult:
        """[NOT TESTED] Production: Production"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ProtectDirective")
    def extract_protectdirective(self, node) -> SignalResult:
        """[NOT TESTED] ProtectDirective: Protectdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ProtectedDirective")
    def extract_protecteddirective(self, node) -> SignalResult:
        """[NOT TESTED] ProtectedDirective: Protecteddirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("PullStrength")
    def extract_pullstrength(self, node) -> SignalResult:
        """[NOT TESTED] PullStrength: Pullstrength"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("QueueDimensionSpecifier")
    def extract_queuedimensionspecifier(self, node) -> SignalResult:
        """[NOT TESTED] QueueDimensionSpecifier: Queuedimensionspecifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("RealTimeType")
    def extract_realtimetype(self, node) -> SignalResult:
        """[NOT TESTED] RealTimeType: Realtimetype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ResetAllDirective")
    def extract_resetalldirective(self, node) -> SignalResult:
        """[NOT TESTED] ResetAllDirective: Resetalldirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("RsIfElse")
    def extract_rsifelse(self, node) -> SignalResult:
        """[NOT TESTED] RsIfElse: Rsifelse"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("RsProdItem")
    def extract_rsproditem(self, node) -> SignalResult:
        """[NOT TESTED] RsProdItem: Rsproditem"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("RsRule")
    def extract_rsrule(self, node) -> SignalResult:
        """[NOT TESTED] RsRule: Rsrule"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("SimplePathSuffix")
    def extract_simplepathsuffix(self, node) -> SignalResult:
        """[NOT TESTED] SimplePathSuffix: Simplepathsuffix"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("SpecparamDeclarator")
    def extract_specparamdeclarator(self, node) -> SignalResult:
        """[NOT TESTED] SpecparamDeclarator: Specparamdeclarator"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NamedLabel")
    def extract_namedlabel(self, node) -> SignalResult:
        """[NOT TESTED] NamedLabel: Namedlabel"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NamedPortConnection")
    def extract_namedportconnection(self, node) -> SignalResult:
        """[NOT TESTED] NamedPortConnection: Namedportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NetAlias")
    def extract_netalias(self, node) -> SignalResult:
        """[NOT TESTED] NetAlias: Netalias"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NetPortHeader")
    def extract_netportheader(self, node) -> SignalResult:
        """[NOT TESTED] NetPortHeader: Netportheader"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NoUnconnectedDriveDirective")
    def extract_nounconnecteddrivedirective(self, node) -> SignalResult:
        """[NOT TESTED] NoUnconnectedDriveDirective: Nounconnecteddrivedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NonAnsiPortList")
    def extract_nonansiportlist(self, node) -> SignalResult:
        """[NOT TESTED] NonAnsiPortList: Nonansiportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NonAnsiUdpPortList")
    def extract_nonansiudpportlist(self, node) -> SignalResult:
        """[NOT TESTED] NonAnsiUdpPortList: Nonansiudpportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("OneStepDelay")
    def extract_onestepdelay(self, node) -> SignalResult:
        """[NOT TESTED] OneStepDelay: Onestepdelay"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("OrderedArgument")
    def extract_orderedargument(self, node) -> SignalResult:
        """[NOT TESTED] OrderedArgument: Orderedargument"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("OrderedPortConnection")
    def extract_orderedportconnection(self, node) -> SignalResult:
        """[NOT TESTED] OrderedPortConnection: Orderedportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ParenthesizedPattern")
    def extract_parenthesizedpattern(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedPattern: Parenthesizedpattern"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("PathDescription")
    def extract_pathdescription(self, node) -> SignalResult:
        """[NOT TESTED] PathDescription: Pathdescription"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("PortReference")
    def extract_portreference(self, node) -> SignalResult:
        """[NOT TESTED] PortReference: Portreference"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("IdentifierSelectName")
    def extract_identifier_select_name(self, node) -> SignalResult:
        """[MIGRATED] IdentifierSelectName: data[3] etc with bit/range select

        From visit_identifier_select - handles complex selectors
        """
    @on("IdentifierSelectName")
    def extract_identifier_select_name(self, node) -> SignalResult:
        """[MIGRATED] IdentifierSelectName: data[3] etc with bit/range select

        From visit_identifier_select - handles complex selectors
        """
        base_name = self._extract_identifier_base_name(node)
        if not base_name:
            return SignalResult()
        base_name = self._apply_selectors_to_base_name(node, base_name)
        clean_name = self.adapter.clean_name(base_name) if base_name else None
        return SignalResult(primary=clean_name) if clean_name else SignalResult()

    def _extract_identifier_base_name(self, node) -> str:
        """[REFACTOR A-PR1 2026-06-26] 提取 IdentifierSelectName 节点 base name."""
        if hasattr(node, "identifier"):
            ident = node.identifier
            if hasattr(ident, "value"):
                base_name = str(ident.value).strip()
            else:
                base_name = str(ident).strip()

        if not base_name:
            base_name = str(node).strip().split("[")[0]
        return base_name

    def _apply_selectors_to_base_name(self, node, base_name: str) -> str:
        """[REFACTOR A-PR1 2026-06-26] 处理 selectors (bit/range select) → 返回带 [N] / [M:N] 的 base_name."""
        selectors = getattr(node, "selectors", None)
        if not (selectors and hasattr(selectors, "__iter__") and not isinstance(selectors, str)):
            return base_name
        for i in range(len(selectors)):
            sel = selectors[i]
            sel_kind = str(getattr(sel, "kind", ""))

            if "ElementSelect" in sel_kind:
                bit_select = getattr(sel, "selector", None)
                if bit_select:
                    bit_select_kind = str(getattr(bit_select, "kind", ""))

                    if "SimpleRange" in bit_select_kind:
                        left_expr = getattr(bit_select, "left", None)
                        right_expr = getattr(bit_select, "right", None)

                        param_map = self._get_param_map()
                        left_val = self._evaluate_expr(left_expr, param_map) if left_expr else None
                        right_val = self._evaluate_expr(right_expr, param_map) if right_expr else None

                        if left_val is not None or right_val is not None:
                            left_str = str(left_val) if left_val is not None else "?"
                            right_str = str(right_val) if right_val is not None else "?"
                            base_name = f"{base_name}[{left_str}:{right_str}]"
                            return base_name
                    else:
                        selector_expr = getattr(bit_select, "expr", None)
                        if selector_expr:
                            param_map = self._get_param_map()
                            evaluated = self._evaluate_expr(selector_expr, param_map)
                            if evaluated is not None:
                                base_name = f"{base_name}[{evaluated}]"
                                return base_name

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
                        base_name = f"{base_name}[{left_str}:{right_str}]"
                        return base_name
        return base_name


    def extract_identifierselectname(self, node) -> SignalResult:
        """[NOT TESTED] IdentifierSelectName: Identifierselectname"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("IfDefDirective")
    def extract_ifdefdirective(self, node) -> SignalResult:
        """[NOT TESTED] IfDefDirective: Ifdefdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("IfNDefDirective")
    def extract_ifndefdirective(self, node) -> SignalResult:
        """[NOT TESTED] IfNDefDirective: Ifndefdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ImplicitType")
    def extract_implicittype(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitType: Implicittype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("IncludeDirective")
    def extract_includedirective(self, node) -> SignalResult:
        """[NOT TESTED] IncludeDirective: Includedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("LibraryIncludeStatement")
    def extract_libraryincludestatement(self, node) -> SignalResult:
        """[NOT TESTED] LibraryIncludeStatement: Libraryincludestatement"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("LibraryMap")
    def extract_librarymap(self, node) -> SignalResult:
        """[NOT TESTED] LibraryMap: Librarymap"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("LineDirective")
    def extract_linedirective(self, node) -> SignalResult:
        """[NOT TESTED] LineDirective: Linedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("MacroActualArgument")
    def extract_macroactualargument(self, node) -> SignalResult:
        """[NOT TESTED] MacroActualArgument: Macroactualargument"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("MacroActualArgumentList")
    def extract_macroactualargumentlist(self, node) -> SignalResult:
        """[NOT TESTED] MacroActualArgumentList: Macroactualargumentlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("MacroArgumentDefault")
    def extract_macroargumentdefault(self, node) -> SignalResult:
        """[NOT TESTED] MacroArgumentDefault: Macroargumentdefault"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("MacroFormalArgument")
    def extract_macroformalargument(self, node) -> SignalResult:
        """[NOT TESTED] MacroFormalArgument: Macroformalargument"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("MacroFormalArgumentList")
    def extract_macroformalargumentlist(self, node) -> SignalResult:
        """[NOT TESTED] MacroFormalArgumentList: Macroformalargumentlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("MacroUsage")
    def extract_macrousage(self, node) -> SignalResult:
        """[NOT TESTED] MacroUsage: Macrousage"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NamedArgument")
    def extract_namedargument(self, node) -> SignalResult:
        """[NOT TESTED] NamedArgument: Namedargument"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ElsIfDirective")
    def extract_elsifdirective(self, node) -> SignalResult:
        """[NOT TESTED] ElsIfDirective: Elsifdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ElseDirective")
    def extract_elsedirective(self, node) -> SignalResult:
        """[NOT TESTED] ElseDirective: Elsedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EmptyNonAnsiPort")
    def extract_emptynonansiport(self, node) -> SignalResult:
        """[NOT TESTED] EmptyNonAnsiPort: Emptynonansiport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EmptyPortConnection")
    def extract_emptyportconnection(self, node) -> SignalResult:
        """[NOT TESTED] EmptyPortConnection: Emptyportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EmptyTimingCheckArg")
    def extract_emptytimingcheckarg(self, node) -> SignalResult:
        """[NOT TESTED] EmptyTimingCheckArg: Emptytimingcheckarg"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EndCellDefineDirective")
    def extract_endcelldefinedirective(self, node) -> SignalResult:
        """[NOT TESTED] EndCellDefineDirective: Endcelldefinedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EndIfDirective")
    def extract_endifdirective(self, node) -> SignalResult:
        """[NOT TESTED] EndIfDirective: Endifdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EndKeywordsDirective")
    def extract_endkeywordsdirective(self, node) -> SignalResult:
        """[NOT TESTED] EndKeywordsDirective: Endkeywordsdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EndProtectDirective")
    def extract_endprotectdirective(self, node) -> SignalResult:
        """[NOT TESTED] EndProtectDirective: Endprotectdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EndProtectedDirective")
    def extract_endprotecteddirective(self, node) -> SignalResult:
        """[NOT TESTED] EndProtectedDirective: Endprotecteddirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EnumType")
    def extract_enumtype(self, node) -> SignalResult:
        """[NOT TESTED] EnumType: Enumtype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ExplicitAnsiPort")
    def extract_explicitansiport(self, node) -> SignalResult:
        """[NOT TESTED] ExplicitAnsiPort: Explicitansiport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ExplicitNonAnsiPort")
    def extract_explicitnonansiport(self, node) -> SignalResult:
        """[NOT TESTED] ExplicitNonAnsiPort: Explicitnonansiport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ExternUdpDecl")
    def extract_externudpdecl(self, node) -> SignalResult:
        """[NOT TESTED] ExternUdpDecl: Externudpdecl"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("FilePathSpec")
    def extract_filepathspec(self, node) -> SignalResult:
        """[NOT TESTED] FilePathSpec: Filepathspec"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ForwardTypeRestriction")
    def extract_forwardtyperestriction(self, node) -> SignalResult:
        """[NOT TESTED] ForwardTypeRestriction: Forwardtyperestriction"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("HierarchyInstantiation")
    def extract_hierarchyinstantiation(self, node) -> SignalResult:
        """[NOT TESTED] HierarchyInstantiation: Hierarchyinstantiation"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DefaultConfigRule")
    def extract_defaultconfigrule(self, node) -> SignalResult:
        """[NOT TESTED] DefaultConfigRule: Defaultconfigrule"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DefaultDecayTimeDirective")
    def extract_defaultdecaytimedirective(self, node) -> SignalResult:
        """[NOT TESTED] DefaultDecayTimeDirective: Defaultdecaytimedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DefaultNetTypeDirective")
    def extract_defaultnettypedirective(self, node) -> SignalResult:
        """[NOT TESTED] DefaultNetTypeDirective: Defaultnettypedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DefaultSkewItem")
    def extract_defaultskewitem(self, node) -> SignalResult:
        """[NOT TESTED] DefaultSkewItem: Defaultskewitem"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DefaultTriregStrengthDirective")
    def extract_defaulttriregstrengthdirective(self, node) -> SignalResult:
        """[NOT TESTED] DefaultTriregStrengthDirective: Defaulttriregstrengthdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DeferredAssertion")
    def extract_deferredassertion(self, node) -> SignalResult:
        """[NOT TESTED] DeferredAssertion: Deferredassertion"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DefineDirective")
    def extract_definedirective(self, node) -> SignalResult:
        """[NOT TESTED] DefineDirective: Definedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("Delay3")
    def extract_delay3(self, node) -> SignalResult:
        """[NOT TESTED] Delay3: Delay3"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DelayModePathDirective")
    def extract_delaymodepathdirective(self, node) -> SignalResult:
        """[NOT TESTED] DelayModePathDirective: Delaymodepathdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DelayModeUnitDirective")
    def extract_delaymodeunitdirective(self, node) -> SignalResult:
        """[NOT TESTED] DelayModeUnitDirective: Delaymodeunitdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DelayModeZeroDirective")
    def extract_delaymodezerodirective(self, node) -> SignalResult:
        """[NOT TESTED] DelayModeZeroDirective: Delaymodezerodirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DisableIff")
    def extract_disableiff(self, node) -> SignalResult:
        """[NOT TESTED] DisableIff: Disableiff"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DriveStrength")
    def extract_drivestrength(self, node) -> SignalResult:
        """[NOT TESTED] DriveStrength: Drivestrength"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EdgeControlSpecifier")
    def extract_edgecontrolspecifier(self, node) -> SignalResult:
        """[NOT TESTED] EdgeControlSpecifier: Edgecontrolspecifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EdgeDescriptor")
    def extract_edgedescriptor(self, node) -> SignalResult:
        """[NOT TESTED] EdgeDescriptor: Edgedescriptor"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EdgeSensitivePathSuffix")
    def extract_edgesensitivepathsuffix(self, node) -> SignalResult:
        """[NOT TESTED] EdgeSensitivePathSuffix: Edgesensitivepathsuffix"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("AnsiPortList")
    def extract_ansiportlist(self, node) -> SignalResult:
        """[NOT TESTED] AnsiPortList: Ansiportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("AnsiUdpPortList")
    def extract_ansiudpportlist(self, node) -> SignalResult:
        """[NOT TESTED] AnsiUdpPortList: Ansiudpportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ArgumentList")
    def extract_argumentlist(self, node) -> SignalResult:
        """[NOT TESTED] ArgumentList: Argumentlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("AttributeSpec")
    def extract_attributespec(self, node) -> SignalResult:
        """[NOT TESTED] AttributeSpec: Attributespec"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("BeginKeywordsDirective")
    def extract_beginkeywordsdirective(self, node) -> SignalResult:
        """[NOT TESTED] BeginKeywordsDirective: Beginkeywordsdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("CellConfigRule")
    def extract_cellconfigrule(self, node) -> SignalResult:
        """[NOT TESTED] CellConfigRule: Cellconfigrule"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("CellDefineDirective")
    def extract_celldefinedirective(self, node) -> SignalResult:
        """[NOT TESTED] CellDefineDirective: Celldefinedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ChargeStrength")
    def extract_chargestrength(self, node) -> SignalResult:
        """[NOT TESTED] ChargeStrength: Chargestrength"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("CompilationUnit")
    def extract_compilationunit(self, node) -> SignalResult:
        """[NOT TESTED] CompilationUnit: Compilationunit"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ConfigCellIdentifier")
    def extract_configcellidentifier(self, node) -> SignalResult:
        """[NOT TESTED] ConfigCellIdentifier: Configcellidentifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ConfigLiblist")
    def extract_configliblist(self, node) -> SignalResult:
        """[NOT TESTED] ConfigLiblist: Configliblist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ConstructorName")
    def extract_constructorname(self, node) -> SignalResult:
        """[NOT TESTED] ConstructorName: Constructorname"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("CycleDelay")
    def extract_cycledelay(self, node) -> SignalResult:
        """[NOT TESTED] CycleDelay: Cycledelay"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DPIExport")
    def extract_dpiexport(self, node) -> SignalResult:
        """[NOT TESTED] DPIExport: Dpiexport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DPIImport")
    def extract_dpiimport(self, node) -> SignalResult:
        """[NOT TESTED] DPIImport: Dpiimport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DefParam")
    def extract_defparam(self, node) -> SignalResult:
        """[NOT TESTED] DefParam: Defparam"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("Declarator")
    def extract_declarator(self, node) -> SignalResult:
        """[NOT TESTED] Declarator: variable declarator"""
        result = SignalResult()
        name = getattr(node, "name", None) or getattr(node, "symbol", None)
        if name:
            if hasattr(name, "name"):
                result.add_signal(str(name.name))
            else:
                result.add_signal(str(name))
        return result

    @on("ImplicitAnsiPort")
    def extract_implicit_ansi_port(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitAnsiPort: implicit ansi port"""
        result = SignalResult()
        name = getattr(node, "name", None)
        if name:
            result.add_signal(str(name))
        return result

    @on("ImplicitNonAnsiPort")
    def extract_implicit_non_ansi_port(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitNonAnsiPort: implicit non-ansi port"""
        result = SignalResult()
        name = getattr(node, "name", None)
        if name:
            result.add_signal(str(name))
        return result

    @on("NamedType")
    def extract_named_type(self, node) -> SignalResult:
        """[NOT TESTED] NamedType: named type"""
        result = SignalResult()
        name = getattr(node, "name", None)
        if name:
            result.add_signal(str(name))
        return result

    @on("SeparatedList")
    def extract_separated_list(self, node) -> SignalResult:
        """[NOT TESTED] SeparatedList: separated list"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "elements", None)
        if items:
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("SyntaxList")
    def extract_syntax_list(self, node) -> SignalResult:
        """[NOT TESTED] SyntaxList: syntax list"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "elements", None)
        if items:
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
