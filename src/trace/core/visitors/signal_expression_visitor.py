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
from .port_visitor import PortVisitor
from .sequence_visitor import SequenceVisitor
from .declaration_visitor import DeclarationVisitor
from .statement_visitor import StatementVisitor
from .type_visitor import TypeVisitor
from .directive_visitor import DirectiveVisitor
from .expression_visitor import ExpressionVisitor
from .generate_visitor import GenerateVisitor
from .operator_visitor import OperatorVisitor
from .signal_result import SignalResult

logger = logging.getLogger(__name__)


class SignalExpressionVisitor(BaseVisitor, OperatorVisitor, MemberVisitor, PortVisitor, GenerateVisitor, ExpressionVisitor, DeclarationVisitor, StatementVisitor, TypeVisitor, DirectiveVisitor, SequenceVisitor):
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

    @on("DelayControl")
    def extract_delay_control(self, node) -> SignalResult:
        """[NOT TESTED] DelayControl: #1delay"""
        expr = getattr(node, "expression", None)
        if expr:
            return self.extract(expr)
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

    @on("ConstraintPrototype")
    def extract_constraint_prototype(self, node) -> SignalResult:
        """[NOT TESTED] ConstraintPrototype: constraint prototype"""
        return SignalResult()

    # Class-related expressions
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

    # Case and generate constructs
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

    @on("FunctionPrototype")
    def extract_function_prototype(self, node) -> SignalResult:
        """[NOT TESTED] FunctionPrototype: function prototype"""
        return SignalResult()

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

    # Interface port header
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

    @on("ConfigUseClause")
    def extract_config_use_clause(self, node) -> SignalResult:
        """[NOT TESTED] ConfigUseClause: config use clause"""
        return SignalResult()

    @on("ExternModuleDecl")
    def extract_extern_module_decl(self, node) -> SignalResult:
        """[NOT TESTED] ExternModuleDecl: extern module declaration"""
        return SignalResult()

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

    @on("LibraryIncDirClause")
    def extract_library_inc_dir_clause(self, node) -> SignalResult:
        """[NOT TESTED] LibraryIncDirClause: library include directory clause"""
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
