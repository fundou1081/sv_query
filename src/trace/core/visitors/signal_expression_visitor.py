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