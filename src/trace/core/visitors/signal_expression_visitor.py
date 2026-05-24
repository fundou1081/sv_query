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
from typing import List, Optional, Dict, Any, Callable, ClassVar
import logging

from .base_visitor import BaseVisitor
from .signal_result import SignalResult

logger = logging.getLogger(__name__)


def on(kind_name: str):
    """注册 handler 的装饰器
    
    用法:
        @on('BinaryOp')
        def handle_binary_op(self, node):
            ...
    """
    def decorator(func):
        func._kind_name = kind_name
        return func
    return decorator


class SignalExpressionVisitor(BaseVisitor):
    """信号/表达式提取 Visitor
    
    负责将 AST 节点转换为信号名或信号列表。
    使用 Visitor 模式，每个语法类型对应独立的 visit 方法。
    
    单 dispatch 重构:
        使用 @on('KindName') 装饰器注册 handler，
        extract() 统一入口分派到对应的 handler。
    
    使用方式:
        visitor = SignalExpressionVisitor(adapter)
        signal_name = visitor.visit(node)
        all_signals = visitor.get_all_signals(node)
        result = visitor.extract(node)  # 统一入口 (推荐)
    """
    
    # 单 dispatch: handler 注册表
    _HANDLERS: ClassVar[Dict[str, Callable]] = {}
    
    # 双轨控制: True=新 handler, False=旧方法回退
    _dispatch_enabled: bool = False
    
    def __init__(self, adapter):
        """初始化
        
        Args:
            adapter: PyslangAdapter 实例，用于清理名称和访问模块参数
        """
        super().__init__()
        self.adapter = adapter
        
        # 收集 @on 装饰的 handler
        self._collect_handlers()
    
    def _collect_handlers(self):
        """收集所有 @on 装饰的 handler 到 _HANDLERS"""
        for name in dir(self):
            if name.startswith('_'):
                continue
            method = getattr(self, name, None)
            if callable(method) and hasattr(method, '_kind_name'):
                kind_name = method._kind_name
                self._HANDLERS[kind_name] = method
                logger.debug(f"Registered handler: {kind_name} -> {name}")
    
    def _get_kind_name(self, node) -> Optional[str]:
        """获取节点的 kind 名称"""
        if node is None:
            return None
        kind = getattr(node, 'kind', None)
        if kind and hasattr(kind, 'name'):
            return kind.name
        return None
    
    # =========================================================================
    # 主入口方法
    # =========================================================================
    
    def visit(self, node) -> Optional[str]:
        """主入口：分发到对应的 visit 方法
        
        Args:
            node: AST 节点
            
        Returns:
            信号名字符串，或 None
        """
        if node is None:
            return None
        
        kind = getattr(node, 'kind', None)
        if kind is None:
            return None
        
        kind_name = kind.name if hasattr(kind, 'name') else None
        if kind_name:
            import re
            # 首先尝试直接转换 (IdentifierName -> visit_identifier_name)
            method_name = "visit_" + re.sub(r'(?<!^)(?=[A-Z])', '_', kind_name).lower()
            if hasattr(self, method_name):
                return getattr(self, method_name)(node)
            
            # 别名映射 (Syntax AST <-> Semantic AST 命名差异)
            # BinaryOp -> binary_expression, UnaryOp -> unary
            alias_map = {
                'BinaryOp': 'binary_expression',
                'UnaryOp': 'unary',
                'ConditionalExpression': 'conditional_op',
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
        from typing import List
        
        if node is None:
            return SignalResult.empty()
        
        kind_name = self._get_kind_name(node)
        if not kind_name:
            return SignalResult.empty()
        
        # === 新路径: 使用 _HANDLERS 单 dispatch ===
        if self._dispatch_enabled and kind_name in self._HANDLERS:
            return self._HANDLERS[kind_name](self, node)
        
        # === 旧路径 fallback: visit() + get_all_signals() ===
        import re
        
        # === Step 1: Try to find explicit extract_ method ===
        method_name = "extract_" + re.sub(r'(?<!^)(?=[A-Z])', '_', kind_name).lower()
        if hasattr(self, method_name):
            return getattr(self, method_name)(node)
        
        # === Step 2: Extract rich metadata ===
        op_name = None
        if hasattr(node, 'op') and node.op:
            op_name = getattr(node.op, 'name', None) or str(node.op)
        
        source_range = None
        if hasattr(node, 'sourceRange') and node.sourceRange:
            sr = node.sourceRange
            try:
                source_range = ((sr.start.line, sr.start.column), (sr.end.line, sr.end.column))
            except:
                pass
        
        # === Step 3: Extract primary signal (like visit()) ===
        primary = self.visit(node)
        
        # === Step 4: Extract all signals (like get_all_signals()) ===
        all_signals = self.get_all_signals(node)
        
        if not all_signals:
            all_signals = self._extract_all_signals_fallback(node)
        
        return SignalResult(
            primary=primary,
            all_signals=all_signals,
            kind_name=kind_name,
            op_name=op_name,
            source_range=source_range
        )
    
    def _extract_all_signals_fallback(self, node) -> List[str]:
        """Fallback for extracting all signals when no explicit handler exists"""
        if node is None:
            return []
        
        signals = []
        
        # Binary expression: left + right
        if hasattr(node, 'left') and hasattr(node, 'right'):
            left = getattr(node, 'left', None)
            right = getattr(node, 'right', None)
            if left:
                signals.extend(self.get_all_signals(left))
            if right:
                signals.extend(self.get_all_signals(right))
            return [s for s in signals if s]
        
        # General recursive fallback: try all child attributes
        for attr_name in dir(node):
            if attr_name.startswith('_'):
                continue
            try:
                attr = getattr(node, attr_name, None)
                if attr is None:
                    continue
                if callable(attr):
                    continue
                if isinstance(attr, list):
                    for item in attr:
                        if hasattr(item, 'kind'):
                            signals.extend(self.get_all_signals(item))
                elif hasattr(attr, 'kind'):
                    signals.extend(self.get_all_signals(attr))
            except:
                pass
        
        return [s for s in signals if s]
    
    def get_all_signals(self, node) -> List[str]:
        """提取表达式中的所有信号名
        
        用于三元、拼接等返回多个信号的表达式。
        
        Args:
            node: AST 节点
            
        Returns:
            信号名列表
        """
        if node is None:
            return []
        
        kind = getattr(node, 'kind', None)
        if kind is None:
            return []
        
        kind_name = kind.name if hasattr(kind, 'name') else None
        
        # 处理返回多个信号的表达式类型
        if kind_name:
            method_name = f"get_all_{kind_name}"
            if hasattr(self, method_name):
                return getattr(self, method_name)(node)
            
            # 别名映射 (Syntax AST <-> Semantic AST 命名差异)
            alias_map = {
                'ConditionalExpression': 'ConditionalOp',
                'ConcatenationExpression': 'Concatenation',
                'BinaryOp': 'binary_expression',
                'UnaryOp': 'unary',
            }
            if kind_name in alias_map:
                alias = alias_map[kind_name]
                # [FIX] 方法名是 snake_case: ConditionalOp -> conditional_op
                import re
                snake_alias = re.sub(r'(?<!^)(?=[A-Z])', '_', alias).lower()
                method_name = f"get_all_{snake_alias}"
                if hasattr(self, method_name):
                    return getattr(self, method_name)(node)
            
            # [FIX] _Name 后缀去除: IdentifierSelectName -> IdentifierSelect
            # 对于 visit 方法分发，将 kind_name 的 '_Name' 后缀去掉后尝试
            if kind_name.endswith('Name'):
                alias = kind_name[:-4]  # 'IdentifierSelectName' -> 'IdentifierSelect'
                import re
                snake_alias = re.sub(r'(?<!^)(?=[A-Z])', '_', alias).lower()
                method_name = f"visit_{snake_alias}"
                if hasattr(self, method_name):
                    return getattr(self, method_name)(node)
            
            # [FIX] CamelCase kind_name 直接映射到 snake_case 方法
            # 例如: ConditionalOp -> get_all_conditional_op
            # 注意: 上面的 direct lookup already tried get_all_ConditionalOp (exact match)
            # 这里处理 CamelCase kind_name 转换为 snake_case 的情况
            import re
            snake_kind = re.sub(r'(?<!^)(?=[A-Z])', '_', kind_name).lower()
            method_name = f"get_all_{snake_kind}"
            if hasattr(self, method_name):
                return getattr(self, method_name)(node)
            
            # [FIX] ConditionalPredicate/Pattern 处理 - 从 conditions 提取
            if kind_name in ('ConditionalPredicate', 'ConditionalPattern'):
                # ConditionalPattern 有 expr 属性
                if kind_name == 'ConditionalPattern':
                    expr = getattr(node, 'expr', None)
                    if expr:
                        return self.get_all_signals(expr)
                    return []
                # ConditionalPredicate 有 conditions 属性
                if kind_name == 'ConditionalPredicate':
                    conditions = getattr(node, 'conditions', None)
                    if conditions:
                        signals = []
                        for cond in conditions:
                            signals.extend(self.get_all_signals(cond))
                        return [s for s in signals if s]
                    return []
        
        # 兜底: 递归提取所有子节点信号 (用于二元、位选等表达式)
        return self.get_all_signals_fallback(node)
    
    def generic_visit(self, node) -> Optional[str]:
        """默认递归进入子节点
        
        对于未实现的类型，尝试递归提取左操作数。
        [铁律26] 禁止 if-elif 链，使用 hasattr 检查
        """
        # [FIX] 二元表达式: left + right, left - right, etc.
        # 对于 get_all_signals，generic_visit 不会被调用（由调用方处理）
        # 对于 visit(单信号)，返回 left
        if hasattr(node, 'left') and hasattr(node, 'right'):
            left = getattr(node, 'left', None)
            if left:
                return self.visit(left)
        
        # [FIX] NamedValue 等类型有 symbol 属性
        if hasattr(node, 'symbol'):
            sym = getattr(node, 'symbol', None)
            if sym and hasattr(sym, 'name'):
                return str(sym.name).strip()
        
        # [FIX] IntegerLiteralExpression: 直接返回字符串表示
        kind = getattr(node, 'kind', None)
        if kind and 'IntegerLiteral' in str(kind):
            return str(node).strip()
        
        return None
    
    def get_all_binary_expression(self, node) -> List[str]:
        """BinaryExpression: a + b, a & b 等
        
        递归提取左右操作数中的所有信号
        """
        signals = []
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            signals.extend(self.get_all_signals(left))
        if right:
            signals.extend(self.get_all_signals(right))
        return [s for s in signals if s]
    
    def get_all_unary(self, node) -> List[str]:
        """UnaryExpression: ~a, -a, !a 等
        
        递归提取操作数中的所有信号
        """
        operand = getattr(node, 'operand', None) or getattr(node, 'expression', None)
        if operand:
            return self.get_all_signals(operand)
        return []
    
    def get_all_streaming(self, node) -> List[str]:
        """StreamingExpression: {>>[a:b]} or {<<[a:b]}
        
        递归提取流操作符内的信号
        """
        # StreamingExpression has 'expression' or 'body' attribute
        expr = getattr(node, 'expression', None) or getattr(node, 'body', None)
        if expr:
            return self.get_all_signals(expr)
        return []
    
    def get_all_inside(self, node) -> List[str]:
        """InsideExpression: expr inside {a, b, c}
        
        递归提取左右操作数中的信号
        """
        signals = []
        left = getattr(node, 'left', None) or getattr(node, 'condition', None)
        right = getattr(node, 'right', None) or getattr(node, 'range', None)
        if left:
            signals.extend(self.get_all_signals(left))
        if right:
            signals.extend(self.get_all_signals(right))
        return [s for s in signals if s]
    
    def get_all_min_typ_max(self, node) -> List[str]:
        """MinTypMaxExpression: min:typ:max
        
        递归提取所有分支中的信号
        """
        signals = []
        min_val = getattr(node, 'min', None) or getattr(node, 'left', None)
        typ_val = getattr(node, 'typ', None) or getattr(node, 'value', None)
        max_val = getattr(node, 'max', None) or getattr(node, 'right', None)
        if min_val:
            signals.extend(self.get_all_signals(min_val))
        if typ_val:
            signals.extend(self.get_all_signals(typ_val))
        if max_val:
            signals.extend(self.get_all_signals(max_val))
        return [s for s in signals if s]
    
    def get_all_dist(self, node) -> List[str]:
        """DistExpression: a dist {[/=]:1, [:=]:2}
        
        递归提取分布项中的信号
        """
        signals = []
        # DistExpression may have 'items' or 'dist_items'
        items = getattr(node, 'items', None) or getattr(node, 'dist_items', None)
        if items:
            for item in items:
                # Each dist item may have 'value' and 'weight'
                val = getattr(item, 'value', None) or getattr(item, 'expr', None)
                if val:
                    signals.extend(self.get_all_signals(val))
        return [s for s in signals if s]
    
    def get_all_value_range(self, node) -> List[str]:
        """ValueRangeExpression: [a:b] or [a..b]
        
        递归提取范围边界中的信号
        """
        signals = []
        left = getattr(node, 'left', None) or getattr(node, 'low', None)
        right = getattr(node, 'right', None) or getattr(node, 'high', None)
        if left:
            signals.extend(self.get_all_signals(left))
        if right:
            signals.extend(self.get_all_signals(right))
        return [s for s in signals if s]
    
    def get_all_multiple_concatenation(self, node) -> List[str]:
        """MultipleConcatenationExpression: {{n{expr}}
        
        递归提取表达式中的信号
        """
        expr = getattr(node, 'expression', None)
        if expr:
            return self.get_all_signals(expr)
        return []
    
    def get_all_stream_expression(self, node) -> List[str]:
        """StreamExpression: {>>[type]{expr}} or {<<[type]{expr}}
        
        递归提取表达式中的信号
        """
        expr = getattr(node, 'expression', None) or getattr(node, 'body', None)
        if expr:
            return self.get_all_signals(expr)
        return []
    
    def get_all_assignment_pattern(self, node) -> List[str]:
        """AssignmentPatternExpression: '{a, b, c}
        
        递归提取所有模式中的信号
        """
        signals = []
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    signals.extend(self.get_all_signals(p))
        return [s for s in signals if s]
    
    def get_all_call(self, node) -> List[str]:
        """Call: 函数调用参数
        
        返回: [arg1, arg2, ...]
        """
        signals = []
        args = getattr(node, 'arguments', None)
        
        if args:
            # Handle OrderedArgument vs NamedArgument
            for arg in args:
                if arg is None:
                    continue
                # NamedArgument has .name and .expr
                expr = getattr(arg, 'expr', None) or getattr(arg, 'value', None)
                if expr:
                    signals.extend(self.get_all_signals(expr))
                else:
                    # Maybe it's just an expression directly
                    signals.extend(self.get_all_signals(arg))
        
        return [s for s in signals if s]
    
    def get_all_element_select(self, node) -> List[str]:
        """ElementSelect: 位选择
        
        返回: [base[index]]
        """
        result = self.visit(node)
        return [result] if result else []
    

    def get_all_null_literal(self, node) -> List[str]:
        """NullLiteralExpression: null
        
        返回: []
        """
        return []
    
    def get_all_string_literal(self, node) -> List[str]:
        """StringLiteralExpression: "string"
        
        返回: []
        """
        return []
    
    def get_all_clock_event(self, node) -> List[str]:
        """ClockingEvent: @clk, @(posedge clk)
        
        提取事件控制中的所有信号
        """
        signals = []
        event = getattr(node, 'event', None) or getattr(node, 'clock', None)
        if event:
            signals.extend(self.get_all_signals(event))
        
        expr = getattr(node, 'expression', None)
        if expr:
            signals.extend(self.get_all_signals(expr))
        
        return [s for s in signals if s]
    
    def get_all_empty_argument(self, node) -> List[str]:
        """EmptyArgument: 函数参数占位
        
        返回: []
        """
        return []
    
    def get_all_data_type(self, node) -> List[str]:
        """DataType: bit, logic, int
        
        返回: []
        """
        return []
    
    def get_all_type_reference(self, node) -> List[str]:
        """TypeReference: 类型引用
        
        返回: []
        """
        return []
    
    def get_all_time_literal(self, node) -> List[str]:
        """TimeLiteralExpression: 1ns, 1us
        
        返回: []
        """
        return []
    
    def get_all_real_literal(self, node) -> List[str]:
        """RealLiteralExpression: 1.5, 3.14
        
        返回: []
        """
        return []
    
    def get_all_unbased_unsized_integer_literal(self, node) -> List[str]:
        """UnbasedUnsizedIntegerLiteral: '0, '1, 'x, 'z
        
        返回: []
        """
        return []
    
    def get_all_unbounded_literal(self, node) -> List[str]:
        """UnboundedLiteral: $
        
        返回: []
        """
        return []
    
    def get_all_unary_operator(self, node) -> List[str]:
        """UnaryOperator: 一元运算符
        
        递归提取操作数
        """
        operand = getattr(node, 'operand', None) or getattr(node, 'expression', None)
        if operand:
            return self.get_all_signals(operand)
        return []
    
    def get_all_binary_operator(self, node) -> List[str]:
        """BinaryOperator: 二元运算符
        
        递归提取左右操作数
        """
        signals = []
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            signals.extend(self.get_all_signals(left))
        if right:
            signals.extend(self.get_all_signals(right))
        return [s for s in signals if s]
    
    def get_all_assignment_expression(self, node) -> List[str]:
        """AssignmentExpression: a = b
        
        递归提取左右操作数
        """
        signals = []
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            signals.extend(self.get_all_signals(left))
        if right:
            signals.extend(self.get_all_signals(right))
        return [s for s in signals if s]
    
    def get_all_new_class(self, node) -> List[str]:
        """NewClassExpression: new()
        
        返回: []
        """
        return []
    
    def get_all_new_array(self, node) -> List[str]:
        """NewArrayExpression: new[size]
        
        返回 size 中的信号
        """
        signals = []
        size = getattr(node, 'size', None) or getattr(node, 'expression', None)
        if size:
            signals.extend(self.get_all_signals(size))
        return [s for s in signals if s]
    
    def get_all_new_covergroup(self, node) -> List[str]:
        """NewCovergroupExpression: covergroup
        
        返回: []
        """
        return []
    
    def get_all_copy_class(self, node) -> List[str]:
        """CopyClassExpression: class.copy()
        
        返回: []
        """
        return []
    
    def get_all_arbitrary_symbol(self, node) -> List[str]:
        """ArbitrarySymbol: 未解析的符号
        
        返回符号名
        """
        name = getattr(node, 'name', None)
        if name:
            return [str(name).strip()]
        return []
    
    def get_all_l_value_reference(self, node) -> List[str]:
        """LValueReference: 左值引用
        
        递归提取引用的信号
        """
        value = getattr(node, 'value', None)
        if value:
            return self.get_all_signals(value)
        return []
    
    def get_all_assertion_instance(self, node) -> List[str]:
        """AssertionInstance: assert property
        
        返回: []
        """
        return []
    
    def get_all_invalid(self, node) -> List[str]:
        """Invalid: 无效节点
        
        返回: []
        """
        return []

    def get_all_signals_fallback(self, node) -> List[str]:
        """Fallback for get_all_signals when no specific method exists
        
        递归提取所有子节点的信号（用于二元、位选等表达式）
        """
        if node is None:
            return []
        
        signals = []
        
        # Binary expression: left + right
        if hasattr(node, 'left') and hasattr(node, 'right'):
            left = getattr(node, 'left', None)
            right = getattr(node, 'right', None)
            if left:
                signals.extend(self.get_all_signals(left))
            if right:
                signals.extend(self.get_all_signals(right))
            if signals:
                return [s for s in signals if s]
        
        # ElementSelect: data[5] -> recursively get signals from value
        if hasattr(node, 'value'):
            value = getattr(node, 'value', None)
            if value:
                signals.extend(self.get_all_signals(value))
                if signals:
                    return [s for s in signals if s]
        
        # Unary expression: operand (e.g., |a, &b, ~c)
        if hasattr(node, 'operand'):
            operand = getattr(node, 'operand', None)
            if operand:
                signals.extend(self.get_all_signals(operand))
                if signals:
                    return [s for s in signals if s]
        
        # InvocationExpression/Call: $floor(a), func(b) -> get arguments
        if hasattr(node, 'arguments'):
            args = getattr(node, 'arguments', None)
            if args:
                # ArgumentListSyntax has .parameters, not iterable directly
                params = getattr(args, 'parameters', None)
                if params is not None:
                    # OrderedArgumentSyntax/ NamedArgumentSyntax
                    for p in params if hasattr(params, '__iter__') else [params]:
                        expr = getattr(p, 'expr', None)
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
    
    def visit_identifier_name(self, node) -> Optional[str]:
        """IdentifierName: 简单信号名
        
        结构: IdentifierName.identifier.value = "clk"
        """
        ident = getattr(node, 'identifier', None)
        if ident is None:
            logger.debug(f"[FALLBACK] IdentifierName missing 'identifier' attr")
            return None
        
        val = getattr(ident, 'value', None)
        if val is None:
            logger.debug(f"[FALLBACK] IdentifierName.identifier missing 'value' attr")
            return None
        
        return self.adapter.clean_name(str(val).strip())
    
    def visit_named_value(self, node) -> Optional[str]:
        """NamedValue: 简单变量引用 din, data 等
        
        结构: NamedValueExpression.symbol = NetSymbol/VariableSymbol, 有 .name 属性
        """
        sym = getattr(node, 'symbol', None)
        if sym and hasattr(sym, 'name'):
            return str(sym.name).strip()
        # 兜底: symbol 没 name 则尝试直接转字符串
        if sym:
            name = str(sym).strip()
            # 可能是 "Symbol(SymbolKind.Net, \"data\")" 格式
            if 'Symbol' in name and '"' in name:
                import re
                m = re.search(r'"([^"]+)"', name)
                if m:
                    return m.group(1)
            return name
        return None
    
    @on('NamedValue')
    def extract_named_value(self, node) -> SignalResult:
        """NamedValue: 单一信号引用
        
        SignalResult 返回: primary=all_signals=[信号名], kind_name='NamedValue'
        """
        signal_name = self.visit_named_value(node)
        return SignalResult.single(signal_name, kind_name='NamedValue')
    
    @on('BinaryExpression')
    def extract_binary_expression(self, node) -> SignalResult:
        """BinaryExpression: a + b, a & b 等二元表达式
        
        递归提取左右操作数中的所有信号
        """
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        
        # 合并结果
        return left_result.merge(right_result)
    
    # =========================================================================
    # 单 dispatch handlers (Phase 3)
    # =========================================================================
    
    @on('UnaryExpression')
    def extract_unary(self, node) -> SignalResult:
        """UnaryExpression: ~a, -a, !a 等"""
        operand = getattr(node, 'operand', None) or getattr(node, 'expression', None)
        if operand:
            return self.extract(operand)
        return SignalResult()
    
    @on('NullLiteral')
    def extract_null_literal(self, node) -> SignalResult:
        """NullLiteralExpression: null"""
        return SignalResult()
    
    @on('StringLiteral')
    def extract_string_literal(self, node) -> SignalResult:
        """StringLiteralExpression: \"string\""""
        return SignalResult()
    
    @on('EmptyArgument')
    def extract_empty_argument(self, node) -> SignalResult:
        """EmptyArgument: 函数参数占位"""
        return SignalResult()
    
    @on('TimeLiteral')
    def extract_time_literal(self, node) -> SignalResult:
        """TimeLiteralExpression: 时间字面量"""
        return SignalResult()
    
    @on('RealLiteral')
    def extract_real_literal(self, node) -> SignalResult:
        """RealLiteralExpression: 实数字面量"""
        return SignalResult()
    
    @on('UnbasedUnsizedLiteral')
    def extract_unbased_unsized_literal(self, node) -> SignalResult:
        """UnbasedUnsizedLiteralExpression: '0, '1, 'x, 'z"""
        return SignalResult()
    
    @on('UnboundedLiteral')
    def extract_unbounded_literal(self, node) -> SignalResult:
        """UnboundedLiteralExpression: $"""
        return SignalResult()
    
    @on('InsideExpression')
    def extract_inside(self, node) -> SignalResult:
        """InsideExpression: expr inside {a, b, c}"""
        left = getattr(node, 'left', None) or getattr(node, 'condition', None)
        right = getattr(node, 'right', None) or getattr(node, 'range', None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)
    
    @on('MinTypMaxExpression')
    def extract_min_typ_max(self, node) -> SignalResult:
        """MinTypMaxExpression: min:typ:max"""
        signals = []
        min_val = getattr(node, 'min', None) or getattr(node, 'left', None)
        typ_val = getattr(node, 'typ', None) or getattr(node, 'value', None)
        max_val = getattr(node, 'max', None) or getattr(node, 'right', None)
        result = SignalResult()
        if min_val:
            result = result.merge(self.extract(min_val))
        if typ_val:
            result = result.merge(self.extract(typ_val))
        if max_val:
            result = result.merge(self.extract(max_val))
        return result
    
    @on('DistExpression')
    def extract_dist(self, node) -> SignalResult:
        """DistExpression: a dist {[/=]:1, [:=]:2}"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'dist_items', None)
        if items:
            for item in items:
                val = getattr(item, 'value', None) or getattr(item, 'expr', None)
                if val:
                    result = result.merge(self.extract(val))
        return result
    
    @on('ValueRangeExpression')
    def extract_value_range(self, node) -> SignalResult:
        """ValueRangeExpression: [a:b] or [a..b]"""
        left = getattr(node, 'left', None) or getattr(node, 'low', None)
        right = getattr(node, 'right', None) or getattr(node, 'high', None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)
    
    @on('StreamingExpression')
    def extract_streaming(self, node) -> SignalResult:
        """StreamingExpression: {>>[a:b]} or {<<[a:b]}"""
        expr = getattr(node, 'expression', None) or getattr(node, 'body', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('MultipleConcatenationExpression')
    def extract_multiple_concatenation(self, node) -> SignalResult:
        """MultipleConcatenationExpression: {{n{expr}}"""
        expr = getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('StreamExpression')
    def extract_stream_expression(self, node) -> SignalResult:
        """StreamExpression: {>>[type]{expr}} or {<<[type]{expr}}"""
        expr = getattr(node, 'expression', None) or getattr(node, 'body', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('AssignmentPatternExpression')
    def extract_assignment_pattern(self, node) -> SignalResult:
        """AssignmentPatternExpression: '{a, b, c}"""
        result = SignalResult()
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result
    
    @on('CallExpression')
    def extract_call(self, node) -> SignalResult:
        """CallExpression: 函数调用参数"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args:
            for arg in args:
                if arg is None:
                    continue
                expr = getattr(arg, 'expr', None) or getattr(arg, 'value', None)
                if expr:
                    result = result.merge(self.extract(expr))
                else:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('ClockingEvent')
    def extract_clock_event(self, node) -> SignalResult:
        """ClockingEvent: @clk, @(posedge clk)"""
        result = SignalResult()
        event = getattr(node, 'event', None) or getattr(node, 'clock', None)
        if event:
            result = result.merge(self.extract(event))
        expr = getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('DataType')
    def extract_data_type(self, node) -> SignalResult:
        """DataType: 数据类型"""
        return SignalResult()
    
    @on('TypeReference')
    def extract_type_reference(self, node) -> SignalResult:
        """TypeReference: 类型引用"""
        return SignalResult()
    
    @on('UnaryOperator')
    def extract_unary_operator(self, node) -> SignalResult:
        """UnaryOperator: 一元运算符"""
        operand = getattr(node, 'operand', None) or getattr(node, 'expression', None)
        if operand:
            return self.extract(operand)
        return SignalResult()
    
    @on('BinaryOperator')
    def extract_binary_operator(self, node) -> SignalResult:
        """BinaryOperator: 二元运算符"""
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)
    
    @on('AssignmentExpression')
    def extract_assignment_expression(self, node) -> SignalResult:
        """AssignmentExpression: a = b"""
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)
    
    @on('NewClassExpression')
    def extract_new_class(self, node) -> SignalResult:
        """NewClassExpression: new()"""
        return SignalResult()
    
    @on('NewArrayExpression')
    def extract_new_array(self, node) -> SignalResult:
        """NewArrayExpression: new[size]"""
        size = getattr(node, 'size', None) or getattr(node, 'expression', None)
        if size:
            return self.extract(size)
        return SignalResult()
    
    @on('NewCovergroupExpression')
    def extract_new_covergroup(self, node) -> SignalResult:
        """NewCovergroupExpression: covergroup"""
        return SignalResult()
    
    @on('CopyClassExpression')
    def extract_copy_class(self, node) -> SignalResult:
        """CopyClassExpression: class.copy()"""
        return SignalResult()
    
    @on('ArbitrarySymbol')
    def extract_arbitrary_symbol(self, node) -> SignalResult:
        """ArbitrarySymbol: 未解析的符号"""
        return SignalResult()
    
    @on('LValueReference')
    def extract_l_value_reference(self, node) -> SignalResult:
        """LValueReference: 左值引用"""
        value = getattr(node, 'value', None)
        if value:
            return self.extract(value)
        return SignalResult()
    
    @on('AssertionInstance')
    def extract_assertion_instance(self, node) -> SignalResult:
        """AssertionInstance: assert property"""
        return SignalResult()
    
    @on('Invalid')
    def extract_invalid(self, node) -> SignalResult:
        """Invalid: 无效节点"""
        return SignalResult()
    
    @on('ConditionalOp')
    def extract_conditional_op(self, node) -> SignalResult:
        """ConditionalOp: 三元运算符 sel ? a : b"""
        result = SignalResult()
        
        # predicate (condition)
        conditions = getattr(node, 'conditions', None)
        if conditions and len(conditions) > 0:
            cond_expr = getattr(conditions[0], 'expr', None)
            if cond_expr:
                result = result.merge(self.extract(cond_expr))
        
        pred = getattr(node, 'predicate', None)
        if pred:
            result = result.merge(self.extract(pred))
        
        left = getattr(node, 'left', None)
        if left:
            result = result.merge(self.extract(left))
        
        right = getattr(node, 'right', None)
        if right:
            result = result.merge(self.extract(right))
        
        return result
    
    @on('ConcatenationExpression')
    def extract_concatenation(self, node) -> SignalResult:
        """ConcatenationExpression: {a, b, c}"""
        result = SignalResult()
        operands = getattr(node, 'operands', None) or getattr(node, 'expressions', None)
        if operands:
            for expr in operands:
                expr_kind = getattr(expr, 'kind', None)
                if expr_kind and 'Token' not in str(expr_kind):
                    result = result.merge(self.extract(expr))
        return result
    
    @on('IdentifierName')
    def extract_identifier_name(self, node) -> SignalResult:
        """IdentifierName: 简单信号名"""
        ident = getattr(node, 'identifier', None)
        if ident is None:
            return SignalResult()
        val = getattr(ident, 'value', None)
        if val is None:
            return SignalResult()
        name = self.adapter.clean_name(str(val).strip())
        return SignalResult.single(name)
    
    @on('ScopedName')
    def extract_scoped_name(self, node) -> SignalResult:
        """ScopedName: 点分路径 p.sub.data"""
        parts = self._extract_scoped_parts(node)
        if parts:
            combined = '.'.join(parts)
            name = self.adapter.clean_name(combined)
            return SignalResult.single(name)
        return SignalResult()
    
    @on('ElementSelectExpression')
    def extract_element_select(self, node) -> SignalResult:
        """ElementSelectExpression: data[5]"""
        base = getattr(node, 'left', None) or getattr(node, 'base', None) or getattr(node, 'value', None)
        if base:
            return self.extract(base)
        return SignalResult()
    
    @on('RangeSelectExpression')
    def extract_range_select(self, node) -> SignalResult:
        """RangeSelectExpression: data[3:0]"""
        base = getattr(node, 'value', None)
        if base:
            return self.extract(base)
        return SignalResult()
    
    @on('IdentifierSelect')
    def extract_identifier_select(self, node) -> SignalResult:
        """IdentifierSelect: data[3] 等带位选的标识符"""
        base_name = None
        if hasattr(node, 'identifier'):
            ident = node.identifier
            if hasattr(ident, 'value'):
                base_name = str(ident.value).strip()
            else:
                base_name = str(ident).strip()
        if not base_name:
            base_name = str(node).strip().split('[')[0]
        return SignalResult.single(self.adapter.clean_name(base_name) if base_name else '')
    
    @on('HierarchicalValueExpression')
    def extract_hierarchical_value(self, node) -> SignalResult:
        """HierarchicalValueExpression: ifc.data"""
        syntax = getattr(node, 'syntax', None)
        if syntax and hasattr(syntax, 'kind'):
            kind_str = str(syntax.kind)
            if 'ScopedName' in kind_str:
                return self.extract(syntax)
        return SignalResult()
    
    @on('ReplicationExpression')
    def extract_replication(self, node) -> SignalResult:
        """ReplicationExpression: {N{signal}}"""
        concat = getattr(node, 'concat', None)
        if concat and hasattr(concat, 'operands'):
            operands = concat.operands
            if hasattr(operands, '__iter__') and not isinstance(operands, str):
                result = SignalResult()
                for expr_item in operands:
                    if hasattr(expr_item, 'kind'):
                        result = result.merge(self.extract(expr_item))
                return result
            else:
                return self.extract(operands)
        return SignalResult()
    
    @on('CastExpression')
    def extract_cast_expression(self, node) -> SignalResult:
        """CastExpression: type'(expr)"""
        expr = getattr(node, 'expression', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('TaggedUnionExpression')
    def extract_tagged_union_expression(self, node) -> SignalResult:
        """TaggedUnionExpression: tag'(expr)"""
        expr = getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('IntegerLiteral')
    def extract_integer_literal(self, node) -> SignalResult:
        """IntegerLiteral: 整数字面量"""
        return SignalResult()
    
    @on('IntegerVectorExpression')
    def extract_integer_vector(self, node) -> SignalResult:
        """IntegerVectorExpression: 带位宽的字面量"""
        return SignalResult()
    
    @on('ReplicatedAssignmentPattern')
    def extract_replicated_assignment_pattern(self, node) -> SignalResult:
        """ReplicatedAssignmentPattern: '{n{a, b, c}}"""
        result = SignalResult()
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result
    
    @on('SimpleAssignmentPattern')
    def extract_simple_assignment_pattern(self, node) -> SignalResult:
        """SimpleAssignmentPattern: 简单赋值模式"""
        result = SignalResult()
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result
    
    @on('StructuredAssignmentPattern')
    def extract_structured_assignment_pattern(self, node) -> SignalResult:
        """StructuredAssignmentPattern: 结构化赋值模式"""
        result = SignalResult()
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result
    
    @on('MemberAccessExpression')
    def extract_member_access(self, node) -> SignalResult:
        """MemberAccessExpression: obj.member"""
        obj = getattr(node, 'left', None) or getattr(node, 'expression', None)
        if obj:
            return self.extract(obj)
        return SignalResult()
    
    @on('ParenthesisExpression')
    def extract_parenthesis_expression(self, node) -> SignalResult:
        """ParenthesisExpression: (expr)"""
        expr = getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('WildcardLiteral')
    def extract_wildcard_literal(self, node) -> SignalResult:
        """WildcardLiteral: *"""
        return SignalResult()
    
    @on('QueueLiteral')
    def extract_queue_literal(self, node) -> SignalResult:
        """QueueLiteral: '{...}"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'expressions', None)
        if items and hasattr(items, '__iter__') and not isinstance(items, str):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('AssociativeArrayLiteral')
    def extract_associative_array_literal(self, node) -> SignalResult:
        """AssociativeArrayLiteral: '{key: value, ...}"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__') and not isinstance(items, str):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('DelayControl')
    def extract_delay_control(self, node) -> SignalResult:
        """DelayControl: #1delay"""
        expr = getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('EventControl')
    def extract_event_control(self, node) -> SignalResult:
        """EventControl: @event"""
        event = getattr(node, 'event', None)
        if event:
            return self.extract(event)
        return SignalResult()
    
    @on('DelayOrEventControl')
    def extract_delay_or_event_control(self, node) -> SignalResult:
        """DelayOrEventControl: #1 or @event"""
        result = SignalResult()
        delay = getattr(node, 'delay', None) or getattr(node, 'expression', None)
        if delay:
            result = result.merge(self.extract(delay))
        event = getattr(node, 'event', None)
        if event:
            result = result.merge(self.extract(event))
        return result
    
    @on('SequenceConjunction')
    def extract_sequence_conjunction(self, node) -> SignalResult:
        """SequenceConjunction: seq1 and seq2"""
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)
    
    @on('SequenceDelay')
    def extract_sequence_delay(self, node) -> SignalResult:
        """SequenceDelay: ##1 seq"""
        seq = getattr(node, 'sequence', None) or getattr(node, 'operand', None)
        if seq:
            return self.extract(seq)
        return SignalResult()
    
    @on('Sequence Repetition')
    def extract_sequence_repetition(self, node) -> SignalResult:
        """SequenceRepetition: seq[*1:3]"""
        seq = getattr(node, 'sequence', None) or getattr(node, 'operand', None)
        if seq:
            return self.extract(seq)
        return SignalResult()
    
    @on('PropertySequence')
    def extract_property_sequence(self, node) -> SignalResult:
        """PropertySequence: sequence expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None) or getattr(node, 'operand', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('PropertyActualArgument')
    def extract_property_actual_argument(self, node) -> SignalResult:
        """PropertyActualArgument: property argument"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('AssertPropertyExpression')
    def extract_assert_property_expression(self, node) -> SignalResult:
        """AssertPropertyExpression: assert property"""
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            return self.extract(prop)
        return SignalResult()
    
    @on('AssumePropertyExpression')
    def extract_assume_property_expression(self, node) -> SignalResult:
        """AssumePropertyExpression: assume property"""
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            return self.extract(prop)
        return SignalResult()
    
    @on('CoverPropertyExpression')
    def extract_cover_property_expression(self, node) -> SignalResult:
        """CoverPropertyExpression: cover property"""
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            return self.extract(prop)
        return SignalResult()
    
    @on('SequenceActualArgument')
    def extract_sequence_actual_argument(self, node) -> SignalResult:
        """SequenceActualArgument: sequence argument"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('SequenceInstance')
    def extract_sequence_instance(self, node) -> SignalResult:
        """SequenceInstance: sequence call"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('PropertyInstance')
    def extract_property_instance(self, node) -> SignalResult:
        """PropertyInstance: property call"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('ClockingBlock')
    def extract_clocking_block(self, node) -> SignalResult:
        """ClockingBlock: clocking block"""
        return SignalResult()
    
    @on('ClockingDrive')
    def extract_clocking_drive(self, node) -> SignalResult:
        """ClockingDrive: clocking drive"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, 'rvalue', None) or getattr(node, 'expr', None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result
    
    @on('ClockingPropertyExpr')
    def extract_clocking_property_expr(self, node) -> SignalResult:
        """ClockingPropertyExpr: property with clock"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        clock = getattr(node, 'clock', None)
        if clock:
            result = result.merge(self.extract(clock))
        return result
    
    @on('SequencePropertyExpr')
    def extract_sequence_property_expr(self, node) -> SignalResult:
        """SequencePropertyExpr: sequence with clock"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        clock = getattr(node, 'clock', None)
        if clock:
            result = result.merge(self.extract(clock))
        return result
    
    @on(' ImpSeq')
    def extract_implication_seq(self, node) -> SignalResult:
        """ImplicationSeq: seq |=> or |->"""
        left = getattr(node, 'left', None) or getattr(node, 'antecedent', None)
        right = getattr(node, 'right', None) or getattr(node, 'consequent', None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)
    
    @on('IfConstraint')
    def extract_if_constraint(self, node) -> SignalResult:
        """IfConstraint: if (cond) constraint"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        true_body = getattr(node, 'true_body', None) or getattr(node, 'constraint', None)
        if true_body:
            result = result.merge(self.extract(true_body))
        return result
    
    @on('ElseConstraint')
    def extract_else_constraint(self, node) -> SignalResult:
        """ElseConstraint: else constraint"""
        result = SignalResult()
        else_body = getattr(node, 'else_body', None) or getattr(node, 'constraint', None)
        if else_body:
            result = result.merge(self.extract(else_body))
        return result
    
    @on('DisableConstraint')
    def extract_disable_constraint(self, node) -> SignalResult:
        """DisableConstraint: disable constraint"""
        expr = getattr(node, 'expr', None) or getattr(node, 'constraint', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('SolveBeforeConstraint')
    def extract_solve_before_constraint(self, node) -> SignalResult:
        """SolveBeforeConstraint: solve before constraint"""
        result = SignalResult()
        before = getattr(node, 'before', None)
        after = getattr(node, 'after', None)
        if before:
            result = result.merge(self.extract(before))
        if after:
            result = result.merge(self.extract(after))
        return result
    
    @on('ExpressionConstraint')
    def extract_expression_constraint(self, node) -> SignalResult:
        """ExpressionConstraint: expression constraint"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('RangeConstraint')
    def extract_range_constraint(self, node) -> SignalResult:
        """RangeConstraint: range constraint"""
        result = SignalResult()
        range_node = getattr(node, 'range', None)
        if range_node:
            result = result.merge(self.extract(range_node))
        return result
    
    @on('DistributionConstraint')
    def extract_distribution_constraint(self, node) -> SignalResult:
        """DistributionConstraint: dist constraint"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('UniqueConstraint')
    def extract_unique_constraint(self, node) -> SignalResult:
        """UniqueConstraint: unique constraint"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ForeachConstraint')
    def extract_foreach_constraint(self, node) -> SignalResult:
        """ForeachConstraint: foreach constraint"""
        result = SignalResult()
        array = getattr(node, 'array', None)
        body = getattr(node, 'body', None) or getattr(node, 'constraint', None)
        if array:
            result = result.merge(self.extract(array))
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('ConditionalPattern')
    def extract_conditional_pattern(self, node) -> SignalResult:
        """ConditionalPattern: pattern if cond"""
        result = SignalResult()
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        return result
    
    @on('WildcardPattern')
    def extract_wildcard_pattern(self, node) -> SignalResult:
        """WildcardPattern: wildcard pattern"""
        return SignalResult()
    
    @on('TaggedPattern')
    def extract_tagged_pattern(self, node) -> SignalResult:
        """TaggedPattern: tagged pattern"""
        result = SignalResult()
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        return result
    
    @on('ConstantExpression')
    def extract_constant_expression(self, node) -> SignalResult:
        """ConstantExpression: constant expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('ParenConstantExpression')
    def extract_paren_constant_expression(self, node) -> SignalResult:
        """ParenConstantExpression: (constant)"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('VoidCastedVarianceExpression')
    def extract_void_casted_variance(self, node) -> SignalResult:
        """VoidCastedVarianceExpression: variance cast"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('EmptyStatement')
    def extract_empty_statement(self, node) -> SignalResult:
        """EmptyStatement: empty statement"""
        return SignalResult()
    
    @on('EmptySequence')
    def extract_empty_sequence(self, node) -> SignalResult:
        """EmptySequence: empty sequence"""
        return SignalResult()
    
    @on('EmptyProperty')
    def extract_empty_property(self, node) -> SignalResult:
        """EmptyProperty: empty property"""
        return SignalResult()
    
    @on('MatchedMultipleSequences')
    def extract_matched_multiple_sequences(self, node) -> SignalResult:
        """MatchedMultipleSequences: matched sequences"""
        return SignalResult()
    
    @on('MatchedSequence')
    def extract_matched_sequence(self, node) -> SignalResult:
        """MatchedSequence: matched sequence"""
        return SignalResult()
    
    @on('MatchedProperty')
    def extract_matched_property(self, node) -> SignalResult:
        """MatchedProperty: matched property"""
        return SignalResult()
    
    @on('SyncQuickBell')
    def extract_sync_quick_bell(self, node) -> SignalResult:
        """SyncQuickBell: sync @bell"""
        return SignalResult()
    
    @on('SyncSharpBell')
    def extract_sync_sharp_bell(self, node) -> SignalResult:
        """SyncSharpBell: sync ##bell"""
        return SignalResult()
    
    @on('Implication')
    def extract_implication(self, node) -> SignalResult:
        """Implication: sequence implication"""
        left = getattr(node, 'left', None) or getattr(node, 'antecedent', None)
        right = getattr(node, 'right', None) or getattr(node, 'consequent', None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)
    
    @on('PropertyImplication')
    def extract_property_implication(self, node) -> SignalResult:
        """PropertyImplication: property implication"""
        left = getattr(node, 'left', None) or getattr(node, 'antecedent', None)
        right = getattr(node, 'right', None) or getattr(node, 'consequent', None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)
    
    @on('IfPropertyExpression')
    def extract_if_property_expression(self, node) -> SignalResult:
        """IfPropertyExpression: if property"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        else_body = getattr(node, 'else_body', None) or getattr(node, 'else_property', None)
        if else_body:
            result = result.merge(self.extract(else_body))
        return result
    
    @on('CasePropertyExpression')
    def extract_case_property_expression(self, node) -> SignalResult:
        """CasePropertyExpression: case property expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('PropertyExpr')
    def extract_property_expr(self, node) -> SignalResult:
        """PropertyExpr: property expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('SequenceExpr')
    def extract_sequence_expr(self, node) -> SignalResult:
        """SequenceExpr: sequence expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('UnaryPropertyExpression')
    def extract_unary_property_expression(self, node) -> SignalResult:
        """UnaryPropertyExpression: unary property"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('StrongParenthesizedProperty')
    def extract_strong_parenthesized_property(self, node) -> SignalResult:
        """StrongParenthesizedProperty: strong(property)"""
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            return self.extract(prop)
        return SignalResult()
    
    @on('WeakParenthesizedProperty')
    def extract_weak_parenthesized_property(self, node) -> SignalResult:
        """WeakParenthesizedProperty: property"""
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            return self.extract(prop)
        return SignalResult()
    
    @on('SequenceMatchItem')
    def extract_sequence_match_item(self, node) -> SignalResult:
        """SequenceMatchItem: sequence match item"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('SequenceMatchFunction')
    def extract_sequence_match_function(self, node) -> SignalResult:
        """SequenceMatchFunction: match function"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('ConcurrentAssertionStatement')
    def extract_concurrent_assertion(self, node) -> SignalResult:
        """ConcurrentAssertionStatement: concurrent assertion"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('DeferredImmediateAssertionStatement')
    def extract_deferred_immediate_assertion(self, node) -> SignalResult:
        """DeferredImmediateAssertionStatement: #0 assert"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('SimpleDeferredImmediateAssertionStatement')
    def extract_simple_deferred_assertion(self, node) -> SignalResult:
        """SimpleDeferredImmediateAssertionStatement: #0 assert"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('FinalDeferredImmediateAssertionStatement')
    def extract_final_deferred_assertion(self, node) -> SignalResult:
        """FinalDeferredImmediateAssertionStatement: final #0 assert"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('ImmediateAssertionStatement')
    def extract_immediate_assertion(self, node) -> SignalResult:
        """ImmediateAssertionStatement: immediate assertion"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('AssumePropertyExpression')
    def extract_assume_property(self, node) -> SignalResult:
        """AssumePropertyExpression: assume property"""
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            return self.extract(prop)
        return SignalResult()
    
    @on('CoverPropertyExpression')
    def extract_cover_property(self, node) -> SignalResult:
        """CoverPropertyExpression: cover property"""
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            return self.extract(prop)
        return SignalResult()
    
    @on('CoverSequenceExpression')
    def extract_cover_sequence(self, node) -> SignalResult:
        """CoverSequenceExpression: cover sequence"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('RestrictPropertyExpression')
    def extract_restrict_property(self, node) -> SignalResult:
        """RestrictPropertyExpression: restrict property"""
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            return self.extract(prop)
        return SignalResult()
    
    @on('ExpectPropertyExpression')
    def extract_expect_property(self, node) -> SignalResult:
        """ExpectPropertyExpression: expect property"""
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            return self.extract(prop)
        return SignalResult()
    
    @on('SequenceRepetition')
    def extract_sequence_repetition(self, node) -> SignalResult:
        """SequenceRepetition: seq[*1:3]"""
        seq = getattr(node, 'sequence', None) or getattr(node, 'operand', None)
        if seq:
            return self.extract(seq)
        return SignalResult()
    
    @on('SequenceConcat')
    def extract_sequence_concat(self, node) -> SignalResult:
        """SequenceConcat: sequence concatenation"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SequenceInstersection')
    def extract_sequence_intersection(self, node) -> SignalResult:
        """SequenceInstersection: sequence intersection"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SequenceFirstMatch')
    def extract_sequence_first_match(self, node) -> SignalResult:
        """SequenceFirstMatch: sequence first_match"""
        seq = getattr(node, 'sequence', None) or getattr(node, 'operand', None)
        if seq:
            return self.extract(seq)
        return SignalResult()
    
    @on('SequenceClocking')
    def extract_sequence_clock(self, node) -> SignalResult:
        """SequenceClocking: sequence with clock"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        clock = getattr(node, 'clock', None)
        if clock:
            result = result.merge(self.extract(clock))
        return result
    
    @on('SequenceMatched')
    def extract_sequence_matched(self, node) -> SignalResult:
        """SequenceMatched: matched sequence"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('PropertyMatched')
    def extract_property_matched(self, node) -> SignalResult:
        """PropertyMatched: matched property"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('SequenceOr')
    def extract_sequence_or(self, node) -> SignalResult:
        """SequenceOr: sequence or"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SequenceAnd')
    def extract_sequence_and(self, node) -> SignalResult:
        """SequenceAnd: sequence and"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('PropertyOr')
    def extract_property_or(self, node) -> SignalResult:
        """PropertyOr: property or"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('PropertyAnd')
    def extract_property_and(self, node) -> SignalResult:
        """PropertyAnd: property and"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('PropertyNot')
    def extract_property_not(self, node) -> SignalResult:
        """PropertyNot: not property"""
        prop = getattr(node, 'property', None) or getattr(node, 'operand', None)
        if prop:
            return self.extract(prop)
        return SignalResult()
    
    @on('PropertyClocked')
    def extract_property_clocked(self, node) -> SignalResult:
        """PropertyClocked: property with clock"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        clock = getattr(node, 'clock', None)
        if clock:
            result = result.merge(self.extract(clock))
        return result
    
    @on('SequenceClocked')
    def extract_sequence_clocked(self, node) -> SignalResult:
        """SequenceClocked: sequence with clock"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        clock = getattr(node, 'clock', None)
        if clock:
            result = result.merge(self.extract(clock))
        return result
    
    @on('PropertyDisableIff')
    def extract_property_disable(self, node) -> SignalResult:
        """PropertyDisableIff: disable iff"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        disable = getattr(node, 'disable', None) or getattr(node, 'expr2', None)
        if disable:
            result = result.merge(self.extract(disable))
        return result
    
    @on('CaseExpression')
    def extract_case_expression(self, node) -> SignalResult:
        """CaseExpression: case expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('CaseItemExpression')
    def extract_case_item_expression(self, node) -> SignalResult:
        """CaseItemExpression: case item"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ConditionalExpression')
    def extract_conditional_expression(self, node) -> SignalResult:
        """ConditionalExpression: cond ? expr1 : expr2"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        true_expr = getattr(node, 'true_expr', None) or getattr(node, 'expr1', None)
        if true_expr:
            result = result.merge(self.extract(true_expr))
        false_expr = getattr(node, 'false_expr', None) or getattr(node, 'expr2', None)
        if false_expr:
            result = result.merge(self.extract(false_expr))
        return result
    
    @on('VariableDeclarationExpression')
    def extract_variable_declaration_expression(self, node) -> SignalResult:
        """VariableDeclarationExpression: variable declaration"""
        result = SignalResult()
        init = getattr(node, 'init', None) or getattr(node, 'value', None)
        if init:
            result = result.merge(self.extract(init))
        return result
    
    @on('LetDeclaration')
    def extract_let_declaration(self, node) -> SignalResult:
        """LetDeclaration: let declaration"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        body = getattr(node, 'body', None) or getattr(node, 'expr', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('LetExpression')
    def extract_let_expression(self, node) -> SignalResult:
        """LetExpression: let expression"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('CallableExpression')
    def extract_callable_expression(self, node) -> SignalResult:
        """CallableExpression: callable expression"""
        result = SignalResult()
        func = getattr(node, 'func', None) or getattr(node, 'callee', None)
        if func:
            result = result.merge(self.extract(func))
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('ReturnStatementExpression')
    def extract_return_expression(self, node) -> SignalResult:
        """ReturnStatementExpression: return expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('YieldStatementExpression')
    def extract_yield_expression(self, node) -> SignalResult:
        """YieldStatementExpression: yield expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('EventTriggerExpression')
    def extract_event_trigger(self, node) -> SignalResult:
        """EventTriggerExpression: ->event"""
        event = getattr(node, 'event', None) or getattr(node, 'expr', None)
        if event:
            return self.extract(event)
        return SignalResult()
    
    @on('NullCheckExpression')
    def extract_null_check(self, node) -> SignalResult:
        """NullCheckExpression: null check"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('TypeOptionExpression')
    def extract_type_option(self, node) -> SignalResult:
        """TypeOptionExpression: type_option expression"""
        result = SignalResult()
        type_expr = getattr(node, 'type', None) or getattr(node, 'expr', None)
        if type_expr:
            result = result.merge(self.extract(type_expr))
        return result
    
    @on('RefVariableExpression')
    def extract_ref_variable(self, node) -> SignalResult:
        """RefVariableExpression: ref variable"""
        var = getattr(node, 'var', None) or getattr(node, 'expr', None)
        if var:
            return self.extract(var)
        return SignalResult()
    
    @on('AssignmentPatternExpression')
    def extract_assignment_pattern_expr(self, node) -> SignalResult:
        """AssignmentPatternExpression: pattern expression"""
        result = SignalResult()
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result
    
    @on('DefaultPatternExpression')
    def extract_default_pattern_expr(self, node) -> SignalResult:
        """DefaultPatternExpression: default pattern"""
        return SignalResult()
    
    @on('DefaultPattern')
    def extract_default_pattern(self, node) -> SignalResult:
        """DefaultPattern: default pattern"""
        return SignalResult()
    
    @on('PatternBinding')
    def extract_pattern_binding(self, node) -> SignalResult:
        """PatternBinding: pattern binding"""
        result = SignalResult()
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        return result
    
    @on('OpenRangeExpression')
    def extract_open_range(self, node) -> SignalResult:
        """OpenRangeExpression: open range"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('MultiPattern')
    def extract_multi_pattern(self, node) -> SignalResult:
        """MultiPattern: multiple patterns"""
        result = SignalResult()
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result
    
    @on('ParameterizedPropertyExpression')
    def extract_parameterized_property(self, node) -> SignalResult:
        """ParameterizedPropertyExpression: parameterized property"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        args = getattr(node, 'arguments', None) or getattr(node, 'params', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('RepeatedPattern')
    def extract_repeated_pattern(self, node) -> SignalResult:
        """RepeatedPattern: repeated pattern"""
        result = SignalResult()
        count = getattr(node, 'count', None) or getattr(node, 'expr', None)
        if count:
            result = result.merge(self.extract(count))
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        return result
    
    @on('WildcardPatternExpression')
    def extract_wildcard_pattern_expr(self, node) -> SignalResult:
        """WildcardPatternExpression: wildcard pattern expression"""
        return SignalResult()
    
    @on('TaggedPatternExpression')
    def extract_tagged_pattern_expr(self, node) -> SignalResult:
        """TaggedPatternExpression: tagged pattern expression"""
        result = SignalResult()
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        return result
    
    @on('WildcardPatternExpression')
    def extract_wildcard_pattern_expr(self, node) -> SignalResult:
        """WildcardPatternExpression: wildcard"""
        return SignalResult()
    
    @on('RandomizeSequence')
    def extract_randomize_sequence(self, node) -> SignalResult:
        """RandomizeSequence: randomize with sequence"""
        result = SignalResult()
        with_expr = getattr(node, 'with', None) or getattr(node, 'expr', None)
        if with_expr:
            result = result.merge(self.extract(with_expr))
        return result
    
    @on('VoidMethodCallSequence')
    def extract_void_method_call_seq(self, node) -> SignalResult:
        """VoidMethodCallSequence: void method call"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('ReturnMethodCallSequence')
    def extract_return_method_call_seq(self, node) -> SignalResult:
        """ReturnMethodCallSequence: return method call sequence"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('NonNullMethodCallSequence')
    def extract_non_null_method_call_seq(self, node) -> SignalResult:
        """NonNullMethodCallSequence: non null method call"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('SequenceAbbrevMaybe')
    def extract_sequence_abbrev_maybe(self, node) -> SignalResult:
        """SequenceAbbrevMaybe: maybe ##?"""
        expr = getattr(node, 'expr', None) or getattr(node, 'sequence', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('SequenceAbbrevPlus')
    def extract_sequence_abbrev_plus(self, node) -> SignalResult:
        """SequenceAbbrevPlus: plus ##+"""
        expr = getattr(node, 'expr', None) or getattr(node, 'sequence', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('SequenceAbbrevStar')
    def extract_sequence_abbrev_star(self, node) -> SignalResult:
        """SequenceAbbrevStar: star ##*"""
        expr = getattr(node, 'expr', None) or getattr(node, 'sequence', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('ImplicationWindow')
    def extract_implication_window(self, node) -> SignalResult:
        """ImplicationWindow: implication window"""
        result = SignalResult()
        antecedent = getattr(node, 'antecedent', None)
        consequent = getattr(node, 'consequent', None)
        if antecedent:
            result = result.merge(self.extract(antecedent))
        if consequent:
            result = result.merge(self.extract(consequent))
        return result
    
    @on('SequenceWindow')
    def extract_sequence_window(self, node) -> SignalResult:
        """SequenceWindow: sequence window"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('PropertyOrSequence')
    def extract_property_or_sequence(self, node) -> SignalResult:
        """PropertyOrSequence: property or sequence"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('PropertyAndSequence')
    def extract_property_and_sequence(self, node) -> SignalResult:
        """PropertyAndSequence: property and sequence"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ExpressionOrStatement')
    def extract_expression_or_statement(self, node) -> SignalResult:
        """ExpressionOrStatement: expression or statement"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None) or getattr(node, 'statement', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('StatementOrExpression')
    def extract_statement_or_expression(self, node) -> SignalResult:
        """StatementOrExpression: statement or expression"""
        stmt = getattr(node, 'statement', None) or getattr(node, 'expr', None)
        if stmt:
            return self.extract(stmt)
        return SignalResult()
    
    @on('LoopStatementExpression')
    def extract_loop_statement_expression(self, node) -> SignalResult:
        """LoopStatementExpression: loop statement expression"""
        result = SignalResult()
        init = getattr(node, 'init', None) or getattr(node, 'expr', None)
        if init:
            result = result.merge(self.extract(init))
        cond = getattr(node, 'cond', None) or getattr(node, 'condition', None)
        if cond:
            result = result.merge(self.extract(cond))
        step = getattr(node, 'step', None) or getattr(node, 'expr2', None)
        if step:
            result = result.merge(self.extract(step))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('JumpStatementExpression')
    def extract_jump_statement_expression(self, node) -> SignalResult:
        """JumpStatementExpression: jump statement"""
        return SignalResult()
    
    @on('WaitStatementExpression')
    def extract_wait_statement_expression(self, node) -> SignalResult:
        """WaitStatementExpression: wait statement"""
        cond = getattr(node, 'cond', None) or getattr(node, 'expression', None)
        if cond:
            return self.extract(cond)
        return SignalResult()
    
    @on('WaitForkStatementExpression')
    def extract_wait_fork_expression(self, node) -> SignalResult:
        """WaitForkStatementExpression: wait fork"""
        return SignalResult()
    
    @on('EventStatementExpression')
    def extract_event_statement_expression(self, node) -> SignalResult:
        """EventStatementExpression: event statement"""
        event = getattr(node, 'event', None) or getattr(node, 'expr', None)
        if event:
            return self.extract(event)
        return SignalResult()
    
    @on('AssertionStatementExpression')
    def extract_assertion_statement_expression(self, node) -> SignalResult:
        """AssertionStatementExpression: assert statement expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('BlockingAssignmentStatement')
    def extract_blocking_assignment_stmt(self, node) -> SignalResult:
        """BlockingAssignmentStatement: blocking assignment"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, 'rvalue', None) or getattr(node, 'expr', None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result
    
    @on('NonBlockingAssignmentStatement')
    def extract_nonblocking_assignment_stmt(self, node) -> SignalResult:
        """NonBlockingAssignmentStatement: non-blocking assignment"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, 'rvalue', None) or getattr(node, 'expr', None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result
    
    @on('ProceduralAssignStatement')
    def extract_procedural_assign_stmt(self, node) -> SignalResult:
        """ProceduralAssignStatement: procedural assign"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, 'rvalue', None) or getattr(node, 'expr', None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result
    
    @on('ProceduralForceStatement')
    def extract_procedural_force_stmt(self, node) -> SignalResult:
        """ProceduralForceStatement: procedural force"""
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()
    
    @on('DeassignStatement')
    def extract_deassign_stmt(self, node) -> SignalResult:
        """DeassignStatement: deassign"""
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()
    
    @on('ReleaseStatement')
    def extract_release_stmt(self, node) -> SignalResult:
        """ReleaseStatement: release"""
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()
    
    @on('VariableDeclarationStatement')
    def extract_variable_declaration_stmt(self, node) -> SignalResult:
        """VariableDeclarationStatement: variable declaration"""
        result = SignalResult()
        init = getattr(node, 'init', None) or getattr(node, 'value', None)
        if init:
            result = result.merge(self.extract(init))
        return result
    
    @on('ForLoopStatementExpression')
    def extract_for_loop_expression(self, node) -> SignalResult:
        """ForLoopStatementExpression: for loop expression"""
        result = SignalResult()
        init = getattr(node, 'init', None)
        if init:
            result = result.merge(self.extract(init))
        cond = getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        step = getattr(node, 'step', None)
        if step:
            result = result.merge(self.extract(step))
        body = getattr(node, 'body', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('ForeachLoopStatementExpression')
    def extract_foreach_loop_expression(self, node) -> SignalResult:
        """ForeachLoopStatementExpression: foreach loop"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('DoWhileStatementExpression')
    def extract_do_while_expression(self, node) -> SignalResult:
        """DoWhileStatementExpression: do while expression"""
        result = SignalResult()
        cond = getattr(node, 'cond', None) or getattr(node, 'expression', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('WhileLoopStatementExpression')
    def extract_while_loop_expression(self, node) -> SignalResult:
        """WhileLoopStatementExpression: while loop expression"""
        result = SignalResult()
        cond = getattr(node, 'cond', None) or getattr(node, 'expression', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('ReturnStatementExpression')
    def extract_return_stmt_expression(self, node) -> SignalResult:
        """ReturnStatementExpression: return expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('BreakStatementExpression')
    def extract_break_stmt_expression(self, node) -> SignalResult:
        """BreakStatementExpression: break"""
        return SignalResult()
    
    @on('ContinueStatementExpression')
    def extract_continue_stmt_expression(self, node) -> SignalResult:
        """ContinueStatementExpression: continue"""
        return SignalResult()
    
    @on('DisableStatementExpression')
    def extract_disable_stmt_expression(self, node) -> SignalResult:
        """DisableStatementExpression: disable statement"""
        return SignalResult()
    
    @on('DisableForkStatementExpression')
    def extract_disable_fork_expression(self, node) -> SignalResult:
        """DisableForkStatementExpression: disable fork"""
        return SignalResult()
    
    @on('BeginStatementExpression')
    def extract_begin_stmt_expression(self, node) -> SignalResult:
        """BeginStatementExpression: begin end block"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('ForkStatementExpression')
    def extract_fork_stmt_expression(self, node) -> SignalResult:
        """ForkStatementExpression: fork join"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('JoinAnyStatementExpression')
    def extract_join_any_expression(self, node) -> SignalResult:
        """JoinAnyStatementExpression: join any"""
        return SignalResult()
    
    @on('JoinNoneStatementExpression')
    def extract_join_none_expression(self, node) -> SignalResult:
        """JoinNoneStatementExpression: join none"""
        return SignalResult()
    
    @on('ParallelStatementExpression')
    def extract_parallel_stmt_expression(self, node) -> SignalResult:
        """ParallelStatementExpression: parallel statement"""
        result = SignalResult()
        body = getattr(node, 'body', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('CaseStatementExpression')
    def extract_case_stmt_expression(self, node) -> SignalResult:
        """CaseStatementExpression: case statement expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'condition', None)
        if expr:
            result = result.merge(self.extract(expr))
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('CaseItemStatementExpression')
    def extract_case_item_stmt_expression(self, node) -> SignalResult:
        """CaseItemStatementExpression: case item statement"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('IfStatementExpression')
    def extract_if_stmt_expression(self, node) -> SignalResult:
        """IfStatementExpression: if statement expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        true_body = getattr(node, 'true_body', None) or getattr(node, 'body', None)
        if true_body:
            result = result.merge(self.extract(true_body))
        false_body = getattr(node, 'false_body', None) or getattr(node, 'else_body', None)
        if false_body:
            result = result.merge(self.extract(false_body))
        return result
    
    @on('IfElseStatementExpression')
    def extract_if_else_stmt_expression(self, node) -> SignalResult:
        """IfElseStatementExpression: if else statement"""
        result = SignalResult()
        cond = getattr(node, 'condition', None)
        if cond:
            result = result.merge(self.extract(cond))
        true_body = getattr(node, 'true_body', None)
        if true_body:
            result = result.merge(self.extract(true_body))
        false_body = getattr(node, 'false_body', None)
        if false_body:
            result = result.merge(self.extract(false_body))
        return result
    
    @on('EmptyStatementExpression')
    def extract_empty_stmt_expression(self, node) -> SignalResult:
        """EmptyStatementExpression: empty statement"""
        return SignalResult()
    
    @on('ExpressionStatement')
    def extract_expression_stmt(self, node) -> SignalResult:
        """ExpressionStatement: expression statement"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('CompoundStatementExpression')
    def extract_compound_stmt_expression(self, node) -> SignalResult:
        """CompoundStatementExpression: compound statement"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('TimingControlStatementExpression')
    def extract_timing_control_stmt_expression(self, node) -> SignalResult:
        """TimingControlStatementExpression: timing control statement"""
        result = SignalResult()
        timing = getattr(node, 'timing', None) or getattr(node, 'control', None)
        if timing:
            result = result.merge(self.extract(timing))
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if stmt:
            result = result.merge(self.extract(stmt))
        return result
    
    @on('TimingDeclarationStatement')
    def extract_timing_decl_stmt(self, node) -> SignalResult:
        """TimingDeclarationStatement: timing declaration"""
        result = SignalResult()
        clock = getattr(node, 'clock', None) or getattr(node, 'event', None)
        if clock:
            result = result.merge(self.extract(clock))
        return result
    
    @on('ExpectStatementExpression')
    def extract_expect_stmt_expression(self, node) -> SignalResult:
        """ExpectStatementExpression: expect statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('CoverageStatementExpression')
    def extract_coverage_stmt_expression(self, node) -> SignalResult:
        """CoverageStatementExpression: coverage statement"""
        result = SignalResult()
        cover = getattr(node, 'cover', None) or getattr(node, 'expr', None)
        if cover:
            result = result.merge(self.extract(cover))
        return result
    
    @on('LetStatementExpression')
    def extract_let_stmt_expression(self, node) -> SignalResult:
        """LetStatementExpression: let statement"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        body = getattr(node, 'body', None) or getattr(node, 'expr', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('PatternStatementExpression')
    def extract_pattern_stmt_expression(self, node) -> SignalResult:
        """PatternStatementExpression: pattern statement"""
        result = SignalResult()
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        return result
    
    @on('ImmediateAssertStatementExpression')
    def extract_immediate_assert_stmt_expr(self, node) -> SignalResult:
        """ImmediateAssertStatementExpression: immediate assert"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('ImmediateAssumeStatementExpression')
    def extract_immediate_assume_stmt_expr(self, node) -> SignalResult:
        """ImmediateAssumeStatementExpression: immediate assume"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('ImmediateCoverStatementExpression')
    def extract_immediate_cover_stmt_expr(self, node) -> SignalResult:
        """ImmediateCoverStatementExpression: immediate cover"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('DeferredAssertStatementExpression')
    def extract_deferred_assert_stmt_expr(self, node) -> SignalResult:
        """DeferredAssertStatementExpression: deferred assert"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('DeferredAssumeStatementExpression')
    def extract_deferred_assume_stmt_expr(self, node) -> SignalResult:
        """DeferredAssumeStatementExpression: deferred assume"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('DeferredCoverStatementExpression')
    def extract_deferred_cover_stmt_expr(self, node) -> SignalResult:
        """DeferredCoverStatementExpression: deferred cover"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('DelayControl')
    def extract_delay_control(self, node) -> SignalResult:
        """DelayControl: #1 delay"""
        expr = getattr(node, 'expr', None) or getattr(node, 'delay', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('EventControl')
    def extract_event_control_stmt(self, node) -> SignalResult:
        """EventControl: @event"""
        event = getattr(node, 'event', None) or getattr(node, 'expr', None)
        if event:
            return self.extract(event)
        return SignalResult()
    
    @on('CycleDelayControl')
    def extract_cycle_delay_control(self, node) -> SignalResult:
        """CycleDelayControl: ##1 cycle delay"""
        return SignalResult()
    
    @on('ImplicitEventControl')
    def extract_implicit_event_control(self, node) -> SignalResult:
        """ImplicitEventControl: @@"""
        return SignalResult()
    
    @on('NullOtherControl')
    def extract_null_other_control(self, node) -> SignalResult:
        """NullOtherControl: null or other control"""
        return SignalResult()
    
    @on('SignallerEventControl')
    def extract_signaller_event_control(self, node) -> SignalResult:
        """SignallerEventControl: signaller event control"""
        result = SignalResult()
        sig = getattr(node, 'signaller', None) or getattr(node, 'expr', None)
        if sig:
            result = result.merge(self.extract(sig))
        return result
    
    @on('SequenceEventControl')
    def extract_sequence_event_control(self, node) -> SignalResult:
        """SequenceEventControl: sequence event control"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('ExpressionOrCondItem')
    def extract_expression_or_cond_item(self, node) -> SignalResult:
        """ExpressionOrCondItem: expression or condition item"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('IfElseConditionItem')
    def extract_if_else_condition_item(self, node) -> SignalResult:
        """IfElseConditionItem: if else condition item"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('SequenceConjunctionItem')
    def extract_sequence_conjunction_item(self, node) -> SignalResult:
        """SequenceConjunctionItem: sequence conjunction item"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'sequence', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('PropertyExprItem')
    def extract_property_expr_item(self, node) -> SignalResult:
        """PropertyExprItem: property expression item"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'property', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ClockingBlockEvent')
    def extract_clocking_block_event(self, node) -> SignalResult:
        """ClockingBlockEvent: clocking block event"""
        return SignalResult()
    
    @on('ProceduralTimingControl')
    def extract_procedural_timing_control(self, node) -> SignalResult:
        """ProceduralTimingControl: procedural timing control"""
        result = SignalResult()
        timing = getattr(node, 'timing', None) or getattr(node, 'control', None)
        if timing:
            result = result.merge(self.extract(timing))
        return result
    
    @on('TimingControlEvent')
    def extract_timing_control_event(self, node) -> SignalResult:
        """TimingControlEvent: timing control event"""
        result = SignalResult()
        event = getattr(node, 'event', None) or getattr(node, 'expr', None)
        if event:
            result = result.merge(self.extract(event))
        return result
    
    @on('TimingControlSequence')
    def extract_timing_control_sequence(self, node) -> SignalResult:
        """TimingControlSequence: timing control sequence"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('TimedStatement')
    def extract_timed_statement(self, node) -> SignalResult:
        """TimedStatement: timed statement"""
        result = SignalResult()
        timing = getattr(node, 'timing', None) or getattr(node, 'control', None)
        if timing:
            result = result.merge(self.extract(timing))
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if stmt:
            result = result.merge(self.extract(stmt))
        return result
    
    @on('ForeverLoopStatement')
    def extract_forever_loop_statement(self, node) -> SignalResult:
        """ForeverLoopStatement: forever loop"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('RepeatLoopStatement')
    def extract_repeat_loop_statement(self, node) -> SignalResult:
        """RepeatLoopStatement: repeat loop"""
        result = SignalResult()
        cond = getattr(node, 'cond', None) or getattr(node, 'expression', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('WaitForkStatement')
    def extract_wait_fork_statement(self, node) -> SignalResult:
        """WaitForkStatement: wait fork"""
        return SignalResult()
    
    @on('WaitOrderStatement')
    def extract_wait_order_statement(self, node) -> SignalResult:
        """WaitOrderStatement: wait order"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('EventTriggerStatement')
    def extract_event_trigger_statement(self, node) -> SignalResult:
        """EventTriggerStatement: event trigger"""
        event = getattr(node, 'event', None) or getattr(node, 'expr', None)
        if event:
            return self.extract(event)
        return SignalResult()
    
    @on('ProceduralAssignStatement')
    def extract_procedural_assign_statement(self, node) -> SignalResult:
        """ProceduralAssignStatement: procedural assign"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, 'rvalue', None) or getattr(node, 'expr', None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result
    
    @on('ProceduralDeassignStatement')
    def extract_procedural_deassign_statement(self, node) -> SignalResult:
        """ProceduralDeassignStatement: procedural deassign"""
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()
    
    @on('RandCaseStatement')
    def extract_rand_case_statement(self, node) -> SignalResult:
        """RandCaseStatement: rand case"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('RandCaseItem')
    def extract_rand_case_item(self, node) -> SignalResult:
        """RandCaseItem: rand case item"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'weight', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('ProceduralCheckerStatement')
    def extract_procedural_checker_statement(self, node) -> SignalResult:
        """ProceduralCheckerStatement: procedural checker"""
        return SignalResult()
    
    @on('BlockStatement')
    def extract_block_statement(self, node) -> SignalResult:
        """BlockStatement: block statement"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('ListStatement')
    def extract_list_statement(self, node) -> SignalResult:
        """ListStatement: list of statements"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'statements', None)
        if items and hasattr(items, '__iter__'):
            for stmt in items:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('ConditionalStatement')
    def extract_conditional_statement(self, node) -> SignalResult:
        """ConditionalStatement: conditional statement"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        true_body = getattr(node, 'true_body', None) or getattr(node, 'body', None)
        if true_body:
            result = result.merge(self.extract(true_body))
        false_body = getattr(node, 'false_body', None) or getattr(node, 'else_body', None)
        if false_body:
            result = result.merge(self.extract(false_body))
        return result
    
    # Constraint kinds
    @on('ConstraintList')
    def extract_constraint_list(self, node) -> SignalResult:
        """ConstraintList: constraint list"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ConstraintExpression')
    def extract_constraint_expression(self, node) -> SignalResult:
        """ConstraintExpression: expression constraint"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('ConstraintImplication')
    def extract_constraint_implication(self, node) -> SignalResult:
        """ConstraintImplication: implication constraint"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'constraint', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('ConstraintConditional')
    def extract_constraint_conditional(self, node) -> SignalResult:
        """ConstraintConditional: conditional constraint"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        true_body = getattr(node, 'true_body', None) or getattr(node, 'constraint', None)
        if true_body:
            result = result.merge(self.extract(true_body))
        false_body = getattr(node, 'false_body', None)
        if false_body:
            result = result.merge(self.extract(false_body))
        return result
    
    @on('ConstraintUniqueness')
    def extract_constraint_uniqueness(self, node) -> SignalResult:
        """ConstraintUniqueness: uniqueness constraint"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ConstraintDisableSoft')
    def extract_constraint_disable_soft(self, node) -> SignalResult:
        """ConstraintDisableSoft: disable soft constraint"""
        return SignalResult()
    
    @on('ConstraintSolveBefore')
    def extract_constraint_solve_before(self, node) -> SignalResult:
        """ConstraintSolveBefore: solve before constraint"""
        result = SignalResult()
        before = getattr(node, 'before', None)
        after = getattr(node, 'after', None)
        if before:
            result = result.merge(self.extract(before))
        if after:
            result = result.merge(self.extract(after))
        return result
    
    @on('ConstraintForeach')
    def extract_constraint_foreach(self, node) -> SignalResult:
        """ConstraintForeach: foreach constraint"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        body = getattr(node, 'body', None) or getattr(node, 'constraint', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    # Pattern kinds
    @on('WildcardPatternKind')
    def extract_wildcard_pattern_kind(self, node) -> SignalResult:
        """WildcardPatternKind: wildcard pattern"""
        return SignalResult()
    
    @on('ConstantPattern')
    def extract_constant_pattern(self, node) -> SignalResult:
        """ConstantPattern: constant pattern"""
        expr = getattr(node, 'expr', None) or getattr(node, 'value', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('VariablePattern')
    def extract_variable_pattern(self, node) -> SignalResult:
        """VariablePattern: variable pattern"""
        var = getattr(node, 'var', None) or getattr(node, 'expr', None)
        if var:
            return self.extract(var)
        return SignalResult()
    
    @on('TaggedPatternKind')
    def extract_tagged_pattern_kind(self, node) -> SignalResult:
        """TaggedPatternKind: tagged pattern"""
        result = SignalResult()
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        return result
    
    @on('StructurePattern')
    def extract_structure_pattern(self, node) -> SignalResult:
        """StructurePattern: structure pattern"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'patterns', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Assertion expr kinds
    @on('AssertExpression')
    def extract_assert_expression(self, node) -> SignalResult:
        """AssertExpression: assert expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('AssumeExpression')
    def extract_assume_expression(self, node) -> SignalResult:
        """AssumeExpression: assume expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('CoverPropertyExpression')
    def extract_cover_property_expr(self, node) -> SignalResult:
        """CoverPropertyExpression: cover property expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('CoverSequenceExpression')
    def extract_cover_sequence_expr(self, node) -> SignalResult:
        """CoverSequenceExpression: cover sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('RestrictExpression')
    def extract_restrict_expression(self, node) -> SignalResult:
        """RestrictExpression: restrict expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('ExpectExpression')
    def extract_expect_expression(self, node) -> SignalResult:
        """ExpectExpression: expect expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('SimpleAssertExpression')
    def extract_simple_assert_expression(self, node) -> SignalResult:
        """SimpleAssertExpression: simple assertion expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('SequenceConcatExpression')
    def extract_sequence_concat_expr(self, node) -> SignalResult:
        """SequenceConcatExpression: sequence concat expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SequenceWithMatchExpression')
    def extract_sequence_with_match_expr(self, node) -> SignalResult:
        """SequenceWithMatchExpression: sequence with match"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        match = getattr(node, 'match', None) or getattr(node, 'expr2', None)
        if match:
            result = result.merge(self.extract(match))
        return result
    
    @on('UnaryAssertExpression')
    def extract_unary_assert_expression(self, node) -> SignalResult:
        """UnaryAssertExpression: unary assertion expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('BinaryAssertExpression')
    def extract_binary_assert_expression(self, node) -> SignalResult:
        """BinaryAssertExpression: binary assertion expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('FirstMatchAssertExpression')
    def extract_first_match_assert_expr(self, node) -> SignalResult:
        """FirstMatchAssertExpression: first_match assertion"""
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            return self.extract(seq)
        return SignalResult()
    
    @on('ClockingAssertExpression')
    def extract_clocking_assert_expr(self, node) -> SignalResult:
        """ClockingAssertExpression: clocking assertion expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        clock = getattr(node, 'clock', None)
        if clock:
            result = result.merge(self.extract(clock))
        return result
    
    @on('StrongWeakAssertExpression')
    def extract_strong_weak_assert_expr(self, node) -> SignalResult:
        """StrongWeakAssertExpression: strong/weak assertion"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('AbortAssertExpression')
    def extract_abort_assert_expr(self, node) -> SignalResult:
        """AbortAssertExpression: abort assertion expression"""
        result = SignalResult()
        left = getattr(node, 'left', None) or getattr(node, 'expr', None)
        right = getattr(node, 'right', None) or getattr(node, 'abort', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ConditionalAssertExpression')
    def extract_conditional_assert_expr(self, node) -> SignalResult:
        """ConditionalAssertExpression: conditional assertion"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        else_expr = getattr(node, 'else_body', None) or getattr(node, 'expr2', None)
        if else_expr:
            result = result.merge(self.extract(else_expr))
        return result
    
    @on('CaseAssertExpression')
    def extract_case_assert_expr(self, node) -> SignalResult:
        """CaseAssertExpression: case assertion expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('DisableIffAssertExpression')
    def extract_disable_iff_assert_expr(self, node) -> SignalResult:
        """DisableIffAssertExpression: disable iff assertion"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        disable = getattr(node, 'disable', None) or getattr(node, 'expr2', None)
        if disable:
            result = result.merge(self.extract(disable))
        return result
    
    # Timing control kinds
    @on('InvalidTimingControl')
    def extract_invalid_timing_control(self, node) -> SignalResult:
        """InvalidTimingControl: invalid timing control"""
        return SignalResult()
    
    @on('DelayTimingControl')
    def extract_delay_timing_control(self, node) -> SignalResult:
        """DelayTimingControl: #delay timing control"""
        result = SignalResult()
        delay = getattr(node, 'delay', None) or getattr(node, 'expr', None)
        if delay:
            result = result.merge(self.extract(delay))
        return result
    
    @on('SignalEventTimingControl')
    def extract_signal_event_timing_control(self, node) -> SignalResult:
        """SignalEventTimingControl: signal event timing control"""
        result = SignalResult()
        event = getattr(node, 'event', None) or getattr(node, 'expr', None)
        if event:
            result = result.merge(self.extract(event))
        return result
    
    @on('EventListTimingControl')
    def extract_event_list_timing_control(self, node) -> SignalResult:
        """EventListTimingControl: event list timing control"""
        result = SignalResult()
        events = getattr(node, 'events', None) or getattr(node, 'items', None)
        if events and hasattr(events, '__iter__'):
            for ev in events:
                if ev:
                    result = result.merge(self.extract(ev))
        return result
    
    @on('ImplicitEventTimingControl')
    def extract_implicit_event_timing_control(self, node) -> SignalResult:
        """ImplicitEventTimingControl: implicit event timing control"""
        return SignalResult()
    
    @on('RepeatedEventTimingControl')
    def extract_repeated_event_timing_control(self, node) -> SignalResult:
        """RepeatedEventTimingControl: repeated event timing control"""
        result = SignalResult()
        count = getattr(node, 'count', None) or getattr(node, 'expr', None)
        if count:
            result = result.merge(self.extract(count))
        event = getattr(node, 'event', None) or getattr(node, 'expr2', None)
        if event:
            result = result.merge(self.extract(event))
        return result
    
    @on('Delay3TimingControl')
    def extract_delay3_timing_control(self, node) -> SignalResult:
        """Delay3TimingControl: delay3 timing control"""
        result = SignalResult()
        delay = getattr(node, 'delay', None) or getattr(node, 'expr', None)
        if delay:
            result = result.merge(self.extract(delay))
        return result
    
    @on('OneStepDelayTimingControl')
    def extract_one_step_delay_timing_control(self, node) -> SignalResult:
        """OneStepDelayTimingControl: one step delay"""
        return SignalResult()
    
    @on('CycleDelayTimingControl')
    def extract_cycle_delay_timing_control(self, node) -> SignalResult:
        """CycleDelayTimingControl: cycle delay ##N"""
        result = SignalResult()
        count = getattr(node, 'count', None) or getattr(node, 'expr', None)
        if count:
            result = result.merge(self.extract(count))
        return result
    
    @on('BlockEventListTimingControl')
    def extract_block_event_list_timing_control(self, node) -> SignalResult:
        """BlockEventListTimingControl: block event list timing control"""
        result = SignalResult()
        events = getattr(node, 'events', None) or getattr(node, 'items', None)
        if events and hasattr(events, '__iter__'):
            for ev in events:
                if ev:
                    result = result.merge(self.extract(ev))
        return result
    
    # Range selection kinds
    @on('SimpleRangeSelection')
    def extract_simple_range_selection(self, node) -> SignalResult:
        """SimpleRangeSelection: simple range selection"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('IndexedUpRangeSelection')
    def extract_indexed_up_range_selection(self, node) -> SignalResult:
        """IndexedUpRangeSelection: indexed up range selection"""
        base = getattr(node, 'base', None) or getattr(node, 'expr', None)
        if base:
            return self.extract(base)
        return SignalResult()
    
    @on('IndexedDownRangeSelection')
    def extract_indexed_down_range_selection(self, node) -> SignalResult:
        """IndexedDownRangeSelection: indexed down range selection"""
        base = getattr(node, 'base', None) or getattr(node, 'expr', None)
        if base:
            return self.extract(base)
        return SignalResult()
    
    # Bins select expression kinds
    @on('InvalidBinsSelectExpr')
    def extract_invalid_bins_select_expr(self, node) -> SignalResult:
        """InvalidBinsSelectExpr: invalid bins select expression"""
        return SignalResult()
    
    @on('ConditionBinsSelectExpr')
    def extract_condition_bins_select_expr(self, node) -> SignalResult:
        """ConditionBinsSelectExpr: condition bins select expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        return result
    
    @on('UnaryBinsSelectExpr')
    def extract_unary_bins_select_expr(self, node) -> SignalResult:
        """UnaryBinsSelectExpr: unary bins select expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('BinaryBinsSelectExpr')
    def extract_binary_bins_select_expr(self, node) -> SignalResult:
        """BinaryBinsSelectExpr: binary bins select expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SetBinsSelectExpr')
    def extract_set_bins_select_expr(self, node) -> SignalResult:
        """SetBinsSelectExpr: set bins select expression"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'set', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('WithFilterBinsSelectExpr')
    def extract_with_filter_bins_select_expr(self, node) -> SignalResult:
        """WithFilterBinsSelectExpr: with filter bins select expression"""
        result = SignalResult()
        with_expr = getattr(node, 'with', None) or getattr(node, 'expr', None)
        if with_expr:
            result = result.merge(self.extract(with_expr))
        filter_expr = getattr(node, 'filter', None) or getattr(node, 'expr2', None)
        if filter_expr:
            result = result.merge(self.extract(filter_expr))
        return result
    
    @on('CrossIdBinsSelectExpr')
    def extract_cross_id_bins_select_expr(self, node) -> SignalResult:
        """CrossIdBinsSelectExpr: cross id bins select expression"""
        return SignalResult()
    
    # Definition kinds
    @on('ModuleDefinition')
    def extract_module_definition(self, node) -> SignalResult:
        """ModuleDefinition: module definition"""
        return SignalResult()
    
    @on('InterfaceDefinition')
    def extract_interface_definition(self, node) -> SignalResult:
        """InterfaceDefinition: interface definition"""
        return SignalResult()
    
    @on('ProgramDefinition')
    def extract_program_definition(self, node) -> SignalResult:
        """ProgramDefinition: program definition"""
        return SignalResult()
    
    # Conversion kinds
    @on('ImplicitConversion')
    def extract_implicit_conversion(self, node) -> SignalResult:
        """ImplicitConversion: implicit conversion"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PropagatedConversion')
    def extract_propagated_conversion(self, node) -> SignalResult:
        """PropagatedConversion: propagated conversion"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('StreamingConcatConversion')
    def extract_streaming_concat_conversion(self, node) -> SignalResult:
        """StreamingConcatConversion: streaming concat conversion"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'expr', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ExplicitConversion')
    def extract_explicit_conversion(self, node) -> SignalResult:
        """ExplicitConversion: explicit conversion"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('BitstreamCastConversion')
    def extract_bitstream_cast_conversion(self, node) -> SignalResult:
        """BitstreamCastConversion: bitstream cast conversion"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Subroutine kinds
    @on('FunctionSubroutine')
    def extract_function_subroutine(self, node) -> SignalResult:
        """FunctionSubroutine: function subroutine"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('TaskSubroutine')
    def extract_task_subroutine(self, node) -> SignalResult:
        """TaskSubroutine: task subroutine"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    # Procedural block kinds
    @on('InitialProceduralBlock')
    def extract_initial_procedural_block(self, node) -> SignalResult:
        """InitialProceduralBlock: initial block"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('FinalProceduralBlock')
    def extract_final_procedural_block(self, node) -> SignalResult:
        """FinalProceduralBlock: final block"""
        result = SignalResult()
        body = getattr(node, 'body', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('AlwaysProceduralBlock')
    def extract_always_procedural_block(self, node) -> SignalResult:
        """AlwaysProceduralBlock: always block"""
        result = SignalResult()
        body = getattr(node, 'body', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('AlwaysCombProceduralBlock')
    def extract_always_comb_procedural_block(self, node) -> SignalResult:
        """AlwaysCombProceduralBlock: always_comb block"""
        result = SignalResult()
        body = getattr(node, 'body', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('AlwaysLatchProceduralBlock')
    def extract_always_latch_procedural_block(self, node) -> SignalResult:
        """AlwaysLatchProceduralBlock: always_latch block"""
        result = SignalResult()
        body = getattr(node, 'body', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('AlwaysFFProceduralBlock')
    def extract_always_ff_procedural_block(self, node) -> SignalResult:
        """AlwaysFFProceduralBlock: always_ff block"""
        result = SignalResult()
        body = getattr(node, 'body', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    # System timing check kinds
    @on('SetupTimingCheck')
    def extract_setup_timing_check(self, node) -> SignalResult:
        """SetupTimingCheck: setup timing check"""
        return SignalResult()
    
    @on('HoldTimingCheck')
    def extract_hold_timing_check(self, node) -> SignalResult:
        """HoldTimingCheck: hold timing check"""
        return SignalResult()
    
    @on('SetupHoldTimingCheck')
    def extract_setup_hold_timing_check(self, node) -> SignalResult:
        """SetupHoldTimingCheck: setup hold timing check"""
        return SignalResult()
    
    @on('RecoveryTimingCheck')
    def extract_recovery_timing_check(self, node) -> SignalResult:
        """RecoveryTimingCheck: recovery timing check"""
        return SignalResult()
    
    @on('RemovalTimingCheck')
    def extract_removal_timing_check(self, node) -> SignalResult:
        """RemovalTimingCheck: removal timing check"""
        return SignalResult()
    
    @on('RecRemTimingCheck')
    def extract_rec_rem_timing_check(self, node) -> SignalResult:
        """RecRemTimingCheck: recrem timing check"""
        return SignalResult()
    
    @on('SkewTimingCheck')
    def extract_skew_timing_check(self, node) -> SignalResult:
        """SkewTimingCheck: skew timing check"""
        return SignalResult()
    
    @on('TimeSkewTimingCheck')
    def extract_time_skew_timing_check(self, node) -> SignalResult:
        """TimeSkewTimingCheck: time skew timing check"""
        return SignalResult()
    
    @on('FullSkewTimingCheck')
    def extract_full_skew_timing_check(self, node) -> SignalResult:
        """FullSkewTimingCheck: full skew timing check"""
        return SignalResult()
    
    @on('PeriodTimingCheck')
    def extract_period_timing_check(self, node) -> SignalResult:
        """PeriodTimingCheck: period timing check"""
        return SignalResult()
    
    @on('WidthTimingCheck')
    def extract_width_timing_check(self, node) -> SignalResult:
        """WidthTimingCheck: width timing check"""
        return SignalResult()
    
    @on('NoChangeTimingCheck')
    def extract_no_change_timing_check(self, node) -> SignalResult:
        """NoChangeTimingCheck: nochange timing check"""
        return SignalResult()
    
    # Pulse style kinds
    @on('OnEventPulseStyle')
    def extract_on_event_pulse_style(self, node) -> SignalResult:
        """OnEventPulseStyle: on_event pulse style"""
        return SignalResult()
    
    @on('OnDetectPulseStyle')
    def extract_on_detect_pulse_style(self, node) -> SignalResult:
        """OnDetectPulseStyle: on_detect pulse style"""
        return SignalResult()
    
    @on('ShowCancelledPulseStyle')
    def extract_show_cancelled_pulse_style(self, node) -> SignalResult:
        """ShowCancelledPulseStyle: show_cancelled pulse style"""
        return SignalResult()
    
    @on('NoShowCancelledPulseStyle')
    def extract_no_show_cancelled_pulse_style(self, node) -> SignalResult:
        """NoShowCancelledPulseStyle: no_show_cancelled pulse style"""
        return SignalResult()
    
    # Edge kinds
    @on('NoEdge')
    def extract_no_edge(self, node) -> SignalResult:
        """NoEdge: no edge"""
        return SignalResult()
    
    @on('PosEdge')
    def extract_pos_edge(self, node) -> SignalResult:
        """PosEdge: positive edge"""
        expr = getattr(node, 'expr', None) or getattr(node, 'signal', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('NegEdge')
    def extract_neg_edge(self, node) -> SignalResult:
        """NegEdge: negative edge"""
        expr = getattr(node, 'expr', None) or getattr(node, 'signal', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('BothEdges')
    def extract_both_edges(self, node) -> SignalResult:
        """BothEdges: both edges"""
        expr = getattr(node, 'expr', None) or getattr(node, 'signal', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Dimension kinds
    @on('UnknownDimension')
    def extract_unknown_dimension(self, node) -> SignalResult:
        """UnknownDimension: unknown dimension"""
        return SignalResult()
    
    @on('RangeDimension')
    def extract_range_dimension(self, node) -> SignalResult:
        """RangeDimension: range dimension"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('AbbreviatedRangeDimension')
    def extract_abbreviated_range_dimension(self, node) -> SignalResult:
        """AbbreviatedRangeDimension: abbreviated range dimension"""
        return SignalResult()
    
    @on('DynamicDimension')
    def extract_dynamic_dimension(self, node) -> SignalResult:
        """DynamicDimension: dynamic dimension"""
        return SignalResult()
    
    @on('AssociativeDimension')
    def extract_associative_dimension(self, node) -> SignalResult:
        """AssociativeDimension: associative dimension"""
        result = SignalResult()
        index = getattr(node, 'index', None) or getattr(node, 'expr', None)
        if index:
            result = result.merge(self.extract(index))
        return result
    
    @on('QueueDimension')
    def extract_queue_dimension(self, node) -> SignalResult:
        """QueueDimension: queue dimension"""
        result = SignalResult()
        size = getattr(node, 'size', None) or getattr(node, 'expr', None)
        if size:
            result = result.merge(self.extract(size))
        return result
    
    @on('DPIOpenArrayDimension')
    def extract_dpi_open_array_dimension(self, node) -> SignalResult:
        """DPIOpenArrayDimension: DPI open array dimension"""
        return SignalResult()
    
    # Value range kinds
    @on('SimpleValueRange')
    def extract_simple_value_range(self, node) -> SignalResult:
        """SimpleValueRange: simple value range"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('AbsoluteToleranceValueRange')
    def extract_absolute_tolerance_value_range(self, node) -> SignalResult:
        """AbsoluteToleranceValueRange: absolute tolerance value range"""
        result = SignalResult()
        range_expr = getattr(node, 'range', None)
        if range_expr:
            result = result.merge(self.extract(range_expr))
        return result
    
    @on('RelativeToleranceValueRange')
    def extract_relative_tolerance_value_range(self, node) -> SignalResult:
        """RelativeToleranceValueRange: relative tolerance value range"""
        result = SignalResult()
        range_expr = getattr(node, 'range', None)
        if range_expr:
            result = result.merge(self.extract(range_expr))
        return result
    
    # ElabSystemTaskKind
    @on('FatalElabSystemTask')
    def extract_fatal_elab_system_task(self, node) -> SignalResult:
        """FatalElabSystemTask: fatal elaboration system task"""
        return SignalResult()
    
    @on('ErrorElabSystemTask')
    def extract_error_elab_system_task(self, node) -> SignalResult:
        """ErrorElabSystemTask: error elaboration system task"""
        return SignalResult()
    
    @on('WarningElabSystemTask')
    def extract_warning_elab_system_task(self, node) -> SignalResult:
        """WarningElabSystemTask: warning elaboration system task"""
        return SignalResult()
    
    @on('InfoElabSystemTask')
    def extract_info_elab_system_task(self, node) -> SignalResult:
        """InfoElabSystemTask: info elaboration system task"""
        return SignalResult()
    
    @on('StaticAssertElabSystemTask')
    def extract_static_assert_elab_system_task(self, node) -> SignalResult:
        """StaticAssertElabSystemTask: static assert elaboration system task"""
        return SignalResult()
    
    # Trivia kinds
    @on('UnknownTrivia')
    def extract_unknown_trivia(self, node) -> SignalResult:
        """UnknownTrivia: unknown trivia"""
        return SignalResult()
    
    @on('WhitespaceTrivia')
    def extract_whitespace_trivia(self, node) -> SignalResult:
        """WhitespaceTrivia: whitespace trivia"""
        return SignalResult()
    
    @on('EndOfLineTrivia')
    def extract_end_of_line_trivia(self, node) -> SignalResult:
        """EndOfLineTrivia: end of line trivia"""
        return SignalResult()
    
    @on('LineCommentTrivia')
    def extract_line_comment_trivia(self, node) -> SignalResult:
        """LineCommentTrivia: line comment trivia"""
        return SignalResult()
    
    @on('BlockCommentTrivia')
    def extract_block_comment_trivia(self, node) -> SignalResult:
        """BlockCommentTrivia: block comment trivia"""
        return SignalResult()
    
    @on('DisabledTextTrivia')
    def extract_disabled_text_trivia(self, node) -> SignalResult:
        """DisabledTextTrivia: disabled text trivia"""
        return SignalResult()
    
    @on('SkippedTokensTrivia')
    def extract_skipped_tokens_trivia(self, node) -> SignalResult:
        """SkippedTokensTrivia: skipped tokens trivia"""
        return SignalResult()
    
    @on('SkippedSyntaxTrivia')
    def extract_skipped_syntax_trivia(self, node) -> SignalResult:
        """SkippedSyntaxTrivia: skipped syntax trivia"""
        return SignalResult()
    
    @on('DirectiveTrivia')
    def extract_directive_trivia(self, node) -> SignalResult:
        """DirectiveTrivia: directive trivia"""
        return SignalResult()
    
    # Statement block kinds
    @on('SequentialStatementBlock')
    def extract_sequential_statement_block(self, node) -> SignalResult:
        """SequentialStatementBlock: sequential statement block"""
        result = SignalResult()
        stmts = getattr(node, 'statements', None) or getattr(node, 'body', None)
        if stmts and hasattr(stmts, '__iter__'):
            for stmt in stmts:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('JoinAllStatementBlock')
    def extract_join_all_statement_block(self, node) -> SignalResult:
        """JoinAllStatementBlock: join all statement block"""
        result = SignalResult()
        stmts = getattr(node, 'statements', None) or getattr(node, 'body', None)
        if stmts and hasattr(stmts, '__iter__'):
            for stmt in stmts:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('JoinAnyStatementBlock')
    def extract_join_any_statement_block(self, node) -> SignalResult:
        """JoinAnyStatementBlock: join any statement block"""
        result = SignalResult()
        stmts = getattr(node, 'statements', None) or getattr(node, 'body', None)
        if stmts and hasattr(stmts, '__iter__'):
            for stmt in stmts:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('JoinNoneStatementBlock')
    def extract_join_none_statement_block(self, node) -> SignalResult:
        """JoinNoneStatementBlock: join none statement block"""
        result = SignalResult()
        stmts = getattr(node, 'statements', None) or getattr(node, 'body', None)
        if stmts and hasattr(stmts, '__iter__'):
            for stmt in stmts:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    # Additional SyntaxKind expression handlers
    @on('AddExpression')
    def extract_add_expression(self, node) -> SignalResult:
        """AddExpression: addition expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SubtractExpression')
    def extract_subtract_expression(self, node) -> SignalResult:
        """SubtractExpression: subtraction expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('MultiplyExpression')
    def extract_multiply_expression(self, node) -> SignalResult:
        """MultiplyExpression: multiplication expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('DivideExpression')
    def extract_divide_expression(self, node) -> SignalResult:
        """DivideExpression: division expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ModuloExpression')
    def extract_modulo_expression(self, node) -> SignalResult:
        """ModuloExpression: modulo expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('BinaryAndExpression')
    def extract_binary_and_expression(self, node) -> SignalResult:
        """BinaryAndExpression: binary and expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('BinaryOrExpression')
    def extract_binary_or_expression(self, node) -> SignalResult:
        """BinaryOrExpression: binary or expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('BinaryXorExpression')
    def extract_binary_xor_expression(self, node) -> SignalResult:
        """BinaryXorExpression: binary xor expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('BinaryXnorExpression')
    def extract_binary_xnor_expression(self, node) -> SignalResult:
        """BinaryXnorExpression: binary xnor expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('EqualityExpression')
    def extract_equality_expression(self, node) -> SignalResult:
        """EqualityExpression: equality expression =="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('InequalityExpression')
    def extract_inequality_expression(self, node) -> SignalResult:
        """InequalityExpression: inequality expression !="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('CaseEqualityExpression')
    def extract_case_equality_expression(self, node) -> SignalResult:
        """CaseEqualityExpression: case equality expression ==="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('CaseInequalityExpression')
    def extract_case_inequality_expression(self, node) -> SignalResult:
        """CaseInequalityExpression: case inequality expression !=="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LessThanExpression')
    def extract_less_than_expression(self, node) -> SignalResult:
        """LessThanExpression: less than expression <"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LessThanOrEqualExpression')
    def extract_less_than_or_equal_expression(self, node) -> SignalResult:
        """LessThanOrEqualExpression: less than or equal expression <="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('GreaterThanExpression')
    def extract_greater_than_expression(self, node) -> SignalResult:
        """GreaterThanExpression: greater than expression >"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('GreaterThanOrEqualExpression')
    def extract_greater_than_or_equal_expression(self, node) -> SignalResult:
        """GreaterThanOrEqualExpression: greater than or equal expression >="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('WildcardEqualityExpression')
    def extract_wildcard_equality_expression(self, node) -> SignalResult:
        """WildcardEqualityExpression: wildcard equality expression ==?"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('WildcardInequalityExpression')
    def extract_wildcard_inequality_expression(self, node) -> SignalResult:
        """WildcardInequalityExpression: wildcard inequality expression !=?"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('AndPropertyExpr')
    def extract_and_property_expr(self, node) -> SignalResult:
        """AndPropertyExpr: and property expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('OrPropertyExpr')
    def extract_or_property_expr(self, node) -> SignalResult:
        """OrPropertyExpr: or property expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ImplicationPropertyExpr')
    def extract_implication_property_expr(self, node) -> SignalResult:
        """ImplicationPropertyExpr: implication property expression"""
        result = SignalResult()
        left = getattr(node, 'left', None) or getattr(node, 'antecedent', None)
        right = getattr(node, 'right', None) or getattr(node, 'consequent', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('AndSequenceExpr')
    def extract_and_sequence_expr(self, node) -> SignalResult:
        """AndSequenceExpr: and sequence expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('OrSequenceExpr')
    def extract_or_sequence_expr(self, node) -> SignalResult:
        """OrSequenceExpr: or sequence expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('FirstMatchSequenceExpr')
    def extract_first_match_sequence_expr(self, node) -> SignalResult:
        """FirstMatchSequenceExpr: first_match sequence expression"""
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            return self.extract(seq)
        return SignalResult()
    
    @on('ClockingSequenceExpr')
    def extract_clocking_sequence_expr(self, node) -> SignalResult:
        """ClockingSequenceExpr: clocking sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        clock = getattr(node, 'clock', None)
        if clock:
            result = result.merge(self.extract(clock))
        return result
    
    # More SyntaxKind expression handlers
    @on('ArithmeticShiftLeftExpression')
    def extract_arithmetic_shift_left_expression(self, node) -> SignalResult:
        """ArithmeticShiftLeftExpression: arithmetic shift left <<<"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ArithmeticShiftRightExpression')
    def extract_arithmetic_shift_right_expression(self, node) -> SignalResult:
        """ArithmeticShiftRightExpression: arithmetic shift right >>>"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LogicalLeftShiftExpression')
    def extract_logical_left_shift_expression(self, node) -> SignalResult:
        """LogicalLeftShiftExpression: logical left shift <<"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LogicalRightShiftExpression')
    def extract_logical_right_shift_expression(self, node) -> SignalResult:
        """LogicalRightShiftExpression: logical right shift >>"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('PowerExpression')
    def extract_power_expression(self, node) -> SignalResult:
        """PowerExpression: power expression **"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('UnaryAndExpression')
    def extract_unary_and_expression(self, node) -> SignalResult:
        """UnaryAndExpression: unary and expression &"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryOrExpression')
    def extract_unary_or_expression(self, node) -> SignalResult:
        """UnaryOrExpression: unary or expression |"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryXorExpression')
    def extract_unary_xor_expression(self, node) -> SignalResult:
        """UnaryXorExpression: unary xor expression ^"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryNandExpression')
    def extract_unary_nand_expression(self, node) -> SignalResult:
        """UnaryNandExpression: unary nand expression ~&"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryNorExpression')
    def extract_unary_nor_expression(self, node) -> SignalResult:
        """UnaryNorExpression: unary nor expression ~|"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryXnorExpression')
    def extract_unary_xnor_expression(self, node) -> SignalResult:
        """UnaryXnorExpression: unary xnor expression ^~"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PostIncrementExpression')
    def extract_post_increment_expression(self, node) -> SignalResult:
        """PostIncrementExpression: post increment expression i++"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PostDecrementExpression')
    def extract_post_decrement_expression(self, node) -> SignalResult:
        """PostDecrementExpression: post decrement expression i--"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PreIncrementExpression')
    def extract_pre_increment_expression(self, node) -> SignalResult:
        """PreIncrementExpression: pre increment expression ++i"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PreDecrementExpression')
    def extract_pre_decrement_expression(self, node) -> SignalResult:
        """PreDecrementExpression: pre decrement expression --i"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('AddAssignmentExpression')
    def extract_add_assignment_expression(self, node) -> SignalResult:
        """AddAssignmentExpression: add assignment +="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SubtractAssignmentExpression')
    def extract_subtract_assignment_expression(self, node) -> SignalResult:
        """SubtractAssignmentExpression: subtract assignment -="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('AndAssignmentExpression')
    def extract_and_assignment_expression(self, node) -> SignalResult:
        """AndAssignmentExpression: and assignment &="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('OrAssignmentExpression')
    def extract_or_assignment_expression(self, node) -> SignalResult:
        """OrAssignmentExpression: or assignment |="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('XorAssignmentExpression')
    def extract_xor_assignment_expression(self, node) -> SignalResult:
        """XorAssignmentExpression: xor assignment ^="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ArithmeticLeftShiftAssignmentExpression')
    def extract_arithmetic_left_shift_assignment(self, node) -> SignalResult:
        """ArithmeticLeftShiftAssignmentExpression: <<<="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ArithmeticRightShiftAssignmentExpression')
    def extract_arithmetic_right_shift_assignment(self, node) -> SignalResult:
        """ArithmeticRightShiftAssignmentExpression: >>>="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LogicalLeftShiftAssignmentExpression')
    def extract_logical_left_shift_assignment(self, node) -> SignalResult:
        """LogicalLeftShiftAssignmentExpression: <<="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LogicalRightShiftAssignmentExpression')
    def extract_logical_right_shift_assignment(self, node) -> SignalResult:
        """LogicalRightShiftAssignmentExpression: >>="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('MultiplyAssignmentExpression')
    def extract_multiply_assignment_expression(self, node) -> SignalResult:
        """MultiplyAssignmentExpression: *="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('DivideAssignmentExpression')
    def extract_divide_assignment_expression(self, node) -> SignalResult:
        """DivideAssignmentExpression: /="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ModuloAssignmentExpression')
    def extract_modulo_assignment_expression(self, node) -> SignalResult:
        """ModuloAssignmentExpression: %="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Type-related expressions
    @on('BitType')
    def extract_bit_type(self, node) -> SignalResult:
        """BitType: bit type"""
        return SignalResult()
    
    @on('ByteType')
    def extract_byte_type(self, node) -> SignalResult:
        """ByteType: byte type"""
        return SignalResult()
    
    @on('CHandleType')
    def extract_chandle_type(self, node) -> SignalResult:
        """CHandleType: chandle type"""
        return SignalResult()
    
    @on('IntType')
    def extract_int_type(self, node) -> SignalResult:
        """IntType: int type"""
        return SignalResult()
    
    @on('LongIntType')
    def extract_long_int_type(self, node) -> SignalResult:
        """LongIntType: longint type"""
        return SignalResult()
    
    @on('ShortIntType')
    def extract_short_int_type(self, node) -> SignalResult:
        """ShortIntType: shortint type"""
        return SignalResult()
    
    @on('IntegerType')
    def extract_integer_type(self, node) -> SignalResult:
        """IntegerType: integer type"""
        return SignalResult()
    
    @on('LogicType')
    def extract_logic_type(self, node) -> SignalResult:
        """LogicType: logic type"""
        return SignalResult()
    
    @on('RegType')
    def extract_reg_type(self, node) -> SignalResult:
        """RegType: reg type"""
        return SignalResult()
    
    @on('BitVectorType')
    def extract_bit_vector_type(self, node) -> SignalResult:
        """BitVectorType: bit vector type"""
        return SignalResult()
    
    @on('StringType')
    def extract_string_type(self, node) -> SignalResult:
        """StringType: string type"""
        return SignalResult()
    
    @on('EventType')
    def extract_event_type(self, node) -> SignalResult:
        """EventType: event type"""
        return SignalResult()
    
    @on('VoidType')
    def extract_void_type(self, node) -> SignalResult:
        """VoidType: void type"""
        return SignalResult()
    
    @on('RealType')
    def extract_real_type(self, node) -> SignalResult:
        """RealType: real type"""
        return SignalResult()
    
    @on('ShortRealType')
    def extract_short_real_type(self, node) -> SignalResult:
        """ShortRealType: shortreal type"""
        return SignalResult()
    
    @on('TypeType')
    def extract_type_type(self, node) -> SignalResult:
        """TypeType: type type"""
        return SignalResult()
    
    @on('UntypedType')
    def extract_untyped_type(self, node) -> SignalResult:
        """UntypedType: untyped type"""
        return SignalResult()
    
    @on('PropertyType')
    def extract_property_type(self, node) -> SignalResult:
        """PropertyType: property type"""
        return SignalResult()
    
    @on('SequenceType')
    def extract_sequence_type(self, node) -> SignalResult:
        """SequenceType: sequence type"""
        return SignalResult()
    
    # Statement-related
    @on('AssertPropertyStatement')
    def extract_assert_property_statement(self, node) -> SignalResult:
        """AssertPropertyStatement: assert property statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('AssumePropertyStatement')
    def extract_assume_property_statement(self, node) -> SignalResult:
        """AssumePropertyStatement: assume property statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('CoverPropertyStatement')
    def extract_cover_property_statement(self, node) -> SignalResult:
        """CoverPropertyStatement: cover property statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('CoverSequenceStatement')
    def extract_cover_sequence_statement(self, node) -> SignalResult:
        """CoverSequenceStatement: cover sequence statement"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('ExpectPropertyStatement')
    def extract_expect_property_statement(self, node) -> SignalResult:
        """ExpectPropertyStatement: expect property statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    # Sequence and property expression kinds
    @on('CasePropertyExpr')
    def extract_case_property_expr(self, node) -> SignalResult:
        """CasePropertyExpr: case property expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ClockingPropertyExpr')
    def extract_clocking_property_expr_stmt(self, node) -> SignalResult:
        """ClockingPropertyExpr: clocking property expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        clock = getattr(node, 'clock', None)
        if clock:
            result = result.merge(self.extract(clock))
        return result
    
    @on('NotPropertyExpr')
    def extract_not_property_expr(self, node) -> SignalResult:
        """NotPropertyExpr: not property expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'property', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('OrSequenceExpr')
    def extract_or_sequence_expr_stmt(self, node) -> SignalResult:
        """OrSequenceExpr: or sequence expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('AndSequenceExpr')
    def extract_and_sequence_expr_stmt(self, node) -> SignalResult:
        """AndSequenceExpr: and sequence expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SequenceMatchExpr')
    def extract_sequence_match_expr(self, node) -> SignalResult:
        """SequenceMatchExpr: sequence match expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        match = getattr(node, 'match', None) or getattr(node, 'expr2', None)
        if match:
            result = result.merge(self.extract(match))
        return result
    
    @on('BinaryPropertyExpr')
    def extract_binary_property_expr(self, node) -> SignalResult:
        """BinaryPropertyExpr: binary property expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('UnaryPropertyExpr')
    def extract_unary_property_expr_stmt(self, node) -> SignalResult:
        """UnaryPropertyExpr: unary property expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'property', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('IfPropertyExpr')
    def extract_if_property_expr_stmt(self, node) -> SignalResult:
        """IfPropertyExpr: if property expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        else_body = getattr(node, 'else_body', None) or getattr(node, 'expr2', None)
        if else_body:
            result = result.merge(self.extract(else_body))
        return result
    
    @on('CaseSequenceExpr')
    def extract_case_sequence_expr(self, node) -> SignalResult:
        """CaseSequenceExpr: case sequence expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('SequenceAbortExpr')
    def extract_sequence_abort_expr(self, node) -> SignalResult:
        """SequenceAbortExpr: sequence abort expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        abort = getattr(node, 'abort', None) or getattr(node, 'expr2', None)
        if abort:
            result = result.merge(self.extract(abort))
        return result
    
    @on('SequenceDelayExpr')
    def extract_sequence_delay_expr(self, node) -> SignalResult:
        """SequenceDelayExpr: sequence delay expression ##"""
        result = SignalResult()
        delay = getattr(node, 'delay', None) or getattr(node, 'expr', None)
        if delay:
            result = result.merge(self.extract(delay))
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr2', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    # More binary operators
    @on('ImplicationSequenceExpr')
    def extract_implication_sequence_expr(self, node) -> SignalResult:
        """ImplicationSequenceExpr: implication sequence => or ->"""
        result = SignalResult()
        left = getattr(node, 'left', None) or getattr(node, 'antecedent', None)
        right = getattr(node, 'right', None) or getattr(node, 'consequent', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('FollowedBySequenceExpr')
    def extract_followed_by_sequence_expr(self, node) -> SignalResult:
        """FollowedBySequenceExpr: followed by #=#"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('NonOverlappingFollowedBySequenceExpr')
    def extract_non_overlapping_followed_by_seq(self, node) -> SignalResult:
        """NonOverlappingFollowedBySequenceExpr: non-overlapping followed by #>#"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('OverlappingFollowedBySequenceExpr')
    def extract_overlapping_followed_by_seq(self, node) -> SignalResult:
        """OverlappingFollowedBySequenceExpr: overlapping followed by #=#"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('WithinSequenceExpr')
    def extract_within_sequence_expr(self, node) -> SignalResult:
        """WithinSequenceExpr: within sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        within = getattr(node, 'within', None) or getattr(node, 'expr2', None)
        if within:
            result = result.merge(self.extract(within))
        return result
    
    @on('ThroughoutSequenceExpr')
    def extract_throughout_sequence_expr(self, node) -> SignalResult:
        """ThroughoutSequenceExpr: throughout sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        throughout = getattr(node, 'throughout', None) or getattr(node, 'expr2', None)
        if throughout:
            result = result.merge(self.extract(throughout))
        return result
    
    @on('WithinFirstMatchSequenceExpr')
    def extract_within_first_match_seq_expr(self, node) -> SignalResult:
        """WithinFirstMatchSequenceExpr: within first_match sequence"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('ThroughoutFirstMatchSequenceExpr')
    def extract_throughout_first_match_seq_expr(self, node) -> SignalResult:
        """ThroughoutFirstMatchSequenceExpr: throughout first_match sequence"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('ClockingBlockPropertyExpr')
    def extract_clocking_block_property_expr(self, node) -> SignalResult:
        """ClockingBlockPropertyExpr: clocking block property expression"""
        return SignalResult()
    
    @on('ClockingBlockSequenceExpr')
    def extract_clocking_block_sequence_expr(self, node) -> SignalResult:
        """ClockingBlockSequenceExpr: clocking block sequence expression"""
        return SignalResult()
    
    # Array and method expressions
    @on('ArrayAndMethod')
    def extract_array_and_method(self, node) -> SignalResult:
        """ArrayAndMethod: array.and() method"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    @on('ArrayOrMethod')
    def extract_array_or_method(self, node) -> SignalResult:
        """ArrayOrMethod: array.or() method"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    @on('ArrayUniqueMethod')
    def extract_array_unique_method(self, node) -> SignalResult:
        """ArrayUniqueMethod: array.unique() method"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    @on('ArrayXorMethod')
    def extract_array_xor_method(self, node) -> SignalResult:
        """ArrayXorMethod: array.xor() method"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    @on('ArrayOrRandomizeMethodExpression')
    def extract_array_randomize_method_expr(self, node) -> SignalResult:
        """ArrayOrRandomizeMethodExpression: array.randomize() with method"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        with_expr = getattr(node, 'with', None) or getattr(node, 'expr2', None)
        if with_expr:
            result = result.merge(self.extract(with_expr))
        return result
    
    # Bins selection
    @on('BinsSelection')
    def extract_bins_selection(self, node) -> SignalResult:
        """BinsSelection: bins selection"""
        result = SignalResult()
        bins = getattr(node, 'bins', None) or getattr(node, 'expr', None)
        if bins:
            result = result.merge(self.extract(bins))
        select = getattr(node, 'select', None) or getattr(node, 'expr2', None)
        if select:
            result = result.merge(self.extract(select))
        return result
    
    @on('BinaryBinsSelectExpr')
    def extract_binary_bins_select_expr_stmt(self, node) -> SignalResult:
        """BinaryBinsSelectExpr: binary bins select expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('BinsSelectConditionExpr')
    def extract_bins_select_condition_expr(self, node) -> SignalResult:
        """BinsSelectConditionExpr: bins select condition expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        return result
    
    @on('BinSelectWithFilterExpr')
    def extract_bin_select_with_filter_expr(self, node) -> SignalResult:
        """BinSelectWithFilterExpr: bin select with filter expression"""
        result = SignalResult()
        bins = getattr(node, 'bins', None) or getattr(node, 'expr', None)
        if bins:
            result = result.merge(self.extract(bins))
        filter_expr = getattr(node, 'filter', None) or getattr(node, 'expr2', None)
        if filter_expr:
            result = result.merge(self.extract(filter_expr))
        return result
    
    # Bit select
    @on('BitSelect')
    def extract_bit_select(self, node) -> SignalResult:
        """BitSelect: bit select"""
        result = SignalResult()
        base = getattr(node, 'base', None) or getattr(node, 'expr', None)
        if base:
            result = result.merge(self.extract(base))
        index = getattr(node, 'index', None) or getattr(node, 'expr2', None)
        if index:
            result = result.merge(self.extract(index))
        return result
    
    # Range select
    @on('AscendingRangeSelect')
    def extract_ascending_range_select(self, node) -> SignalResult:
        """AscendingRangeSelect: ascending range select"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('DescendingRangeSelect')
    def extract_descending_range_select(self, node) -> SignalResult:
        """DescendingRangeSelect: descending range select"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Class expressions
    @on('CopyClassExpression')
    def extract_copy_class_expression(self, node) -> SignalResult:
        """CopyClassExpression: copy class expression"""
        result = SignalResult()
        source = getattr(node, 'source', None) or getattr(node, 'expr', None)
        if source:
            result = result.merge(self.extract(source))
        return result
    
    # Constraint expressions
    @on('ConditionalConstraint')
    def extract_conditional_constraint(self, node) -> SignalResult:
        """ConditionalConstraint: conditional constraint"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        true_body = getattr(node, 'true_body', None) or getattr(node, 'constraint', None)
        if true_body:
            result = result.merge(self.extract(true_body))
        false_body = getattr(node, 'false_body', None)
        if false_body:
            result = result.merge(self.extract(false_body))
        return result
    
    @on('ExpressionConstraint')
    def extract_expression_constraint_stmt(self, node) -> SignalResult:
        """ExpressionConstraint: expression constraint"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('DisableConstraint')
    def extract_disable_constraint_stmt(self, node) -> SignalResult:
        """DisableConstraint: disable constraint"""
        expr = getattr(node, 'expr', None) or getattr(node, 'constraint', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('DistConstraintList')
    def extract_dist_constraint_list(self, node) -> SignalResult:
        """DistConstraintList: dist constraint list"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ConstraintBlock')
    def extract_constraint_block(self, node) -> SignalResult:
        """ConstraintBlock: constraint block"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'constraints', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ConstraintDeclaration')
    def extract_constraint_declaration(self, node) -> SignalResult:
        """ConstraintDeclaration: constraint declaration"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'constraints', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ConstraintPrototype')
    def extract_constraint_prototype(self, node) -> SignalResult:
        """ConstraintPrototype: constraint prototype"""
        return SignalResult()
    
    # Class-related expressions
    @on('ClassDeclaration')
    def extract_class_declaration(self, node) -> SignalResult:
        """ClassDeclaration: class declaration"""
        return SignalResult()
    
    @on('ClassMethodDeclaration')
    def extract_class_method_declaration(self, node) -> SignalResult:
        """ClassMethodDeclaration: class method declaration"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('ClassMethodPrototype')
    def extract_class_method_prototype(self, node) -> SignalResult:
        """ClassMethodPrototype: class method prototype"""
        return SignalResult()
    
    @on('ClassPropertyDeclaration')
    def extract_class_property_declaration(self, node) -> SignalResult:
        """ClassPropertyDeclaration: class property declaration"""
        result = SignalResult()
        init = getattr(node, 'init', None) or getattr(node, 'value', None)
        if init:
            result = result.merge(self.extract(init))
        return result
    
    @on('ClassSpecifier')
    def extract_class_specifier(self, node) -> SignalResult:
        """ClassSpecifier: class specifier"""
        return SignalResult()
    
    @on('ClassName')
    def extract_class_name(self, node) -> SignalResult:
        """ClassName: class name"""
        return SignalResult()
    
    # Checker-related
    @on('CheckerDeclaration')
    def extract_checker_declaration(self, node) -> SignalResult:
        """CheckerDeclaration: checker declaration"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('CheckerInstanceStatement')
    def extract_checker_instance_statement(self, node) -> SignalResult:
        """CheckerInstanceStatement: checker instance statement"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('CheckerInstantiation')
    def extract_checker_instantiation(self, node) -> SignalResult:
        """CheckerInstantiation: checker instantiation"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('CheckerDataDeclaration')
    def extract_checker_data_declaration(self, node) -> SignalResult:
        """CheckerDataDeclaration: checker data declaration"""
        return SignalResult()
    
    # Coverage-related
    @on('CoverageBins')
    def extract_coverage_bins(self, node) -> SignalResult:
        """CoverageBins: coverage bins"""
        result = SignalResult()
        value = getattr(node, 'value', None) or getattr(node, 'expr', None)
        if value:
            result = result.merge(self.extract(value))
        return result
    
    @on('CoverageBinsArraySize')
    def extract_coverage_bins_array_size(self, node) -> SignalResult:
        """CoverageBinsArraySize: coverage bins array size"""
        result = SignalResult()
        size = getattr(node, 'size', None) or getattr(node, 'expr', None)
        if size:
            result = result.merge(self.extract(size))
        return result
    
    @on('DefaultCoverageBinInitializer')
    def extract_default_coverage_bin_initializer(self, node) -> SignalResult:
        """DefaultCoverageBinInitializer: default coverage bin initializer"""
        return SignalResult()
    
    @on('ExpressionCoverageBinInitializer')
    def extract_expression_coverage_bin_initializer(self, node) -> SignalResult:
        """ExpressionCoverageBinInitializer: expression coverage bin initializer"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    # ElabSystemTask
    @on('ElabSystemTask')
    def extract_elab_system_task(self, node) -> SignalResult:
        """ElabSystemTask: elaboration system task"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    # Bind directive
    @on('BindDirective')
    def extract_bind_directive(self, node) -> SignalResult:
        """BindDirective: bind directive"""
        result = SignalResult()
        target = getattr(node, 'target', None) or getattr(node, 'expr', None)
        if target:
            result = result.merge(self.extract(target))
        return result
    
    @on('BindTargetList')
    def extract_bind_target_list(self, node) -> SignalResult:
        """BindTargetList: bind target list"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Default function port
    @on('DefaultFunctionPort')
    def extract_default_function_port(self, node) -> SignalResult:
        """DefaultFunctionPort: default function port"""
        return SignalResult()
    
    # Case and generate constructs
    @on('CaseStatement')
    def extract_case_statement_stmt(self, node) -> SignalResult:
        """CaseStatement: case statement"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'condition', None)
        if expr:
            result = result.merge(self.extract(expr))
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('CaseGenerate')
    def extract_case_generate(self, node) -> SignalResult:
        """CaseGenerate: case generate construct"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'condition', None)
        if expr:
            result = result.merge(self.extract(expr))
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('DefaultCaseItem')
    def extract_default_case_item(self, node) -> SignalResult:
        """DefaultCaseItem: default case item"""
        result = SignalResult()
        stmts = getattr(node, 'statements', None) or getattr(node, 'body', None)
        if stmts and hasattr(stmts, '__iter__'):
            for stmt in stmts:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('DefaultPropertyCaseItem')
    def extract_default_property_case_item(self, node) -> SignalResult:
        """DefaultPropertyCaseItem: default property case item"""
        return SignalResult()
    
    # Assertion item ports
    @on('AssertionItemPort')
    def extract_assertion_item_port(self, node) -> SignalResult:
        """AssertionItemPort: assertion item port"""
        return SignalResult()
    
    @on('AssertionItemPortList')
    def extract_assertion_item_port_list(self, node) -> SignalResult:
        """AssertionItemPortList: assertion item port list"""
        return SignalResult()
    
    @on('ConcurrentAssertionMember')
    def extract_concurrent_assertion_member(self, node) -> SignalResult:
        """ConcurrentAssertionMember: concurrent assertion member"""
        return SignalResult()
    
    # Coverage constructs
    @on('CovergroupDeclaration')
    def extract_covergroup_declaration(self, node) -> SignalResult:
        """CovergroupDeclaration: covergroup declaration"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'coverpoints', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('Coverpoint')
    def extract_coverpoint(self, node) -> SignalResult:
        """Coverpoint: coverpoint"""
        result = SignalResult()
        transition = getattr(node, 'transition', None) or getattr(node, 'expr', None)
        if transition:
            result = result.merge(self.extract(transition))
        return result
    
    @on('CoverCross')
    def extract_cover_cross(self, node) -> SignalResult:
        """CoverCross: cover cross"""
        return SignalResult()
    
    @on('CoverageOption')
    def extract_coverage_option(self, node) -> SignalResult:
        """CoverageOption: coverage option"""
        return SignalResult()
    
    @on('CoverageIffClause')
    def extract_coverage_iff_clause(self, node) -> SignalResult:
        """CoverageIffClause: coverage iff clause"""
        expr = getattr(node, 'expr', None) or getattr(node, 'condition', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('BlockCoverageEvent')
    def extract_block_coverage_event(self, node) -> SignalResult:
        """BlockCoverageEvent: block coverage event"""
        return SignalResult()
    
    # Bad and invalid expressions
    @on('BadExpression')
    def extract_bad_expression(self, node) -> SignalResult:
        """BadExpression: bad expression"""
        return SignalResult()
    
    # Binary block event expression
    @on('BinaryBlockEventExpression')
    def extract_binary_block_event_expression(self, node) -> SignalResult:
        """BinaryBlockEventExpression: binary block event expression"""
        return SignalResult()
    
    @on('BinaryEventExpression')
    def extract_binary_event_expression(self, node) -> SignalResult:
        """BinaryEventExpression: binary event expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Blocking event trigger
    @on('BlockingEventTriggerStatement')
    def extract_blocking_event_trigger_statement(self, node) -> SignalResult:
        """BlockingEventTriggerStatement: blocking event trigger"""
        event = getattr(node, 'event', None) or getattr(node, 'expr', None)
        if event:
            return self.extract(event)
        return SignalResult()
    
    # Default disable declaration
    @on('DefaultDisableDeclaration')
    def extract_default_disable_declaration(self, node) -> SignalResult:
        """DefaultDisableDeclaration: default disable declaration"""
        expr = getattr(node, 'expr', None) or getattr(node, 'disable', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Conditional pattern
    @on('ConditionalPattern')
    def extract_conditional_pattern_stmt(self, node) -> SignalResult:
        """ConditionalPattern: conditional pattern"""
        result = SignalResult()
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        return result
    
    # Assignment pattern items
    @on('AssignmentPatternItem')
    def extract_assignment_pattern_item(self, node) -> SignalResult:
        """AssignmentPatternItem: assignment pattern item"""
        result = SignalResult()
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        init = getattr(node, 'init', None) or getattr(node, 'value', None)
        if init:
            result = result.merge(self.extract(init))
        return result
    
    # Anonymous program
    @on('AnonymousProgram')
    def extract_anonymous_program(self, node) -> SignalResult:
        """AnonymousProgram: anonymous program"""
        return SignalResult()
    
    # Extern interface method
    @on('ExternInterfaceMethod')
    def extract_extern_interface_method(self, node) -> SignalResult:
        """ExternInterfaceMethod: extern interface method"""
        return SignalResult()
    
    # More expression types
    @on('EmptyExpression')
    def extract_empty_expression(self, node) -> SignalResult:
        """EmptyExpression: empty expression"""
        return SignalResult()
    
    @on('InvalidExpression')
    def extract_invalid_expression(self, node) -> SignalResult:
        """InvalidExpression: invalid expression"""
        return SignalResult()
    
    @on('OpenRangeExpression')
    def extract_open_range_expression(self, node) -> SignalResult:
        """OpenRangeExpression: open range expression"""
        return SignalResult()
    
    @on('ParenthesizedExpression')
    def extract_parenthesized_expression(self, node) -> SignalResult:
        """ParenthesizedExpression: parenthesized expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Conditional directive expressions
    @on('BinaryConditionalDirectiveExpression')
    def extract_binary_conditional_directive_expr(self, node) -> SignalResult:
        """BinaryConditionalDirectiveExpression: binary conditional directive expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ConditionalDirectiveExpression')
    def extract_conditional_directive_expression(self, node) -> SignalResult:
        """ConditionalDirectiveExpression: conditional directive expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        true_expr = getattr(node, 'true_expr', None) or getattr(node, 'expr', None)
        if true_expr:
            result = result.merge(self.extract(true_expr))
        false_expr = getattr(node, 'false_expr', None) or getattr(node, 'expr2', None)
        if false_expr:
            result = result.merge(self.extract(false_expr))
        return result
    
    # Default pattern key expression
    @on('DefaultPatternKeyExpression')
    def extract_default_pattern_key_expression(self, node) -> SignalResult:
        """DefaultPatternKeyExpression: default pattern key expression"""
        return SignalResult()
    
    # Function return type
    @on('FunctionReturnType')
    def extract_function_return_type(self, node) -> SignalResult:
        """FunctionReturnType: function return type"""
        return SignalResult()
    
    # Import package declaration
    @on('ImportPackageDeclaration')
    def extract_import_package_declaration(self, node) -> SignalResult:
        """ImportPackageDeclaration: import package declaration"""
        return SignalResult()
    
    # Interface instantiation
    @on('InterfaceInstantiation')
    def extract_interface_instantiation(self, node) -> SignalResult:
        """InterfaceInstantiation: interface instantiation"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    # Modport declaration
    @on('ModportDeclaration')
    def extract_modport_declaration(self, node) -> SignalResult:
        """ModportDeclaration: modport declaration"""
        return SignalResult()
    
    @on('ModportItem')
    def extract_modport_item(self, node) -> SignalResult:
        """ModportItem: modport item"""
        result = SignalResult()
        signal = getattr(node, 'signal', None) or getattr(node, 'expr', None)
        if signal:
            result = result.merge(self.extract(signal))
        return result
    
    @on('ModportClockingItem')
    def extract_modport_clocking_item(self, node) -> SignalResult:
        """ModportClockingItem: modport clocking item"""
        return SignalResult()
    
    @on('ModportSimplePortDecl')
    def extract_modport_simple_port_decl(self, node) -> SignalResult:
        """ModportSimplePortDecl: modport simple port declaration"""
        return SignalResult()
    
    @on('ModportSubroutinePortDecl')
    def extract_modport_subroutine_port_decl(self, node) -> SignalResult:
        """ModportSubroutinePortDecl: modport subroutine port declaration"""
        return SignalResult()
    
    # Program instantiation
    @on('ProgramInstantiation')
    def extract_program_instantiation(self, node) -> SignalResult:
        """ProgramInstantiation: program instantiation"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    # Variable declaration patterns
    @on('VariablePatternBinding')
    def extract_variable_pattern_binding(self, node) -> SignalResult:
        """VariablePatternBinding: variable pattern binding"""
        result = SignalResult()
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        init = getattr(node, 'init', None) or getattr(node, 'value', None)
        if init:
            result = result.merge(self.extract(init))
        return result
    
    # Function and task declarations
    @on('FunctionDeclaration')
    def extract_function_declaration(self, node) -> SignalResult:
        """FunctionDeclaration: function declaration"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('TaskDeclaration')
    def extract_task_declaration(self, node) -> SignalResult:
        """TaskDeclaration: task declaration"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('ExternFunctionDeclaration')
    def extract_extern_function_declaration(self, node) -> SignalResult:
        """ExternFunctionDeclaration: extern function declaration"""
        return SignalResult()
    
    @on('ExternTaskDeclaration')
    def extract_extern_task_declaration(self, node) -> SignalResult:
        """ExternTaskDeclaration: extern task declaration"""
        return SignalResult()
    
    @on('FunctionPrototype')
    def extract_function_prototype(self, node) -> SignalResult:
        """FunctionPrototype: function prototype"""
        return SignalResult()
    
    @on('TaskPrototype')
    def extract_task_prototype(self, node) -> SignalResult:
        """TaskPrototype: task prototype"""
        return SignalResult()
    
    # Package and module declarations
    @on('PackageDeclaration')
    def extract_package_declaration(self, node) -> SignalResult:
        """PackageDeclaration: package declaration"""
        return SignalResult()
    
    @on('ModuleDeclaration')
    def extract_module_declaration(self, node) -> SignalResult:
        """ModuleDeclaration: module declaration"""
        return SignalResult()
    
    @on('InterfaceDeclaration')
    def extract_interface_declaration(self, node) -> SignalResult:
        """InterfaceDeclaration: interface declaration"""
        return SignalResult()
    
    @on('ProgramDeclaration')
    def extract_program_declaration_stmt(self, node) -> SignalResult:
        """ProgramDeclaration: program declaration"""
        return SignalResult()
    
    # Generate constructs
    @on('ForGenerate')
    def extract_for_generate(self, node) -> SignalResult:
        """ForGenerate: for generate construct"""
        result = SignalResult()
        init = getattr(node, 'init', None)
        if init:
            result = result.merge(self.extract(init))
        cond = getattr(node, 'cond', None) or getattr(node, 'condition', None)
        if cond:
            result = result.merge(self.extract(cond))
        step = getattr(node, 'step', None)
        if step:
            result = result.merge(self.extract(step))
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('IfGenerate')
    def extract_if_generate(self, node) -> SignalResult:
        """IfGenerate: if generate construct"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        true_body = getattr(node, 'true_body', None) or getattr(node, 'body', None)
        if true_body:
            result = result.merge(self.extract(true_body))
        false_body = getattr(node, 'false_body', None) or getattr(node, 'else_body', None)
        if false_body:
            result = result.merge(self.extract(false_body))
        return result
    
    @on('LoopGenerate')
    def extract_loop_generate(self, node) -> SignalResult:
        """LoopGenerate: loop generate construct"""
        result = SignalResult()
        init = getattr(node, 'init', None)
        if init:
            result = result.merge(self.extract(init))
        cond = getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        step = getattr(node, 'step', None)
        if step:
            result = result.merge(self.extract(step))
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('GenerateBlock')
    def extract_generate_block(self, node) -> SignalResult:
        """GenerateBlock: generate block"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('GenerateRegion')
    def extract_generate_region(self, node) -> SignalResult:
        """GenerateRegion: generate region"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'statements', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Continuous assignment
    @on('ContinuousAssign')
    def extract_continuous_assign(self, node) -> SignalResult:
        """ContinuousAssign: continuous assignment"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, 'rvalue', None) or getattr(node, 'expr', None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result
    
    @on('AliasStatement')
    def extract_alias_statement(self, node) -> SignalResult:
        """AliasStatement: alias statement"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Port declarations
    @on('PortDeclaration')
    def extract_port_declaration(self, node) -> SignalResult:
        """PortDeclaration: port declaration"""
        result = SignalResult()
        init = getattr(node, 'init', None) or getattr(node, 'value', None)
        if init:
            result = result.merge(self.extract(init))
        return result
    
    @on('InvalidPort')
    def extract_invalid_port(self, node) -> SignalResult:
        """InvalidPort: invalid port"""
        return SignalResult()
    
    @on('TypedPortDeclaration')
    def extract_typed_port_declaration(self, node) -> SignalResult:
        """TypedPortDeclaration: typed port declaration"""
        return SignalResult()
    
    @on('TypedVariableDeclaration')
    def extract_typed_variable_declaration(self, node) -> SignalResult:
        """TypedVariableDeclaration: typed variable declaration"""
        return SignalResult()
    
    # Loop statements
    @on('ForLoopStatement')
    def extract_for_loop_statement(self, node) -> SignalResult:
        """ForLoopStatement: for loop statement"""
        result = SignalResult()
        init = getattr(node, 'init', None)
        if init:
            result = result.merge(self.extract(init))
        cond = getattr(node, 'cond', None) or getattr(node, 'condition', None)
        if cond:
            result = result.merge(self.extract(cond))
        step = getattr(node, 'step', None)
        if step:
            result = result.merge(self.extract(step))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('ForeachLoopStatement')
    def extract_foreach_loop_statement(self, node) -> SignalResult:
        """ForeachLoopStatement: foreach loop statement"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('WhileLoopStatement')
    def extract_while_loop_statement(self, node) -> SignalResult:
        """WhileLoopStatement: while loop statement"""
        result = SignalResult()
        cond = getattr(node, 'cond', None) or getattr(node, 'condition', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('DoWhileLoopStatement')
    def extract_do_while_loop_statement(self, node) -> SignalResult:
        """DoWhileLoopStatement: do while loop statement"""
        result = SignalResult()
        cond = getattr(node, 'cond', None) or getattr(node, 'condition', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('ForeverLoopStatement')
    def extract_forever_loop_statement_stmt(self, node) -> SignalResult:
        """ForeverLoopStatement: forever loop statement"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    # Repeat loop
    @on('RepeatLoopStatement')
    def extract_repeat_loop_statement_stmt(self, node) -> SignalResult:
        """RepeatLoopStatement: repeat loop statement"""
        result = SignalResult()
        cond = getattr(node, 'cond', None) or getattr(node, 'expression', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    # Jump statements
    @on('ReturnStatement')
    def extract_return_statement(self, node) -> SignalResult:
        """ReturnStatement: return statement"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('BreakStatement')
    def extract_break_statement(self, node) -> SignalResult:
        """BreakStatement: break statement"""
        return SignalResult()
    
    @on('ContinueStatement')
    def extract_continue_statement(self, node) -> SignalResult:
        """ContinueStatement: continue statement"""
        return SignalResult()
    
    @on('DisableStatement')
    def extract_disable_statement(self, node) -> SignalResult:
        """DisableStatement: disable statement"""
        return SignalResult()
    
    # Wait statements
    @on('WaitStatement')
    def extract_wait_statement_stmt(self, node) -> SignalResult:
        """WaitStatement: wait statement"""
        cond = getattr(node, 'cond', None) or getattr(node, 'expression', None)
        if cond:
            return self.extract(cond)
        return SignalResult()
    
    @on('WaitOrderStatement')
    def extract_wait_order_statement_stmt(self, node) -> SignalResult:
        """WaitOrderStatement: wait order statement"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Fork/join statements
    @on('ForkStatement')
    def extract_fork_statement(self, node) -> SignalResult:
        """ForkStatement: fork statement"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('JoinStatement')
    def extract_join_statement(self, node) -> SignalResult:
        """JoinStatement: join statement"""
        return SignalResult()
    
    @on('JoinAnyStatement')
    def extract_join_any_statement_stmt(self, node) -> SignalResult:
        """JoinAnyStatement: join any statement"""
        return SignalResult()
    
    @on('JoinNoneStatement')
    def extract_join_none_statement_stmt(self, node) -> SignalResult:
        """JoinNoneStatement: join none statement"""
        return SignalResult()
    
    # Force/release statements
    @on('ForceStatement')
    def extract_force_statement(self, node) -> SignalResult:
        """ForceStatement: force statement"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, 'rvalue', None) or getattr(node, 'expr', None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result
    
    @on('ReleaseStatement')
    def extract_release_statement(self, node) -> SignalResult:
        """ReleaseStatement: release statement"""
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()
    
    # Procedural timing control
    @on('ProceduralTimingControlStatement')
    def extract_procedural_timing_control_stmt(self, node) -> SignalResult:
        """ProceduralTimingControlStatement: procedural timing control statement"""
        result = SignalResult()
        timing = getattr(node, 'timing', None) or getattr(node, 'control', None)
        if timing:
            result = result.merge(self.extract(timing))
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if stmt:
            result = result.merge(self.extract(stmt))
        return result
    
    # Delay control
    @on('DelayControlStatement')
    def extract_delay_control_statement(self, node) -> SignalResult:
        """DelayControlStatement: delay control statement"""
        result = SignalResult()
        delay = getattr(node, 'delay', None) or getattr(node, 'expr', None)
        if delay:
            result = result.merge(self.extract(delay))
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if stmt:
            result = result.merge(self.extract(stmt))
        return result
    
    # Event control
    @on('EventControlStatement')
    def extract_event_control_statement(self, node) -> SignalResult:
        """EventControlStatement: event control statement"""
        result = SignalResult()
        event = getattr(node, 'event', None) or getattr(node, 'expr', None)
        if event:
            result = result.merge(self.extract(event))
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if stmt:
            result = result.merge(self.extract(stmt))
        return result
    
    # Cycle delay control
    @on('CycleDelayControlStatement')
    def extract_cycle_delay_control_statement(self, node) -> SignalResult:
        """CycleDelayControlStatement: cycle delay control statement"""
        result = SignalResult()
        count = getattr(node, 'count', None) or getattr(node, 'expr', None)
        if count:
            result = result.merge(self.extract(count))
        stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
        if stmt:
            result = result.merge(self.extract(stmt))
        return result
    
    # Empty statement
    @on('EmptyStatement')
    def extract_empty_statement_stmt(self, node) -> SignalResult:
        """EmptyStatement: empty statement"""
        return SignalResult()
    
    # Expression statement
    @on('ExpressionStatement')
    def extract_expression_statement_stmt(self, node) -> SignalResult:
        """ExpressionStatement: expression statement"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Variable declaration statement
    @on('VariableDeclarationStatement')
    def extract_variable_declaration_statement(self, node) -> SignalResult:
        """VariableDeclarationStatement: variable declaration statement"""
        result = SignalResult()
        init = getattr(node, 'init', None) or getattr(node, 'value', None)
        if init:
            result = result.merge(self.extract(init))
        return result
    
    # Local parameter declaration
    @on('LocalParameterDeclaration')
    def extract_local_parameter_declaration(self, node) -> SignalResult:
        """LocalParameterDeclaration: local parameter declaration"""
        return SignalResult()
    
    @on('ParameterDeclaration')
    def extract_parameter_declaration(self, node) -> SignalResult:
        """ParameterDeclaration: parameter declaration"""
        return SignalResult()
    
    # Non-blocking assignment statement
    @on('NonBlockingAssignmentStatement')
    def extract_non_blocking_assignment_stmt(self, node) -> SignalResult:
        """NonBlockingAssignmentStatement: non-blocking assignment statement"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, 'rvalue', None) or getattr(node, 'expr', None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result
    
    @on('BlockingAssignmentStatement')
    def extract_blocking_assignment_stmt_stmt(self, node) -> SignalResult:
        """BlockingAssignmentStatement: blocking assignment statement"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, 'rvalue', None) or getattr(node, 'expr', None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result
    
    # Procedural assign/deassign
    @on('ProceduralAssignStatement')
    def extract_procedural_assign_statement_stmt(self, node) -> SignalResult:
        """ProceduralAssignStatement: procedural assign statement"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, 'rvalue', None) or getattr(node, 'expr', None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result
    
    @on('ProceduralDeassignStatement')
    def extract_procedural_deassign_statement_stmt(self, node) -> SignalResult:
        """ProceduralDeassignStatement: procedural deassign statement"""
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()
    
    # Rand statement
    @on('RandCaseStatement')
    def extract_rand_case_statement_stmt(self, node) -> SignalResult:
        """RandCaseStatement: rand case statement"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('RandCaseItem')
    def extract_rand_case_item_stmt(self, node) -> SignalResult:
        """RandCaseItem: rand case item"""
        result = SignalResult()
        weight = getattr(node, 'weight', None) or getattr(node, 'condition', None)
        if weight:
            result = result.merge(self.extract(weight))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('RandSequenceStatement')
    def extract_rand_sequence_statement(self, node) -> SignalResult:
        """RandSequenceStatement: rand sequence statement"""
        return SignalResult()
    
    # Immediate assertion statements
    @on('ImmediateAssertStatement')
    def extract_immediate_assert_statement(self, node) -> SignalResult:
        """ImmediateAssertStatement: immediate assert statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('ImmediateAssumeStatement')
    def extract_immediate_assume_statement(self, node) -> SignalResult:
        """ImmediateAssumeStatement: immediate assume statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('ImmediateCoverStatement')
    def extract_immediate_cover_statement(self, node) -> SignalResult:
        """ImmediateCoverStatement: immediate cover statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    # Deferred assertion statements
    @on('FinalDeferredAssertStatement')
    def extract_final_deferred_assert_statement(self, node) -> SignalResult:
        """FinalDeferredAssertStatement: final deferred assert statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('SimpleDeferredAssertStatement')
    def extract_simple_deferred_assert_statement(self, node) -> SignalResult:
        """SimpleDeferredAssertStatement: simple deferred assert statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    # Concurrent assertion statements
    @on('ConcurrentAssertStatement')
    def extract_concurrent_assert_statement(self, node) -> SignalResult:
        """ConcurrentAssertStatement: concurrent assert statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('AssertStatement')
    def extract_assert_statement_stmt(self, node) -> SignalResult:
        """AssertStatement: assert statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    @on('AssumeStatement')
    def extract_assume_statement_stmt(self, node) -> SignalResult:
        """AssumeStatement: assume statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('CoverStatement')
    def extract_cover_statement_stmt(self, node) -> SignalResult:
        """CoverStatement: cover statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    # Expect property statement
    @on('ExpectPropertyStatement')
    def extract_expect_property_statement_stmt(self, node) -> SignalResult:
        """ExpectPropertyStatement: expect property statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    # Checker instantiation statement
    @on('CheckerInstantiationStatement')
    def extract_checker_instantiation_statement(self, node) -> SignalResult:
        """CheckerInstantiationStatement: checker instantiation statement"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    # Final statement
    @on('FinalStatement')
    def extract_final_statement(self, node) -> SignalResult:
        """FinalStatement: final statement"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    # Initial statement
    @on('InitialStatement')
    def extract_initial_statement(self, node) -> SignalResult:
        """InitialStatement: initial statement"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    # Sequence/Property expressions
    @on('SequenceAbbrevMaybeExpr')
    def extract_sequence_abbrev_maybe_expr(self, node) -> SignalResult:
        """SequenceAbbrevMaybeExpr: sequence abbreviation maybe ##?"""
        expr = getattr(node, 'expr', None) or getattr(node, 'sequence', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('SequenceAbbrevPlusExpr')
    def extract_sequence_abbrev_plus_expr(self, node) -> SignalResult:
        """SequenceAbbrevPlusExpr: sequence abbreviation plus ##+"""
        expr = getattr(node, 'expr', None) or getattr(node, 'sequence', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('SequenceAbbrevStarExpr')
    def extract_sequence_abbrev_star_expr(self, node) -> SignalResult:
        """SequenceAbbrevStarExpr: sequence abbreviation star ##*"""
        expr = getattr(node, 'expr', None) or getattr(node, 'sequence', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('SequenceConcatExpr')
    def extract_sequence_concat_expr(self, node) -> SignalResult:
        """SequenceConcatExpr: sequence concatenation expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SequenceIntersectExpr')
    def extract_sequence_intersect_expr(self, node) -> SignalResult:
        """SequenceIntersectExpr: sequence intersect expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SequenceOrExpr')
    def extract_sequence_or_expr_stmt(self, node) -> SignalResult:
        """SequenceOrExpr: sequence or expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SequenceAndExpr')
    def extract_sequence_and_expr_stmt(self, node) -> SignalResult:
        """SequenceAndExpr: sequence and expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SequenceFirstMatchExpr')
    def extract_sequence_first_match_expr_stmt(self, node) -> SignalResult:
        """SequenceFirstMatchExpr: sequence first_match expression"""
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            return self.extract(seq)
        return SignalResult()
    
    @on('SequenceClockingExpr')
    def extract_sequence_clocking_expr_stmt(self, node) -> SignalResult:
        """SequenceClockingExpr: sequence clocking expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        clock = getattr(node, 'clock', None)
        if clock:
            result = result.merge(self.extract(clock))
        return result
    
    @on('SequenceNotExpr')
    def extract_sequence_not_expr(self, node) -> SignalResult:
        """SequenceNotExpr: sequence not expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'sequence', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PropertyNotExpr')
    def extract_property_not_expr_stmt(self, node) -> SignalResult:
        """PropertyNotExpr: property not expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'property', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PropertyOrExpr')
    def extract_property_or_expr_stmt(self, node) -> SignalResult:
        """PropertyOrExpr: property or expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('PropertyAndExpr')
    def extract_property_and_expr_stmt(self, node) -> SignalResult:
        """PropertyAndExpr: property and expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('PropertyImplicationExpr')
    def extract_property_implication_expr(self, node) -> SignalResult:
        """PropertyImplicationExpr: property implication expression"""
        result = SignalResult()
        left = getattr(node, 'left', None) or getattr(node, 'antecedent', None)
        right = getattr(node, 'right', None) or getattr(node, 'consequent', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('PropertyIfExpr')
    def extract_property_if_expr(self, node) -> SignalResult:
        """PropertyIfExpr: property if expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        else_body = getattr(node, 'else_body', None) or getattr(node, 'expr2', None)
        if else_body:
            result = result.merge(self.extract(else_body))
        return result
    
    # Clocking block expressions
    @on('ClockingBlockEventExpr')
    def extract_clocking_block_event_expr(self, node) -> SignalResult:
        """ClockingBlockEventExpr: clocking block event expression"""
        return SignalResult()
    
    @on('ClockingBlockPropertyExpr')
    def extract_clocking_block_property_expr_stmt(self, node) -> SignalResult:
        """ClockingBlockPropertyExpr: clocking block property expression"""
        return SignalResult()
    
    @on('ClockingBlockSequenceExpr')
    def extract_clocking_block_sequence_expr_stmt(self, node) -> SignalResult:
        """ClockingBlockSequenceExpr: clocking block sequence expression"""
        return SignalResult()
    
    # Data type expressions
    @on('BitVectorExpr')
    def extract_bit_vector_expr(self, node) -> SignalResult:
        """BitVectorExpr: bit vector expression"""
        return SignalResult()
    
    @on('StringLiteralExpr')
    def extract_string_literal_expr(self, node) -> SignalResult:
        """StringLiteralExpr: string literal expression"""
        return SignalResult()
    
    @on('TimeLiteralExpr')
    def extract_time_literal_expr(self, node) -> SignalResult:
        """TimeLiteralExpr: time literal expression"""
        return SignalResult()
    
    @on('RealLiteralExpr')
    def extract_real_literal_expr(self, node) -> SignalResult:
        """RealLiteralExpr: real literal expression"""
        return SignalResult()
    
    @on('IntegerLiteralExpr')
    def extract_integer_literal_expr(self, node) -> SignalResult:
        """IntegerLiteralExpr: integer literal expression"""
        return SignalResult()
    
    @on('UnbasedUnsizedLiteralExpr')
    def extract_unbased_unsized_literal_expr(self, node) -> SignalResult:
        """UnbasedUnsizedLiteralExpr: unbased unsized literal expression"""
        return SignalResult()
    
    # Method call expressions
    @on('MethodCallExpression')
    def extract_method_call_expression_stmt(self, node) -> SignalResult:
        """MethodCallExpression: method call expression"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('SystemMethodCallExpression')
    def extract_system_method_call_expression(self, node) -> SignalResult:
        """SystemMethodCallExpression: system method call expression"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    # New expressions
    @on('NewClassExpression')
    def extract_new_class_expression_stmt(self, node) -> SignalResult:
        """NewClassExpression: new class expression"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('NewArrayExpression')
    def extract_new_array_expression_stmt(self, node) -> SignalResult:
        """NewArrayExpression: new array expression"""
        result = SignalResult()
        size = getattr(node, 'size', None) or getattr(node, 'expr', None)
        if size:
            result = result.merge(self.extract(size))
        return result
    
    @on('NewCovergroupExpression')
    def extract_new_covergroup_expression_stmt(self, node) -> SignalResult:
        """NewCovergroupExpression: new covergroup expression"""
        return SignalResult()
    
    # Pattern expressions
    @on('WildcardPatternExpr')
    def extract_wildcard_pattern_expr(self, node) -> SignalResult:
        """WildcardPatternExpr: wildcard pattern expression"""
        return SignalResult()
    
    @on('ConstantPatternExpr')
    def extract_constant_pattern_expr(self, node) -> SignalResult:
        """ConstantPatternExpr: constant pattern expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'value', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('VariablePatternExpr')
    def extract_variable_pattern_expr(self, node) -> SignalResult:
        """VariablePatternExpr: variable pattern expression"""
        var = getattr(node, 'var', None) or getattr(node, 'expr', None)
        if var:
            return self.extract(var)
        return SignalResult()
    
    @on('TaggedPatternExpr')
    def extract_tagged_pattern_expr(self, node) -> SignalResult:
        """TaggedPatternExpr: tagged pattern expression"""
        result = SignalResult()
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        return result
    
    @on('StructurePatternExpr')
    def extract_structure_pattern_expr(self, node) -> SignalResult:
        """StructurePatternExpr: structure pattern expression"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'patterns', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ReplicatedPatternExpr')
    def extract_replicated_pattern_expr(self, node) -> SignalResult:
        """ReplicatedPatternExpr: replicated pattern expression"""
        result = SignalResult()
        count = getattr(node, 'count', None) or getattr(node, 'expr', None)
        if count:
            result = result.merge(self.extract(count))
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        return result
    
    # Constraint block expressions
    @on('ConstraintListExpr')
    def extract_constraint_list_expr(self, node) -> SignalResult:
        """ConstraintListExpr: constraint list expression"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Dist constraint
    @on('DistConstraintExpr')
    def extract_dist_constraint_expr(self, node) -> SignalResult:
        """DistConstraintExpr: dist constraint expression"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('DistWeight')
    def extract_dist_weight(self, node) -> SignalResult:
        """DistWeight: dist weight"""
        result = SignalResult()
        weight = getattr(node, 'weight', None) or getattr(node, 'expr', None)
        if weight:
            result = result.merge(self.extract(weight))
        value = getattr(node, 'value', None) or getattr(node, 'expr2', None)
        if value:
            result = result.merge(self.extract(value))
        return result
    
    # Let expression
    @on('LetExpression')
    def extract_let_expression_stmt(self, node) -> SignalResult:
        """LetExpression: let expression"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        body = getattr(node, 'body', None) or getattr(node, 'expr', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    # Randomize with expression
    @on('RandomizeWithExpression')
    def extract_randomize_with_expression(self, node) -> SignalResult:
        """RandomizeWithExpression: randomize with expression"""
        result = SignalResult()
        with_expr = getattr(node, 'with', None) or getattr(node, 'expr', None)
        if with_expr:
            result = result.merge(self.extract(with_expr))
        return result
    
    # Wait fork expression
    @on('WaitForkExpression')
    def extract_wait_fork_expression(self, node) -> SignalResult:
        """WaitForkExpression: wait fork expression"""
        return SignalResult()
    
    # Method expressions
    @on('ArrayAndMethodExpr')
    def extract_array_and_method_expr(self, node) -> SignalResult:
        """ArrayAndMethodExpr: array.and() method expression"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    @on('ArrayOrMethodExpr')
    def extract_array_or_method_expr(self, node) -> SignalResult:
        """ArrayOrMethodExpr: array.or() method expression"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    @on('ArrayUniqueMethodExpr')
    def extract_array_unique_method_expr(self, node) -> SignalResult:
        """ArrayUniqueMethodExpr: array.unique() method expression"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    @on('ArrayXorMethodExpr')
    def extract_array_xor_method_expr(self, node) -> SignalResult:
        """ArrayXorMethodExpr: array.xor() method expression"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    # Delay control expressions
    @on('DelayControlExpr')
    def extract_delay_control_expr(self, node) -> SignalResult:
        """DelayControlExpr: delay control expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'delay', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('EventControlExpr')
    def extract_event_control_expr(self, node) -> SignalResult:
        """EventControlExpr: event control expression"""
        event = getattr(node, 'event', None) or getattr(node, 'expr', None)
        if event:
            return self.extract(event)
        return SignalResult()
    
    @on('CycleDelayExpr')
    def extract_cycle_delay_expr(self, node) -> SignalResult:
        """CycleDelayExpr: cycle delay expression ##"""
        result = SignalResult()
        count = getattr(node, 'count', None) or getattr(node, 'expr', None)
        if count:
            result = result.merge(self.extract(count))
        return result
    
    # Queue expressions
    @on('QueueExpression')
    def extract_queue_expression(self, node) -> SignalResult:
        """QueueExpression: queue expression"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'expressions', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Associative array expressions
    @on('AssociativeArrayExpression')
    def extract_associative_array_expression(self, node) -> SignalResult:
        """AssociativeArrayExpression: associative array expression"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Streaming expressions
    @on('StreamingConcatenationExpr')
    def extract_streaming_concatenation_expr(self, node) -> SignalResult:
        """StreamingConcatenationExpr: streaming concatenation expression"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'streams', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('StreamExpression')
    def extract_stream_expression_stmt(self, node) -> SignalResult:
        """StreamExpression: stream expression"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'expr', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Concatenation expressions
    @on('ConcatenationExpr')
    def extract_concatenation_expr(self, node) -> SignalResult:
        """ConcatenationExpr: concatenation expression"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'expressions', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ReplicationExpr')
    def extract_replication_expr(self, node) -> SignalResult:
        """ReplicationExpr: replication expression {N{expr}}"""
        result = SignalResult()
        count = getattr(node, 'count', None) or getattr(node, 'expr', None)
        if count:
            result = result.merge(self.extract(count))
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    # MinTypMax expression
    @on('MinTypMaxExpr')
    def extract_min_typ_max_expr_stmt(self, node) -> SignalResult:
        """MinTypMaxExpr: min typ max expression"""
        result = SignalResult()
        min = getattr(node, 'min', None) or getattr(node, 'expr', None)
        if min:
            result = result.merge(self.extract(min))
        typ = getattr(node, 'typ', None) or getattr(node, 'expr2', None)
        if typ:
            result = result.merge(self.extract(typ))
        max = getattr(node, 'max', None) or getattr(node, 'expr3', None)
        if max:
            result = result.merge(self.extract(max))
        return result
    
    # Inside expression
    @on('InsideExpr')
    def extract_inside_expr(self, node) -> SignalResult:
        """InsideExpr: inside expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        range_expr = getattr(node, 'range', None) or getattr(node, 'expr2', None)
        if range_expr:
            result = result.merge(self.extract(range_expr))
        return result
    
    # Matched expressions
    @on('MatchedExpr')
    def extract_matched_expr(self, node) -> SignalResult:
        """MatchedExpr: matched expression"""
        result = SignalResult()
        match = getattr(node, 'match', None) or getattr(node, 'expr', None)
        if match:
            result = result.merge(self.extract(match))
        return result
    
    # Unary operators
    @on('UnaryPlusExpr')
    def extract_unary_plus_expr(self, node) -> SignalResult:
        """UnaryPlusExpr: unary plus expression +"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryMinusExpr')
    def extract_unary_minus_expr(self, node) -> SignalResult:
        """UnaryMinusExpr: unary minus expression -"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryNotExpr')
    def extract_unary_not_expr(self, node) -> SignalResult:
        """UnaryNotExpr: unary not expression !"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryTildeExpr')
    def extract_unary_tilde_expr(self, node) -> SignalResult:
        """UnaryTildeExpr: unary tilde expression ~"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # More unary operators
    @on('UnaryAndExpr')
    def extract_unary_and_expr(self, node) -> SignalResult:
        """UnaryAndExpr: unary and expression &"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryOrExpr')
    def extract_unary_or_expr(self, node) -> SignalResult:
        """UnaryOrExpr: unary or expression |"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryXorExpr')
    def extract_unary_xor_expr(self, node) -> SignalResult:
        """UnaryXorExpr: unary xor expression ^"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryNandExpr')
    def extract_unary_nand_expr(self, node) -> SignalResult:
        """UnaryNandExpr: unary nand expression ~&"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryNorExpr')
    def extract_unary_nor_expr(self, node) -> SignalResult:
        """UnaryNorExpr: unary nor expression ~|"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryXnorExpr')
    def extract_unary_xnor_expr(self, node) -> SignalResult:
        """UnaryXnorExpr: unary xnor expression ^~"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Increment/Decrement expressions
    @on('PreIncrementExpr')
    def extract_pre_increment_expr(self, node) -> SignalResult:
        """PreIncrementExpr: pre increment expression ++expr"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PreDecrementExpr')
    def extract_pre_decrement_expr(self, node) -> SignalResult:
        """PreDecrementExpr: pre decrement expression --expr"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PostIncrementExpr')
    def extract_post_increment_expr_stmt(self, node) -> SignalResult:
        """PostIncrementExpr: post increment expression expr++"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PostDecrementExpr')
    def extract_post_decrement_expr_stmt(self, node) -> SignalResult:
        """PostDecrementExpr: post decrement expression expr--"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Comparison operators
    @on('LessThanExpr')
    def extract_less_than_expr_stmt(self, node) -> SignalResult:
        """LessThanExpr: less than expression <"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('GreaterThanExpr')
    def extract_greater_than_expr_stmt(self, node) -> SignalResult:
        """GreaterThanExpr: greater than expression >"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LessThanOrEqualExpr')
    def extract_less_than_or_equal_expr_stmt(self, node) -> SignalResult:
        """LessThanOrEqualExpr: less than or equal expression <="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('GreaterThanOrEqualExpr')
    def extract_greater_than_or_equal_expr_stmt(self, node) -> SignalResult:
        """GreaterThanOrEqualExpr: greater than or equal expression >="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Binary logical operators
    @on('LogicalAndExpr')
    def extract_logical_and_expr(self, node) -> SignalResult:
        """LogicalAndExpr: logical and expression &&"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LogicalOrExpr')
    def extract_logical_or_expr(self, node) -> SignalResult:
        """LogicalOrExpr: logical or expression ||"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LogicalXorExpr')
    def extract_logical_xor_expr(self, node) -> SignalResult:
        """LogicalXorExpr: logical xor expression ^"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LogicalXnorExpr')
    def extract_logical_xnor_expr(self, node) -> SignalResult:
        """LogicalXnorExpr: logical xnor expression ^~"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Shift operators
    @on('LeftShiftExpr')
    def extract_left_shift_expr(self, node) -> SignalResult:
        """LeftShiftExpr: left shift expression <<"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('RightShiftExpr')
    def extract_right_shift_expr(self, node) -> SignalResult:
        """RightShiftExpr: right shift expression >>"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ArithmeticLeftShiftExpr')
    def extract_arithmetic_left_shift_expr(self, node) -> SignalResult:
        """ArithmeticLeftShiftExpr: arithmetic left shift <<<"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ArithmeticRightShiftExpr')
    def extract_arithmetic_right_shift_expr(self, node) -> SignalResult:
        """ArithmeticRightShiftExpr: arithmetic right shift >>>"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Power expression
    @on('PowerExpr')
    def extract_power_expr(self, node) -> SignalResult:
        """PowerExpr: power expression **"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Modulo expression
    @on('ModuloExpr')
    def extract_modulo_expr(self, node) -> SignalResult:
        """ModuloExpr: modulo expression %"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Multicast/Replication expressions
    @on('MulticastExpression')
    def extract_multicast_expression(self, node) -> SignalResult:
        """MulticastExpression: multicast expression"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None) or getattr(node, 'expr', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        return result
    
    @on('StreamingReplicationExpr')
    def extract_streaming_replication_expr(self, node) -> SignalResult:
        """StreamingReplicationExpr: streaming replication expression"""
        result = SignalResult()
        count = getattr(node, 'count', None) or getattr(node, 'expr', None)
        if count:
            result = result.merge(self.extract(count))
        return result
    
    # Clocking block expressions
    @on('ClockingBlockExpr')
    def extract_clocking_block_expr(self, node) -> SignalResult:
        """ClockingBlockExpr: clocking block expression"""
        return SignalResult()
    
    @on('ClockingBlockEventExpr')
    def extract_clocking_block_event_expr_stmt(self, node) -> SignalResult:
        """ClockingBlockEventExpr: clocking block event expression"""
        return SignalResult()
    
    # Import/Export expressions
    @on('ImportExportExpr')
    def extract_import_export_expr(self, node) -> SignalResult:
        """ImportExportExpr: import export expression"""
        return SignalResult()
    
    # Typedef expressions
    @on('TypedefExpression')
    def extract_typedef_expression(self, node) -> SignalResult:
        """TypedefExpression: typedef expression"""
        return SignalResult()
    
    # Null/Unknown expressions
    @on('NullExpression')
    def extract_null_expression(self, node) -> SignalResult:
        """NullExpression: null expression"""
        return SignalResult()
    
    @on('UnboundedExpression')
    def extract_unbounded_expression(self, node) -> SignalResult:
        """UnboundedExpression: unbounded expression $"""
        return SignalResult()
    
    # This expression
    @on('ThisExpression')
    def extract_this_expression(self, node) -> SignalResult:
        """ThisExpression: this expression"""
        return SignalResult()
    
    # Super expression
    @on('SuperExpression')
    def extract_super_expression(self, node) -> SignalResult:
        """SuperExpression: super expression"""
        return SignalResult()
    
    # Wildcard expression
    @on('WildcardExpression')
    def extract_wildcard_expression(self, node) -> SignalResult:
        """WildcardExpression: wildcard expression"""
        return SignalResult()
    
    # Assignment operators
    @on('AssignmentOperatorExpr')
    def extract_assignment_operator_expr(self, node) -> SignalResult:
        """AssignmentOperatorExpr: assignment operator expression"""
        return SignalResult()
    
    # Binary operators
    @on('BinaryAndExpr')
    def extract_binary_and_expr(self, node) -> SignalResult:
        """BinaryAndExpr: binary and expression &"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('BinaryOrExpr')
    def extract_binary_or_expr(self, node) -> SignalResult:
        """BinaryOrExpr: binary or expression |"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('BinaryXorExpr')
    def extract_binary_xor_expr(self, node) -> SignalResult:
        """BinaryXorExpr: binary xor expression ^"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('BinaryNandExpr')
    def extract_binary_nand_expr(self, node) -> SignalResult:
        """BinaryNandExpr: binary nand expression ~&"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('BinaryNorExpr')
    def extract_binary_nor_expr(self, node) -> SignalResult:
        """BinaryNorExpr: binary nor expression ~|"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('BinaryXnorExpr')
    def extract_binary_xnor_expr_stmt(self, node) -> SignalResult:
        """BinaryXnorExpr: binary xnor expression ^~"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Arithmetic operators
    @on('AddExpr')
    def extract_add_expr_stmt(self, node) -> SignalResult:
        """AddExpr: add expression +"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SubtractExpr')
    def extract_subtract_expr_stmt(self, node) -> SignalResult:
        """SubtractExpr: subtract expression -"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('MultiplyExpr')
    def extract_multiply_expr_stmt(self, node) -> SignalResult:
        """MultiplyExpr: multiply expression *"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('DivideExpr')
    def extract_divide_expr_stmt(self, node) -> SignalResult:
        """DivideExpr: divide expression /"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ModExpression')
    def extract_mod_expression_stmt(self, node) -> SignalResult:
        """ModExpression: mod expression %"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('EqualityExpr')
    def extract_equality_expr(self, node) -> SignalResult:
        """EqualityExpr: equality expression =="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('InequalityExpr')
    def extract_inequality_expr(self, node) -> SignalResult:
        """InequalityExpr: inequality expression !="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Case equality operators
    @on('CaseEqualityExpr')
    def extract_case_equality_expr(self, node) -> SignalResult:
        """CaseEqualityExpr: case equality expression ==="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('CaseInequalityExpr')
    def extract_case_inequality_expr(self, node) -> SignalResult:
        """CaseInequalityExpr: case inequality expression !=="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Ternary/Conditional expression
    @on('ConditionalExpr')
    def extract_conditional_expr(self, node) -> SignalResult:
        """ConditionalExpr: conditional expression cond ? expr1 : expr2"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        left = getattr(node, 'left', None) or getattr(node, 'true', None)
        if left:
            result = result.merge(self.extract(left))
        right = getattr(node, 'right', None) or getattr(node, 'false', None)
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Cast expressions
    @on('CastExpr')
    def extract_cast_expr_stmt(self, node) -> SignalResult:
        """CastExpr: cast expression"""
        result = SignalResult()
        cast = getattr(node, 'cast', None) or getattr(node, 'type', None)
        if cast:
            result = result.merge(self.extract(cast))
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ConstantCastExpr')
    def extract_constant_cast_expr(self, node) -> SignalResult:
        """ConstantCastExpr: constant cast expression"""
        result = SignalResult()
        cast = getattr(node, 'cast', None) or getattr(node, 'type', None)
        if cast:
            result = result.merge(self.extract(cast))
        expr = getattr(node, 'expr', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('DynamicArrayCastExpr')
    def extract_dynamic_array_cast_expr(self, node) -> SignalResult:
        """DynamicArrayCastExpr: dynamic array cast expression"""
        result = SignalResult()
        cast = getattr(node, 'cast', None) or getattr(node, 'type', None)
        if cast:
            result = result.merge(self.extract(cast))
        expr = getattr(node, 'expr', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('StaticCastExpr')
    def extract_static_cast_expr(self, node) -> SignalResult:
        """StaticCastExpr: static cast expression"""
        result = SignalResult()
        cast = getattr(node, 'cast', None) or getattr(node, 'type', None)
        if cast:
            result = result.merge(self.extract(cast))
        expr = getattr(node, 'expr', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    # Signature expression
    @on('SignatureExpression')
    def extract_signature_expression(self, node) -> SignalResult:
        """SignatureExpression: signature expression"""
        return SignalResult()
    
    # Tagged union expression
    @on('TaggedUnionExpr')
    def extract_tagged_union_expr(self, node) -> SignalResult:
        """TaggedUnionExpr: tagged union expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'value', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    # With expression
    @on('WithExpression')
    def extract_with_expression_stmt(self, node) -> SignalResult:
        """WithExpression: with expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'array', None)
        if expr:
            result = result.merge(self.extract(expr))
        with_clause = getattr(node, 'with', None) or getattr(node, 'clause', None)
        if with_clause:
            result = result.merge(self.extract(with_clause))
        return result
    
    # Randomize method expressions
    @on('RandomizeMethodExpr')
    def extract_randomize_method_expr(self, node) -> SignalResult:
        """RandomizeMethodExpr: randomize() method expression"""
        result = SignalResult()
        with_expr = getattr(node, 'with', None)
        if with_expr:
            result = result.merge(self.extract(with_expr))
        return result
    
    @on('PrerandomizeMethodExpr')
    def extract_prerandomize_method_expr(self, node) -> SignalResult:
        """PrerandomizeMethodExpr: pre_randomize() method expression"""
        return SignalResult()
    
    @on('PostrandomizeMethodExpr')
    def extract_postrandomize_method_expr(self, node) -> SignalResult:
        """PostrandomizeMethodExpr: post_randomize() method expression"""
        return SignalResult()
    
    # Array method expressions
    @on('ArrayMethodExpr')
    def extract_array_method_expr(self, node) -> SignalResult:
        """ArrayMethodExpr: array method expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'array', None)
        if expr:
            result = result.merge(self.extract(expr))
        with_expr = getattr(node, 'with', None)
        if with_expr:
            result = result.merge(self.extract(with_expr))
        return result
    
    @on('ArrayAndMethodExpr')
    def extract_array_and_method_expr_stmt(self, node) -> SignalResult:
        """ArrayAndMethodExpr: array.and() method expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'array', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ArrayOrMethodExpr')
    def extract_array_or_method_expr_stmt(self, node) -> SignalResult:
        """ArrayOrMethodExpr: array.or() method expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'array', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ArrayUniqueMethodExpr')
    def extract_array_unique_method_expr_stmt(self, node) -> SignalResult:
        """ArrayUniqueMethodExpr: array.unique() method expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'array', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ArrayXorMethodExpr')
    def extract_array_xor_method_expr_stmt(self, node) -> SignalResult:
        """ArrayXorMethodExpr: array.xor() method expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'array', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ArrayOrRandomizeMethodExpr')
    def extract_array_or_randomize_method_expr(self, node) -> SignalResult:
        """ArrayOrRandomizeMethodExpr: array.or_randomize() method expression"""
        return SignalResult()
    
    # Expression statements
    @on('ExpressionStatement')
    def extract_expression_statement_stmt(self, node) -> SignalResult:
        """ExpressionStatement: expression statement"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Void expression
    @on('VoidExpression')
    def extract_void_expression(self, node) -> SignalResult:
        """VoidExpression: void expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Primary expressions
    @on('PrimaryExpression')
    def extract_primary_expression_stmt(self, node) -> SignalResult:
        """PrimaryExpression: primary expression"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'expressions', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Simple expressions
    @on('SimpleExpression')
    def extract_simple_expression(self, node) -> SignalResult:
        """SimpleExpression: simple expression"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'expressions', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Bit select expressions
    @on('BitSelectExpr')
    def extract_bit_select_expr(self, node) -> SignalResult:
        """BitSelectExpr: bit select expression"""
        result = SignalResult()
        base = getattr(node, 'base', None) or getattr(node, 'expr', None)
        if base:
            result = result.merge(self.extract(base))
        index = getattr(node, 'index', None) or getattr(node, 'expr2', None)
        if index:
            result = result.merge(self.extract(index))
        return result
    
    @on('PlusBitSelectExpr')
    def extract_plus_bit_select_expr(self, node) -> SignalResult:
        """PlusBitSelectExpr: plus bit select expression"""
        result = SignalResult()
        base = getattr(node, 'base', None) or getattr(node, 'expr', None)
        if base:
            result = result.merge(self.extract(base))
        index = getattr(node, 'index', None)
        if index:
            result = result.merge(self.extract(index))
        return result
    
    @on('MinusBitSelectExpr')
    def extract_minus_bit_select_expr(self, node) -> SignalResult:
        """MinusBitSelectExpr: minus bit select expression"""
        result = SignalResult()
        base = getattr(node, 'base', None) or getattr(node, 'expr', None)
        if base:
            result = result.merge(self.extract(base))
        index = getattr(node, 'index', None)
        if index:
            result = result.merge(self.extract(index))
        return result
    
    # Range select expressions
    @on('AscendingRangeSelectExpr')
    def extract_ascending_range_select_expr(self, node) -> SignalResult:
        """AscendingRangeSelectExpr: ascending range select [a:b]"""
        result = SignalResult()
        base = getattr(node, 'base', None) or getattr(node, 'expr', None)
        if base:
            result = result.merge(self.extract(base))
        left = getattr(node, 'left', None) or getattr(node, 'expr2', None)
        if left:
            result = result.merge(self.extract(left))
        right = getattr(node, 'right', None) or getattr(node, 'expr3', None)
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('DescendingRangeSelectExpr')
    def extract_descending_range_select_expr(self, node) -> SignalResult:
        """DescendingRangeSelectExpr: descending range select [a:b]"""
        result = SignalResult()
        base = getattr(node, 'base', None) or getattr(node, 'expr', None)
        if base:
            result = result.merge(self.extract(base))
        left = getattr(node, 'left', None) or getattr(node, 'expr2', None)
        if left:
            result = result.merge(self.extract(left))
        right = getattr(node, 'right', None) or getattr(node, 'expr3', None)
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('PlusRangeSelectExpr')
    def extract_plus_range_select_expr(self, node) -> SignalResult:
        """PlusRangeSelectExpr: plus range select [a+:b]"""
        result = SignalResult()
        base = getattr(node, 'base', None) or getattr(node, 'expr', None)
        if base:
            result = result.merge(self.extract(base))
        width = getattr(node, 'width', None) or getattr(node, 'expr2', None)
        if width:
            result = result.merge(self.extract(width))
        return result
    
    @on('MinusRangeSelectExpr')
    def extract_minus_range_select_expr(self, node) -> SignalResult:
        """MinusRangeSelectExpr: minus range select [a-:b]"""
        result = SignalResult()
        base = getattr(node, 'base', None) or getattr(node, 'expr', None)
        if base:
            result = result.merge(self.extract(base))
        width = getattr(node, 'width', None) or getattr(node, 'expr2', None)
        if width:
            result = result.merge(self.extract(width))
        return result
    
    # Increment assignment expressions
    @on('IncrementAssignmentExpr')
    def extract_increment_assignment_expr(self, node) -> SignalResult:
        """IncrementAssignmentExpr: increment assignment expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('DecrementAssignmentExpr')
    def extract_decrement_assignment_expr(self, node) -> SignalResult:
        """DecrementAssignmentExpr: decrement assignment expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Package expressions
    @on('PackageExpression')
    def extract_package_expression(self, node) -> SignalResult:
        """PackageExpression: package expression"""
        return SignalResult()
    
    # Class scope expressions
    @on('ClassScopeExpr')
    def extract_class_scope_expr(self, node) -> SignalResult:
        """ClassScopeExpr: class scope expression"""
        result = SignalResult()
        class_name = getattr(node, 'class_name', None) or getattr(node, 'type', None)
        if class_name:
            result = result.merge(self.extract(class_name))
        return result
    
    # Interface handle expressions
    @on('InterfaceHandleExpr')
    def extract_interface_handle_expr(self, node) -> SignalResult:
        """InterfaceHandleExpr: interface handle expression"""
        return SignalResult()
    
    # Bit stream casting expressions
    @on('BitStreamCastExpr')
    def extract_bit_stream_cast_expr(self, node) -> SignalResult:
        """BitStreamCastExpr: bit stream cast expression"""
        result = SignalResult()
        cast = getattr(node, 'cast', None) or getattr(node, 'type', None)
        if cast:
            result = result.merge(self.extract(cast))
        expr = getattr(node, 'expr', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    # Cast expressions with hierarchy
    @on('CastToBitBaseExpr')
    def extract_cast_to_bit_base_expr(self, node) -> SignalResult:
        """CastToBitBaseExpr: cast to bit base expression"""
        expr = getattr(node, 'expr', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('CastToShortIntExpr')
    def extract_cast_to_short_int_expr(self, node) -> SignalResult:
        """CastToShortIntExpr: cast to short int expression"""
        expr = getattr(node, 'expr', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('CastToIntExpr')
    def extract_cast_to_int_expr(self, node) -> SignalResult:
        """CastToIntExpr: cast to int expression"""
        expr = getattr(node, 'expr', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('CastToLongIntExpr')
    def extract_cast_to_long_int_expr(self, node) -> SignalResult:
        """CastToLongIntExpr: cast to long int expression"""
        expr = getattr(node, 'expr', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('CastToByteExpr')
    def extract_cast_to_byte_expr(self, node) -> SignalResult:
        """CastToByteExpr: cast to byte expression"""
        expr = getattr(node, 'expr', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('CastToBitExpr')
    def extract_cast_to_bit_expr(self, node) -> SignalResult:
        """CastToBitExpr: cast to bit expression"""
        expr = getattr(node, 'expr', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('CastToRealExpr')
    def extract_cast_to_real_expr(self, node) -> SignalResult:
        """CastToRealExpr: cast to real expression"""
        expr = getattr(node, 'expr', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Event expressions
    @on('EventExpression')
    def extract_event_expression(self, node) -> SignalResult:
        """EventExpression: event expression"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('BinaryBlockEventExpr')
    def extract_binary_block_event_expr(self, node) -> SignalResult:
        """BinaryBlockEventExpr: binary block event expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Clocking block expressions
    @on('ClockingBlockExpr')
    def extract_clocking_block_expr_stmt(self, node) -> SignalResult:
        """ClockingBlockExpr: clocking block expression"""
        return SignalResult()
    
    # Sequence matching expressions
    @on('MatchedExpr')
    def extract_matched_expr_stmt(self, node) -> SignalResult:
        """MatchedExpr: matched expression"""
        result = SignalResult()
        match = getattr(node, 'match', None) or getattr(node, 'expr', None)
        if match:
            result = result.merge(self.extract(match))
        return result
    
    @on('SyncAcceptSequenceExpr')
    def extract_sync_accept_sequence_expr(self, node) -> SignalResult:
        """SyncAcceptSequenceExpr: sync accept sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('SyncRejectSequenceExpr')
    def extract_sync_reject_sequence_expr(self, node) -> SignalResult:
        """SyncRejectSequenceExpr: sync reject sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('SyncRejectWeakSequenceExpr')
    def extract_sync_reject_weak_sequence_expr(self, node) -> SignalResult:
        """SyncRejectWeakSequenceExpr: sync reject weak sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('SyncSequenceExpr')
    def extract_sync_sequence_expr(self, node) -> SignalResult:
        """SyncSequenceExpr: sync sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('AsyncAcceptSequenceExpr')
    def extract_async_accept_sequence_expr(self, node) -> SignalResult:
        """AsyncAcceptSequenceExpr: async accept sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('AsyncRejectSequenceExpr')
    def extract_async_reject_sequence_expr(self, node) -> SignalResult:
        """AsyncRejectSequenceExpr: async reject sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('AsyncRejectWeakSequenceExpr')
    def extract_async_reject_weak_sequence_expr(self, node) -> SignalResult:
        """AsyncRejectWeakSequenceExpr: async reject weak sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    # More expression types
    @on('EventControlExpression')
    def extract_event_control_expression(self, node) -> SignalResult:
        """EventControlExpression: event control expression"""
        return SignalResult()
    
    @on('DelayControlExpression')
    def extract_delay_control_expression(self, node) -> SignalResult:
        """DelayControlExpression: delay control expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'delay', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('CycleDelayExpression')
    def extract_cycle_delay_expression(self, node) -> SignalResult:
        """CycleDelayExpression: cycle delay expression ##"""
        result = SignalResult()
        count = getattr(node, 'count', None) or getattr(node, 'expr', None)
        if count:
            result = result.merge(self.extract(count))
        return result
    
    @on('RejectStatement')
    def extract_reject_statement(self, node) -> SignalResult:
        """RejectStatement: reject statement"""
        return SignalResult()
    
    @on('AcceptStatement')
    def extract_accept_statement(self, node) -> SignalResult:
        """AcceptStatement: accept statement"""
        return SignalResult()
    
    @on('RejectConditionExpression')
    def extract_reject_condition_expression(self, node) -> SignalResult:
        """RejectConditionExpression: reject condition expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'expr', None)
        if cond:
            result = result.merge(self.extract(cond))
        return result
    
    @on('AcceptConditionExpression')
    def extract_accept_condition_expression(self, node) -> SignalResult:
        """AcceptConditionExpression: accept condition expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'expr', None)
        if cond:
            result = result.merge(self.extract(cond))
        return result
    
    @on('ImplicationExpression')
    def extract_implication_expression(self, node) -> SignalResult:
        """ImplicationExpression: implication expression"""
        result = SignalResult()
        left = getattr(node, 'left', None) or getattr(node, 'antecedent', None)
        right = getattr(node, 'right', None) or getattr(node, 'consequent', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('PropertyListExpression')
    def extract_property_list_expression(self, node) -> SignalResult:
        """PropertyListExpression: property list expression"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('PropertySpecExpression')
    def extract_property_spec_expression(self, node) -> SignalResult:
        """PropertySpecExpression: property spec expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    # Constraint expressions
    @on('ConstraintExpression')
    def extract_constraint_expression(self, node) -> SignalResult:
        """ConstraintExpression: constraint expression"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'constraints', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('UniquenessConstraintExpr')
    def extract_uniqueness_constraint_expr(self, node) -> SignalResult:
        """UniquenessConstraintExpr: uniqueness constraint expression"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ImplicationConstraintExpr')
    def extract_implication_constraint_expr(self, node) -> SignalResult:
        """ImplicationConstraintExpr: implication constraint expression"""
        result = SignalResult()
        left = getattr(node, 'left', None) or getattr(node, 'condition', None)
        right = getattr(node, 'right', None) or getattr(node, 'constraint', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('IfElseConstraintExpr')
    def extract_if_else_constraint_expr(self, node) -> SignalResult:
        """IfElseConstraintExpr: if-else constraint expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'expr', None)
        if cond:
            result = result.merge(self.extract(cond))
        constraint = getattr(node, 'constraint', None) or getattr(node, 'body', None)
        if constraint:
            result = result.merge(self.extract(constraint))
        else_body = getattr(node, 'else_body', None) or getattr(node, 'else', None)
        if else_body:
            result = result.merge(self.extract(else_body))
        return result
    
    @on('ForeachConstraintExpr')
    def extract_foreach_constraint_expr(self, node) -> SignalResult:
        """ForeachConstraintExpr: foreach constraint expression"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        constraint = getattr(node, 'constraint', None) or getattr(node, 'body', None)
        if constraint:
            result = result.merge(self.extract(constraint))
        return result
    
    @on('SolveBeforeConstraintExpr')
    def extract_solve_before_constraint_expr(self, node) -> SignalResult:
        """SolveBeforeConstraintExpr: solve_before constraint expression"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'expressions', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Rand sequence expressions
    @on('RandSequenceExpression')
    def extract_rand_sequence_expression(self, node) -> SignalResult:
        """RandSequenceExpression: rand sequence expression"""
        return SignalResult()
    
    @on('RandSequenceBodyExpr')
    def extract_rand_sequence_body_expr(self, node) -> SignalResult:
        """RandSequenceBodyExpr: rand sequence body expression"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('RandSequenceItemExpr')
    def extract_rand_sequence_item_expr(self, node) -> SignalResult:
        """RandSequenceItemExpr: rand sequence item expression"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('RandSequenceRepeatExpr')
    def extract_rand_sequence_repeat_expr(self, node) -> SignalResult:
        """RandSequenceRepeatExpr: rand sequence repeat expression"""
        result = SignalResult()
        count = getattr(node, 'count', None) or getattr(node, 'expr', None)
        if count:
            result = result.merge(self.extract(count))
        expr = getattr(node, 'expr', None) or getattr(node, 'sequence', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('RandSequenceWhenExpr')
    def extract_rand_sequence_when_expr(self, node) -> SignalResult:
        """RandSequenceWhenExpr: rand sequence when expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'expr', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'sequence', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    def visit_scoped_name(self, node) -> Optional[str]:
        """ScopedName: 点分路径
        
        结构: p.sub.data -> ScopedName(ScopedName(p, sub), data)
        """
        parts = self._extract_scoped_parts(node)
        if len(parts) >= 2:
            combined = '.'.join(parts)
            return self.adapter.clean_name(combined)
        elif len(parts) == 1:
            return parts[0]
        return None
    
    def _extract_scoped_parts(self, node, parts=None) -> List[str]:
        """递归提取 ScopedName 的各部分
        
        Args:
            node: ScopedName AST 节点
            parts: 累积的部分列表
            
        Returns:
            点分路径的各部分
        """
        if parts is None:
            parts = []
        
        kind = getattr(node, 'kind', None)
        if not kind:
            return parts
        
        kind_str = str(kind)
        
        if 'ScopedName' in kind_str:
            left = getattr(node, 'left', None)
            if left:
                self._extract_scoped_parts(left, parts)
            right = getattr(node, 'right', None)
            if right:
                ri = getattr(right, 'identifier', None)
                if ri:
                    rv = getattr(ri, 'value', None)
                    if rv:
                        parts.append(str(rv).strip())
        elif 'IdentifierName' in kind_str:
            ident = getattr(node, 'identifier', None)
            if ident:
                val = getattr(ident, 'value', None)
                if val:
                    parts.append(str(val).strip())
        
        return parts
    
    # =========================================================================
    # [P0] 字面量 - 必须实现
    # =========================================================================
    
    def visit_integer_literal(self, node) -> Optional[str]:
        """IntegerLiteral: 简单整数字面量 0, 1, 255 等
        """
        val = getattr(node, 'value', None)
        if val is not None:
            return str(val).strip()
        return str(node).strip()
    
    def visit_integer_vector(self, node) -> Optional[str]:
        """IntegerVectorExpression: 带位宽的字面量 8'hAA, 16'd123
        """
        import pyslang
        val = getattr(node, 'value', None)
        if isinstance(val, pyslang.Token) and val.kind == pyslang.TokenKind.IntegerLiteral:
            return str(node).strip()
        return str(node).strip()
    
    # =========================================================================
    # [P1] 位选择 - 常用，必须实现
    # =========================================================================
    
    def visit_element_select(self, node) -> Optional[str]:
        """ElementSelect: 位选择 data[5]
        
        结构: ElementSelect.value = data, selector = 5
        """
        value = getattr(node, 'value', None)
        selector = getattr(node, 'selector', None)
        
        if value and selector is not None:
            base_name = None
            if hasattr(value, 'symbol'):
                sym = value.symbol
                if hasattr(sym, 'name'):
                    base_name = str(sym.name)
            
            if base_name:
                selector_val = getattr(selector, 'value', None)
                if selector_val is not None:
                    return f"{base_name}[{selector_val}]"
        
        # 兜底: 递归获取基础信号
        if value:
            base = self.visit(value)
            if base:
                return base
        return None
    
    def visit_range_select(self, node) -> Optional[str]:
        """RangeSelect: 范围选择 data[3:0]
        
        结构: RangeSelect.value = data, left = 3, right = 0
        """
        value = getattr(node, 'value', None)
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        
        if value and left is not None and right is not None:
            base_signals = self.get_all_signals(value)
            if base_signals:
                base_name = base_signals[0]
                left_val = getattr(left, 'value', None)
                right_val = getattr(right, 'value', None)
                if left_val is not None and right_val is not None:
                    return f"{base_name}[{left_val}:{right_val}]"
        
        # 兜底
        if value:
            return self.visit(value)
        return None
    
    # =========================================================================
    # [P1] 表达式类型
    # =========================================================================
    
    def visit_conversion(self, node) -> Optional[str]:
        """Conversion: 隐式类型转换
        
        例如: assign dout = data[5]; data[5] 是 ElementSelect,外面包了一层 Conversion
        """
        operand = getattr(node, 'operand', None)
        if operand:
            return self.visit(operand)
        return None
    
    def visit_member_access(self, node) -> Optional[str]:
        """MemberAccessExpression: class 成员访问 p.addr
        
        结构: member = p, member_sym = addr
        """
        value = getattr(node, 'value', None) or getattr(node, 'expression', None)
        member_sym = getattr(node, 'member', None)
        
        if value and member_sym:
            base_name = self.visit(value)
            member_name = getattr(member_sym, 'name', None)
            if member_name:
                member_name = str(member_name).strip()
            else:
                member_name = str(member_sym).strip()
            
            if base_name and member_name:
                return f"{base_name}.{member_name}"
        return None
    
    def visit_binary_expression(self, node) -> Optional[str]:
        """BinaryExpression: 二元表达式 a + b, a & b 等
        
        默认返回左操作数
        """
        left = getattr(node, 'left', None)
        if left:
            return self.visit(left)
        return None
    
    def visit_call(self, node) -> Optional[str]:
        """Call/InvocationExpression: 函数调用
        
        结构: InvocationExpression.left = IdentifierName (函数名)
        """
        left = getattr(node, 'left', None)
        if left:
            identifier = getattr(left, 'identifier', None)
            if identifier:
                val = getattr(identifier, 'value', None)
                if val:
                    return str(val).strip()
            return str(left).strip()
        return None
    
    def visit_parenthesized(self, node) -> Optional[str]:
        """ParenthesizedExpression: (expr)
        """
        expr = getattr(node, 'expression', None)
        if expr:
            return self.visit(expr)
        return None
    
    def visit_unary(self, node) -> Optional[str]:
        """UnaryExpression: ~a, -a, !a 等
        """
        operand = getattr(node, 'operand', None) or getattr(node, 'expression', None)
        if operand:
            return self.visit(operand)
        return None
    
    # =========================================================================
    # [P1] 复合表达式 - 返回多个信号
    # =========================================================================
    
    def get_all_conditional_op(self, node) -> List[str]:
        """ConditionalOp: 三元运算符 sel ? a : b
        
        返回: [sel, a, b]
        """
        signals = []
        
        # predicate (condition)
        conditions = getattr(node, 'conditions', None)
        if conditions and len(conditions) > 0:
            cond_expr = getattr(conditions[0], 'expr', None)
            if cond_expr:
                signals.extend(self.get_all_signals(cond_expr))
        
        # Also try .predicate for compatibility
        pred = getattr(node, 'predicate', None)
        if pred:
            signals.extend(self.get_all_signals(pred))
        
        # left (true branch)
        left = getattr(node, 'left', None)
        if left:
            signals.extend(self.get_all_signals(left))
        
        # right (false branch)
        right = getattr(node, 'right', None)
        if right:
            signals.extend(self.get_all_signals(right))
        
        return [s for s in signals if s]
    
    def get_all_concatenation(self, node) -> List[str]:
        """ConcatenationExpression: {a, b, c}
        
        返回: [a, b, c]
        """
        signals = []
        operands = getattr(node, 'operands', None) or getattr(node, 'expressions', None)
        
        if operands:
            for expr in operands:
                expr_kind = getattr(expr, 'kind', None)
                if expr_kind and 'Token' not in str(expr_kind):
                    signals.extend(self.get_all_signals(expr))
        
        return [s for s in signals if s]
    
    def get_all_call(self, node) -> List[str]:
        """Call: 函数调用参数
        
        支持:
        - 位置参数: func(a, b, c)
        - 命名参数: func(.name(a), .value(b))
        
        返回: [arg1, arg2, ...]
        """
        signals = []
        args = getattr(node, 'arguments', None)
        
        if args:
            # Handle OrderedArgument vs NamedArgument
            for arg in args:
                if arg is None:
                    continue
                # NamedArgument has .name and .expr
                expr = getattr(arg, 'expr', None) or getattr(arg, 'value', None)
                if expr:
                    signals.extend(self.get_all_signals(expr))
                else:
                    # Maybe it's just an expression directly
                    signals.extend(self.get_all_signals(arg))
        
        return [s for s in signals if s]
    
    def get_all_element_select(self, node) -> List[str]:
        """ElementSelect: 位选择
        
        返回: [base[index]]
        """
        result = self.visit(node)
        return [result] if result else []
    
    def get_all_range_select(self, node) -> List[str]:
        """RangeSelect: 范围选择
        
        返回: [base[left:right]]
        """
        result = self.visit(node)
        return [result] if result else []
    
    # =========================================================================
    # [P2] 特殊类型
    # =========================================================================
    
    def visit_identifier_select(self, node) -> Optional[str]:
        """IdentifierSelect: data[3] 等带位选的标识符
        
        结构: identifier.value = "data", selectors = [ElementSelect]
        """
        base_name = None
        if hasattr(node, 'identifier'):
            ident = node.identifier
            if hasattr(ident, 'value'):
                base_name = str(ident.value).strip()
            else:
                base_name = str(ident).strip()
        
        if not base_name:
            base_name = str(node).strip().split('[')[0]
        
        # 获取位选索引
        selectors = getattr(node, 'selectors', None)
        if selectors and hasattr(selectors, '__iter__'):
            for i in range(len(selectors)):
                sel = selectors[i]
                sel_kind = str(getattr(sel, 'kind', ''))
                
                if 'ElementSelect' in sel_kind:
                    bit_select = getattr(sel, 'selector', None)
                    if bit_select:
                        bit_select_kind = str(getattr(bit_select, 'kind', ''))
                        
                        if 'SimpleRange' in bit_select_kind:
                            # 范围选择
                            left_expr = getattr(bit_select, 'left', None)
                            right_expr = getattr(bit_select, 'right', None)
                            
                            param_map = self._get_param_map()
                            left_val = self._evaluate_expr(left_expr, param_map) if left_expr else None
                            right_val = self._evaluate_expr(right_expr, param_map) if right_expr else None
                            
                            if left_val is not None or right_val is not None:
                                left_str = str(left_val) if left_val is not None else '?'
                                right_str = str(right_val) if right_val is not None else '?'
                                return self.adapter.clean_name(f"{base_name}[{left_str}:{right_str}]")
                        else:
                            # 单位选择
                            selector_expr = getattr(bit_select, 'expr', None)
                            if selector_expr:
                                param_map = self._get_param_map()
                                evaluated = self._evaluate_expr(selector_expr, param_map)
                                if evaluated is not None:
                                    return self.adapter.clean_name(f"{base_name}[{evaluated}]")
                
                elif 'SimpleRangeSelect' in sel_kind:
                    range_sel = getattr(sel, 'selector', None) or sel
                    left_expr = getattr(range_sel, 'left', None)
                    right_expr = getattr(range_sel, 'right', None)
                    
                    if left_expr or right_expr:
                        param_map = self._get_param_map()
                        left_val = self._evaluate_expr(left_expr, param_map) if left_expr else None
                        right_val = self._evaluate_expr(right_expr, param_map) if right_expr else None
                        
                        if left_val is not None or right_val is not None:
                            left_str = str(left_val) if left_val is not None else '?'
                            right_str = str(right_val) if right_val is not None else '?'
                            return self.adapter.clean_name(f"{base_name}[{left_str}:{right_str}]")
        
        return self.adapter.clean_name(base_name) if base_name else None
    
    def visit_hierarchical_value(self, node) -> Optional[str]:
        """HierarchicalValueExpression: ifc.data (interface 成员访问)
        
        结构: HierarchicalValueExpression.syntax = ScopedNameSyntax
        """
        syntax = getattr(node, 'syntax', None)
        if syntax and hasattr(syntax, 'kind'):
            kind_str = str(syntax.kind)
            if 'ScopedName' in kind_str:
                return self.visit_scoped_name(syntax)
        return None
    
    def visit_multiple_concatenation(self, node) -> Optional[str]:
        """MultipleConcatenationExpression: {N{signal}}
        
        结构: signal.concatenation.expressions
        """
        if hasattr(node, 'concatenation'):
            concat = node.concatenation
            if concat and hasattr(concat, 'expressions'):
                exprs = concat.expressions
                if hasattr(exprs, '__iter__') and not isinstance(exprs, str):
                    for expr_item in exprs:
                        if hasattr(expr_item, 'kind'):
                            result = self.visit(expr_item)
                            if result:
                                return result
                else:
                    result = self.visit(exprs)
                    if result:
                        return result
        return None
    
    def visit_replication(self, node) -> Optional[str]:
        """ReplicationExpression: {N{signal}}
        
        结构: ReplicationExpression.concat = ConcatenationExpression
        """
        concat = getattr(node, 'concat', None)
        if concat and hasattr(concat, 'operands'):
            operands = concat.operands
            if hasattr(operands, '__iter__') and not isinstance(operands, str):
                for expr_item in operands:
                    if hasattr(expr_item, 'kind'):
                        result = self.visit(expr_item)
                        if result:
                            return result
            else:
                result = self.visit(operands)
                if result:
                    return result
        return None
    
    def visit_cast_expression(self, node) -> Optional[str]:
        """CastExpression: type'(expr) or signed'(expr)
        
        返回: expr 的信号
        """
        expr = getattr(node, 'expression', None) or getattr(node, 'operand', None)
        if expr:
            return self.visit(expr)
        return None
    
    def visit_tagged_union_expression(self, node) -> Optional[str]:
        """TaggedUnionExpression: tag'(expr)
        
        返回: expr 的信号
        """
        expr = getattr(node, 'expression', None)
        if expr:
            return self.visit(expr)
        return None
    
    def visit_multiple_concatenation(self, node) -> Optional[str]:
        """MultipleConcatenationExpression: {{n{expr}}
        
        返回: expr 的信号
        """
        expr = getattr(node, 'expression', None)
        if expr:
            return self.visit(expr)
        return None
    
    def visit_stream_expression(self, node) -> Optional[str]:
        """StreamExpression: {>>[type]{expr}} or {<<[type]{expr}}
        
        返回: expr 的信号
        """
        expr = getattr(node, 'expression', None) or getattr(node, 'body', None)
        if expr:
            return self.visit(expr)
        return None
    
    def visit_assignment_pattern(self, node) -> Optional[str]:
        """AssignmentPatternExpression: '{a, b, c}
        
        返回: 第一个信号的名称
        """
        signals = []
        # AssignmentPattern may have 'patterns' or 'items'
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    sig = self.visit(p)
                    if sig:
                        signals.append(sig)
        return signals[0] if signals else None
    
    def visit_null_literal(self, node) -> Optional[str]:
        """NullLiteralExpression: null
        
        返回: None (null 没有信号名)
        """
        return None
    
    def visit_string_literal(self, node) -> Optional[str]:
        """StringLiteralExpression: "string"
        
        返回: None (字符串没有信号名)
        """
        return None
    
    def visit_clock_event(self, node) -> Optional[str]:
        """ClockingEvent: @clk, @(posedge clk)
        
        提取事件控制中的信号名
        """
        # ClockingEvent may have 'clock' or 'event'
        event = getattr(node, 'event', None) or getattr(node, 'clock', None)
        if event:
            return self.visit(event)
        
        # Try expression for event control
        expr = getattr(node, 'expression', None)
        if expr:
            return self.visit(expr)
        return None
    
    def visit_empty_argument(self, node) -> Optional[str]:
        """EmptyArgument: 函数参数占位 ,,
        
        返回: None
        """
        return None
    
    def visit_data_type(self, node) -> Optional[str]:
        """DataType: bit, logic, int 等类型声明
        
        返回: None (类型没有信号)
        """
        return None
    
    def visit_type_reference(self, node) -> Optional[str]:
        """TypeReference: 类型引用
        
        返回: None
        """
        return None
    
    def visit_time_literal(self, node) -> Optional[str]:
        """TimeLiteralExpression: 1ns, 1us 等
        
        返回: None (时间字面量没有信号)
        """
        return None
    
    def visit_real_literal(self, node) -> Optional[str]:
        """RealLiteralExpression: 1.5, 3.14 等
        
        返回: None (实数没有信号)
        """
        return None
    
    def visit_unbased_unsized_integer_literal(self, node) -> Optional[str]:
        """UnbasedUnsizedIntegerLiteral: '0, '1, 'x, 'z
        
        返回: None
        """
        return None
    
    def visit_unbounded_literal(self, node) -> Optional[str]:
        """UnboundedLiteral: $
        
        返回: None
        """
        return None
    
    def visit_unary_operator(self, node) -> Optional[str]:
        """UnaryOperator: 一元运算符表达式
        
        与 UnaryOp 相同处理
        """
        operand = getattr(node, 'operand', None) or getattr(node, 'expression', None)
        if operand:
            return self.visit(operand)
        return None
    
    def visit_binary_operator(self, node) -> Optional[str]:
        """BinaryOperator: 二元运算符表达式
        
        与 BinaryOp 相同处理
        """
        left = getattr(node, 'left', None)
        if left:
            return self.visit(left)
        return None
    
    def visit_assignment_expression(self, node) -> Optional[str]:
        """AssignmentExpression: 赋值表达式 a = b
        
        默认返回左操作数
        """
        left = getattr(node, 'left', None)
        if left:
            return self.visit(left)
        return None
    
    def visit_new_class(self, node) -> Optional[str]:
        """NewClassExpression: new() 或 new(expr)
        
        返回: None (构造函数没有信号)
        """
        return None
    
    def visit_new_array(self, node) -> Optional[str]:
        """NewArrayExpression: new[size]
        
        返回: size 中的信号
        """
        size = getattr(node, 'size', None) or getattr(node, 'expression', None)
        if size:
            return self.visit(size)
        return None
    
    def visit_new_covergroup(self, node) -> Optional[str]:
        """NewCovergroupExpression: covergroup
        
        返回: None
        """
        return None
    
    def visit_copy_class(self, node) -> Optional[str]:
        """CopyClassExpression: class.copy()
        
        返回: None
        """
        return None
    
    def visit_arbitrary_symbol(self, node) -> Optional[str]:
        """ArbitrarySymbol: 未解析的符号
        
        返回符号名
        """
        name = getattr(node, 'name', None)
        if name:
            return str(name).strip()
        return None
    
    def visit_l_value_reference(self, node) -> Optional[str]:
        """LValueReference: 左值引用
        
        返回引用的信号
        """
        value = getattr(node, 'value', None)
        if value:
            return self.visit(value)
        return None
    
    def visit_assertion_instance(self, node) -> Optional[str]:
        """AssertionInstance: assert property 等
        
        返回: None
        """
        return None

    def visit_replicated_assignment_pattern(self, node) -> Optional[str]:
        """ReplicatedAssignmentPattern: '{n{a, b, c}}
        
        提取模式中的信号
        """
        signals = []
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    sig = self.visit(p)
                    if sig:
                        signals.append(sig)
        return signals[0] if signals else None
    
    def get_all_replicated_assignment_pattern(self, node) -> List[str]:
        """ReplicatedAssignmentPattern: '{n{a, b, c}}
        
        递归提取所有模式中的信号
        """
        signals = []
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    signals.extend(self.get_all_signals(p))
        return [s for s in signals if s]
    
    def visit_simple_assignment_pattern(self, node) -> Optional[str]:
        """SimpleAssignmentPattern: '{a, b, c}
        
        提取模式中的信号
        """
        signals = []
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    sig = self.visit(p)
                    if sig:
                        signals.append(sig)
        return signals[0] if signals else None
    
    def get_all_simple_assignment_pattern(self, node) -> List[str]:
        """SimpleAssignmentPattern: '{a, b, c}
        
        递归提取所有模式中的信号
        """
        signals = []
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    signals.extend(self.get_all_signals(p))
        return [s for s in signals if s]
    
    def visit_structured_assignment_pattern(self, node) -> Optional[str]:
        """StructuredAssignmentPattern: '{a: x, b: y}
        
        提取模式中的信号
        """
        signals = []
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    sig = self.visit(p)
                    if sig:
                        signals.append(sig)
        return signals[0] if signals else None
    
    def get_all_structured_assignment_pattern(self, node) -> List[str]:
        """StructuredAssignmentPattern: '{a: x, b: y}
        
        递归提取所有模式中的信号
        """
        signals = []
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    signals.extend(self.get_all_signals(p))
        return [s for s in signals if s]

    # =========================================================================
    # 辅助方法
    # =========================================================================
    
    def _get_param_map(self) -> Dict[str, int]:
        """获取模块参数映射"""
        param_map = {}
        try:
            if hasattr(self.adapter, '_current_module') and self.adapter._current_module:
                params = self.adapter.get_module_parameters(self.adapter._current_module)
                for p in params:
                    name = p.get('name')
                    value = p.get('value')
                    if name and value is not None:
                        try:
                            param_map[name] = int(value)
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass
        return param_map
    
    def _evaluate_expr(self, expr, param_map: Dict[str, int]) -> Optional[Any]:
        """评估表达式，解析参数"""
        if expr is None:
            return None
        
        try:
            # 尝试获取 value 属性
            val = getattr(expr, 'value', None)
            if val is not None:
                # 检查是否是参数引用
                if hasattr(expr, 'symbol'):
                    sym = expr.symbol
                    if sym and hasattr(sym, 'name'):
                        name = str(sym.name)
                        if name in param_map:
                            return param_map[name]
                return int(val) if isinstance(val, (int, float)) else val
            
            # 二元表达式
            if hasattr(expr, 'left') and hasattr(expr, 'right'):
                left = self._evaluate_expr(getattr(expr, 'left', None), param_map)
                right = self._evaluate_expr(getattr(expr, 'right', None), param_map)
                
                if left is not None and right is not None:
                    op = str(getattr(expr, 'kind', ''))
                    if 'Add' in op:
                        return left + right
                    elif 'Subtract' in op:
                        return left - right
                    elif 'Multiply' in op:
                        return left * right
                    elif 'Divide' in op and right != 0:
                        return left // right
            
            return None
        except Exception:
            return None