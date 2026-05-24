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
        @on('IdentifierName')
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
        使用 @on 装饰器注册 handler，
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
    
    @on('EmptyArgument')
    def extract_empty_argument(self, node) -> SignalResult:
        """[NOT TESTED] EmptyArgument: 函数参数占位"""
        return SignalResult()
    
    @on('InsideExpression')
    def extract_inside(self, node) -> SignalResult:
        """[NOT TESTED] InsideExpression: expr inside {a, b, c}"""
        left = getattr(node, 'left', None) or getattr(node, 'condition', None)
        right = getattr(node, 'right', None) or getattr(node, 'range', None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)
    
    @on('MinTypMaxExpression')
    def extract_min_typ_max(self, node) -> SignalResult:
        """[NOT TESTED] MinTypMaxExpression: min:typ:max"""
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
    
    @on('ValueRangeExpression')
    def extract_value_range(self, node) -> SignalResult:
        """[NOT TESTED] ValueRangeExpression: [a:b] or [a..b]"""
        left = getattr(node, 'left', None) or getattr(node, 'low', None)
        right = getattr(node, 'right', None) or getattr(node, 'high', None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)
    
    @on('MultipleConcatenationExpression')
    def extract_multiple_concatenation(self, node) -> SignalResult:
        """[NOT TESTED] MultipleConcatenationExpression: {{n{expr}}"""
        expr = getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('StreamExpression')
    def extract_stream_expression(self, node) -> SignalResult:
        """[NOT TESTED] StreamExpression: {>>[type]{expr}} or {<<[type]{expr}}"""
        expr = getattr(node, 'expression', None) or getattr(node, 'body', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('AssignmentPatternExpression')
    def extract_assignment_pattern(self, node) -> SignalResult:
        """[NOT TESTED] AssignmentPatternExpression: '{a, b, c}"""
        result = SignalResult()
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result
    
    @on('TypeReference')
    def extract_type_reference(self, node) -> SignalResult:
        """[NOT TESTED] TypeReference: 类型引用"""
        return SignalResult()
    
    @on('AssignmentExpression')
    def extract_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] AssignmentExpression: a = b"""
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        left_result = self.extract(left) if left else SignalResult()
        right_result = self.extract(right) if right else SignalResult()
        return left_result.merge(right_result)
    
    @on('NewClassExpression')
    def extract_new_class(self, node) -> SignalResult:
        """[NOT TESTED] NewClassExpression: new()"""
        return SignalResult()
    
    @on('NewArrayExpression')
    def extract_new_array(self, node) -> SignalResult:
        """[NOT TESTED] NewArrayExpression: new[size]"""
        size = getattr(node, 'size', None) or getattr(node, 'expression', None)
        if size:
            return self.extract(size)
        return SignalResult()
    
    @on('CopyClassExpression')
    def extract_copy_class(self, node) -> SignalResult:
        """[NOT TESTED] CopyClassExpression: class.copy()"""
        return SignalResult()
    
    @on('ConcatenationExpression')
    def extract_concatenation(self, node) -> SignalResult:
        """[NOT TESTED] ConcatenationExpression: {a, b, c}"""
        result = SignalResult()
        operands = getattr(node, 'operands', None) or getattr(node, 'expressions', None)
        if operands:
            for expr in operands:
                expr_kind = getattr(expr, 'kind', None)
                if expr_kind and 'Token' not in str(expr_kind):
                    result = result.merge(self.extract(expr))
        return result
    
    @on('ScopedName')
    def extract_scoped_name(self, node) -> SignalResult:
        """[NOT TESTED] ScopedName: 点分路径 p.sub.data"""
        parts = self._extract_scoped_parts(node)
        if parts:
            combined = '.'.join(parts)
            name = self.adapter.clean_name(combined)
            return SignalResult.single(name)
        return SignalResult()
    
    @on('ElementSelectExpression')
    def extract_element_select(self, node) -> SignalResult:
        """[MIGRATED] ElementSelectExpression: data[5] bit select
        
        From visit_element_select - handles symbol-based selectors
        """
        value = getattr(node, 'value', None) or getattr(node, 'base', None) or getattr(node, 'left', None)
        selector = getattr(node, 'selector', None)
        
        if value and selector is not None:
            base_name = None
            # Try to get name from symbol
            if hasattr(value, 'symbol'):
                sym = value.symbol
                if hasattr(sym, 'name'):
                    base_name = str(sym.name)
            
            if base_name:
                selector_val = getattr(selector, 'value', None)
                if selector_val is not None:
                    return SignalResult(primary=f"{base_name}[{selector_val}]")
        
        # Fall back to extracting from base
        if value:
            return self.extract(value)
        return SignalResult()

    def extract_element_select(self, node) -> SignalResult:
        """[NOT TESTED] ElementSelectExpression: data[5]"""
        base = getattr(node, 'left', None) or getattr(node, 'base', None) or getattr(node, 'value', None)
        if base:
            return self.extract(base)
        return SignalResult()
    
    @on('CastExpression')
    def extract_cast_expression(self, node) -> SignalResult:
        """[NOT TESTED] CastExpression: type'(expr)"""
        expr = getattr(node, 'expression', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('TaggedUnionExpression')
    def extract_tagged_union_expression(self, node) -> SignalResult:
        """[NOT TESTED] TaggedUnionExpression: tag'(expr)"""
        expr = getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('IntegerVectorExpression')
    def extract_integer_vector(self, node) -> SignalResult:
        """[NOT TESTED] IntegerVectorExpression: 带位宽的字面量"""
        return SignalResult()
    
    @on('ReplicatedAssignmentPattern')
    def extract_replicated_assignment_pattern(self, node) -> SignalResult:
        """[NOT TESTED] ReplicatedAssignmentPattern: '{n{a, b, c}}"""
        result = SignalResult()
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result
    
    @on('SimpleAssignmentPattern')
    def extract_simple_assignment_pattern(self, node) -> SignalResult:
        """[NOT TESTED] SimpleAssignmentPattern: 简单赋值模式"""
        result = SignalResult()
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result
    
    @on('StructuredAssignmentPattern')
    def extract_structured_assignment_pattern(self, node) -> SignalResult:
        """[NOT TESTED] StructuredAssignmentPattern: 结构化赋值模式"""
        result = SignalResult()
        patterns = getattr(node, 'patterns', None) or getattr(node, 'items', None)
        if patterns and hasattr(patterns, '__iter__') and not isinstance(patterns, str):
            for p in patterns:
                if p:
                    result = result.merge(self.extract(p))
        return result
    
    @on('MemberAccessExpression')
    def extract_member_access(self, node) -> SignalResult:
        """[NOT TESTED] MemberAccessExpression: obj.member"""
        obj = getattr(node, 'left', None) or getattr(node, 'expression', None)
        if obj:
            return self.extract(obj)
        return SignalResult()
    
    @on('DelayControl')
    def extract_delay_control(self, node) -> SignalResult:
        """[NOT TESTED] DelayControl: #1delay"""
        expr = getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('EventControl')
    def extract_event_control(self, node) -> SignalResult:
        """[NOT TESTED] EventControl: @event"""
        event = getattr(node, 'event', None)
        if event:
            return self.extract(event)
        return SignalResult()
    
    @on('ClockingPropertyExpr')
    def extract_clocking_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] ClockingPropertyExpr: property with clock"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        clock = getattr(node, 'clock', None)
        if clock:
            result = result.merge(self.extract(clock))
        return result
    
    @on('DisableConstraint')
    def extract_disable_constraint(self, node) -> SignalResult:
        """[NOT TESTED] DisableConstraint: disable constraint"""
        expr = getattr(node, 'expr', None) or getattr(node, 'constraint', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('SolveBeforeConstraint')
    def extract_solve_before_constraint(self, node) -> SignalResult:
        """[NOT TESTED] SolveBeforeConstraint: solve before constraint"""
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
        """[NOT TESTED] ExpressionConstraint: expression constraint"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('ConditionalPattern')
    def extract_conditional_pattern(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalPattern: pattern if cond"""
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
        """[NOT TESTED] WildcardPattern: wildcard pattern"""
        return SignalResult()
    
    @on('TaggedPattern')
    def extract_tagged_pattern(self, node) -> SignalResult:
        """[NOT TESTED] TaggedPattern: tagged pattern"""
        result = SignalResult()
        pattern = getattr(node, 'pattern', None)
        if pattern:
            result = result.merge(self.extract(pattern))
        return result
    
    @on('EmptyStatement')
    def extract_empty_statement(self, node) -> SignalResult:
        """[NOT TESTED] EmptyStatement: empty statement"""
        return SignalResult()
    
    @on('CasePropertyExpr')
    def extract_case_property_expression(self, node) -> SignalResult:
        """[NOT TESTED] CasePropertyExpression: case property expression"""
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
    
    @on('UnaryPropertyExpr')
    def extract_unary_property_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryPropertyExpression: unary property"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('SequenceRepetition')
    def extract_sequence_repetition(self, node) -> SignalResult:
        """[NOT TESTED] SequenceRepetition: seq[*1:3]"""
        seq = getattr(node, 'sequence', None) or getattr(node, 'operand', None)
        if seq:
            return self.extract(seq)
        return SignalResult()
    
    @on('ConditionalExpression')
    def extract_conditional_expression(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalExpression: cond ? expr1 : expr2"""
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
    
    @on('LetDeclaration')
    def extract_let_declaration(self, node) -> SignalResult:
        """[NOT TESTED] LetDeclaration: let declaration"""
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
    
    @on('ProceduralAssignStatement')
    def extract_procedural_assign_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ProceduralAssignStatement: procedural assign"""
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
        """[NOT TESTED] ProceduralForceStatement: procedural force"""
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()
    
    @on('ExpressionStatement')
    def extract_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ExpressionStatement: expression statement"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('ImplicitEventControl')
    def extract_implicit_event_control(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitEventControl: @@"""
        return SignalResult()
    
    @on('WaitForkStatement')
    def extract_wait_fork_statement(self, node) -> SignalResult:
        """[NOT TESTED] WaitForkStatement: wait fork"""
        return SignalResult()
    
    @on('WaitOrderStatement')
    def extract_wait_order_statement(self, node) -> SignalResult:
        """[NOT TESTED] WaitOrderStatement: wait order"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ProceduralDeassignStatement')
    def extract_procedural_deassign_statement(self, node) -> SignalResult:
        """[NOT TESTED] ProceduralDeassignStatement: procedural deassign"""
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            return self.extract(lvalue)
        return SignalResult()
    
    @on('RandCaseStatement')
    def extract_rand_case_statement(self, node) -> SignalResult:
        """[NOT TESTED] RandCaseStatement: rand case"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('RandCaseItem')
    def extract_rand_case_item(self, node) -> SignalResult:
        """[NOT TESTED] RandCaseItem: rand case item"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'weight', None)
        if cond:
            result = result.merge(self.extract(cond))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('ConditionalStatement')
    def extract_conditional_statement(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalStatement: conditional statement"""
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
    @on('VariablePattern')
    def extract_variable_pattern(self, node) -> SignalResult:
        """[NOT TESTED] VariablePattern: variable pattern"""
        var = getattr(node, 'var', None) or getattr(node, 'expr', None)
        if var:
            return self.extract(var)
        return SignalResult()
    
    @on('StructurePattern')
    def extract_structure_pattern(self, node) -> SignalResult:
        """[NOT TESTED] StructurePattern: structure pattern"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'patterns', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Assertion expr kinds
    @on('UnaryBinsSelectExpr')
    def extract_unary_bins_select_expr(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBinsSelectExpr: unary bins select expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('BinaryBinsSelectExpr')
    def extract_binary_bins_select_expr(self, node) -> SignalResult:
        """[NOT TESTED] BinaryBinsSelectExpr: binary bins select expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('AddExpression')
    def extract_add_expression(self, node) -> SignalResult:
        """[NOT TESTED] AddExpression: addition expression"""
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
        """[NOT TESTED] SubtractExpression: subtraction expression"""
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
        """[NOT TESTED] MultiplyExpression: multiplication expression"""
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
        """[NOT TESTED] DivideExpression: division expression"""
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
        """[NOT TESTED] BinaryAndExpression: binary and expression"""
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
        """[NOT TESTED] BinaryOrExpression: binary or expression"""
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
        """[NOT TESTED] BinaryXorExpression: binary xor expression"""
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
        """[NOT TESTED] BinaryXnorExpression: binary xnor expression"""
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
        """[NOT TESTED] EqualityExpression: equality expression =="""
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
        """[NOT TESTED] InequalityExpression: inequality expression !="""
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
        """[NOT TESTED] CaseEqualityExpression: case equality expression ==="""
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
        """[NOT TESTED] CaseInequalityExpression: case inequality expression !=="""
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
        """[NOT TESTED] LessThanExpression: less than expression <"""
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
        """[NOT TESTED] GreaterThanExpression: greater than expression >"""
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
        """[NOT TESTED] WildcardEqualityExpression: wildcard equality expression ==?"""
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
        """[NOT TESTED] WildcardInequalityExpression: wildcard inequality expression !=?"""
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
        """[NOT TESTED] AndPropertyExpr: and property expression"""
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
        """[NOT TESTED] OrPropertyExpr: or property expression"""
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
        """[NOT TESTED] ImplicationPropertyExpr: implication property expression"""
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
        """[NOT TESTED] AndSequenceExpr: and sequence expression"""
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
        """[NOT TESTED] OrSequenceExpr: or sequence expression"""
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
        """[NOT TESTED] FirstMatchSequenceExpr: first_match sequence expression"""
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            return self.extract(seq)
        return SignalResult()
    
    @on('ClockingSequenceExpr')
    def extract_clocking_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] ClockingSequenceExpr: clocking sequence expression"""
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
        """[NOT TESTED] ArithmeticShiftLeftExpression: arithmetic shift left <<<"""
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
        """[NOT TESTED] ArithmeticShiftRightExpression: arithmetic shift right >>>"""
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
        """[NOT TESTED] PowerExpression: power expression **"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('AddAssignmentExpression')
    def extract_add_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] AddAssignmentExpression: add assignment +="""
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
        """[NOT TESTED] SubtractAssignmentExpression: subtract assignment -="""
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
        """[NOT TESTED] AndAssignmentExpression: and assignment &="""
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
        """[NOT TESTED] OrAssignmentExpression: or assignment |="""
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
        """[NOT TESTED] XorAssignmentExpression: xor assignment ^="""
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
        """[NOT TESTED] ArithmeticLeftShiftAssignmentExpression: <<<="""
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
        """[NOT TESTED] ArithmeticRightShiftAssignmentExpression: >>>="""
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
        """[NOT TESTED] LogicalLeftShiftAssignmentExpression: <<="""
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
        """[NOT TESTED] LogicalRightShiftAssignmentExpression: >>="""
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
        """[NOT TESTED] MultiplyAssignmentExpression: *="""
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
        """[NOT TESTED] DivideAssignmentExpression: /="""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('BitType')
    def extract_bit_type(self, node) -> SignalResult:
        """[NOT TESTED] BitType: bit type"""
        return SignalResult()
    
    @on('ByteType')
    def extract_byte_type(self, node) -> SignalResult:
        """[NOT TESTED] ByteType: byte type"""
        return SignalResult()
    
    @on('CHandleType')
    def extract_chandle_type(self, node) -> SignalResult:
        """[NOT TESTED] CHandleType: chandle type"""
        return SignalResult()
    
    @on('IntType')
    def extract_int_type(self, node) -> SignalResult:
        """[NOT TESTED] IntType: int type"""
        return SignalResult()
    
    @on('LongIntType')
    def extract_long_int_type(self, node) -> SignalResult:
        """[NOT TESTED] LongIntType: longint type"""
        return SignalResult()
    
    @on('ShortIntType')
    def extract_short_int_type(self, node) -> SignalResult:
        """[NOT TESTED] ShortIntType: shortint type"""
        return SignalResult()
    
    @on('IntegerType')
    def extract_integer_type(self, node) -> SignalResult:
        """[NOT TESTED] IntegerType: integer type"""
        return SignalResult()
    
    @on('LogicType')
    def extract_logic_type(self, node) -> SignalResult:
        """[NOT TESTED] LogicType: logic type"""
        return SignalResult()
    
    @on('RegType')
    def extract_reg_type(self, node) -> SignalResult:
        """[NOT TESTED] RegType: reg type"""
        return SignalResult()
    
    @on('StringType')
    def extract_string_type(self, node) -> SignalResult:
        """[NOT TESTED] StringType: string type"""
        return SignalResult()
    
    @on('EventType')
    def extract_event_type(self, node) -> SignalResult:
        """[NOT TESTED] EventType: event type"""
        return SignalResult()
    
    @on('VoidType')
    def extract_void_type(self, node) -> SignalResult:
        """[NOT TESTED] VoidType: void type"""
        return SignalResult()
    
    @on('RealType')
    def extract_real_type(self, node) -> SignalResult:
        """[NOT TESTED] RealType: real type"""
        return SignalResult()
    
    @on('ShortRealType')
    def extract_short_real_type(self, node) -> SignalResult:
        """[NOT TESTED] ShortRealType: shortreal type"""
        return SignalResult()
    
    @on('PropertyType')
    def extract_property_type(self, node) -> SignalResult:
        """[NOT TESTED] PropertyType: property type"""
        return SignalResult()
    
    @on('SequenceType')
    def extract_sequence_type(self, node) -> SignalResult:
        """[NOT TESTED] SequenceType: sequence type"""
        return SignalResult()
    
    # Statement-related
    @on('AssertPropertyStatement')
    def extract_assert_property_statement(self, node) -> SignalResult:
        """[NOT TESTED] AssertPropertyStatement: assert property statement"""
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
        """[NOT TESTED] AssumePropertyStatement: assume property statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('CoverPropertyStatement')
    def extract_cover_property_statement(self, node) -> SignalResult:
        """[NOT TESTED] CoverPropertyStatement: cover property statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('CoverSequenceStatement')
    def extract_cover_sequence_statement(self, node) -> SignalResult:
        """[NOT TESTED] CoverSequenceStatement: cover sequence statement"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('ExpectPropertyStatement')
    def extract_expect_property_statement(self, node) -> SignalResult:
        """[NOT TESTED] ExpectPropertyStatement: expect property statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, 'action', None)
        if action:
            result = result.merge(self.extract(action))
        return result
    
    # Sequence and property expression kinds
    @on('WithinSequenceExpr')
    def extract_within_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] WithinSequenceExpr: within sequence expression"""
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
        """[NOT TESTED] ThroughoutSequenceExpr: throughout sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        throughout = getattr(node, 'throughout', None) or getattr(node, 'expr2', None)
        if throughout:
            result = result.merge(self.extract(throughout))
        return result
    
    @on('ArrayAndMethod')
    def extract_array_and_method(self, node) -> SignalResult:
        """[NOT TESTED] ArrayAndMethod: array.and() method"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    @on('ArrayOrMethod')
    def extract_array_or_method(self, node) -> SignalResult:
        """[NOT TESTED] ArrayOrMethod: array.or() method"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    @on('ArrayUniqueMethod')
    def extract_array_unique_method(self, node) -> SignalResult:
        """[NOT TESTED] ArrayUniqueMethod: array.unique() method"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    @on('ArrayXorMethod')
    def extract_array_xor_method(self, node) -> SignalResult:
        """[NOT TESTED] ArrayXorMethod: array.xor() method"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        return result
    
    @on('ArrayOrRandomizeMethodExpression')
    def extract_array_randomize_method_expr(self, node) -> SignalResult:
        """[NOT TESTED] ArrayOrRandomizeMethodExpression: array.randomize() with method"""
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
        """[NOT TESTED] BinsSelection: bins selection"""
        result = SignalResult()
        bins = getattr(node, 'bins', None) or getattr(node, 'expr', None)
        if bins:
            result = result.merge(self.extract(bins))
        select = getattr(node, 'select', None) or getattr(node, 'expr2', None)
        if select:
            result = result.merge(self.extract(select))
        return result
    
    @on('BinsSelectConditionExpr')
    def extract_bins_select_condition_expr(self, node) -> SignalResult:
        """[NOT TESTED] BinsSelectConditionExpr: bins select condition expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'cond', None)
        if cond:
            result = result.merge(self.extract(cond))
        return result
    
    @on('BinSelectWithFilterExpr')
    def extract_bin_select_with_filter_expr(self, node) -> SignalResult:
        """[NOT TESTED] BinSelectWithFilterExpr: bin select with filter expression"""
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
        """[NOT TESTED] BitSelect: bit select"""
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
        """[NOT TESTED] AscendingRangeSelect: ascending range select"""
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
        """[NOT TESTED] DescendingRangeSelect: descending range select"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Class expressions
    @on('ConditionalConstraint')
    def extract_conditional_constraint(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalConstraint: conditional constraint"""
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
    
    @on('DistConstraintList')
    def extract_dist_constraint_list(self, node) -> SignalResult:
        """[NOT TESTED] DistConstraintList: dist constraint list"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ConstraintBlock')
    def extract_constraint_block(self, node) -> SignalResult:
        """[NOT TESTED] ConstraintBlock: constraint block"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'constraints', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ConstraintDeclaration')
    def extract_constraint_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ConstraintDeclaration: constraint declaration"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'constraints', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ConstraintPrototype')
    def extract_constraint_prototype(self, node) -> SignalResult:
        """[NOT TESTED] ConstraintPrototype: constraint prototype"""
        return SignalResult()
    
    # Class-related expressions
    @on('ClassDeclaration')
    def extract_class_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ClassDeclaration: class declaration"""
        return SignalResult()
    
    @on('ClassMethodDeclaration')
    def extract_class_method_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ClassMethodDeclaration: class method declaration"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('ClassMethodPrototype')
    def extract_class_method_prototype(self, node) -> SignalResult:
        """[NOT TESTED] ClassMethodPrototype: class method prototype"""
        return SignalResult()
    
    @on('ClassPropertyDeclaration')
    def extract_class_property_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ClassPropertyDeclaration: class property declaration"""
        result = SignalResult()
        init = getattr(node, 'init', None) or getattr(node, 'value', None)
        if init:
            result = result.merge(self.extract(init))
        return result
    
    @on('ClassSpecifier')
    def extract_class_specifier(self, node) -> SignalResult:
        """[NOT TESTED] ClassSpecifier: class specifier"""
        return SignalResult()
    
    @on('ClassName')
    def extract_class_name(self, node) -> SignalResult:
        """[NOT TESTED] ClassName: class name"""
        return SignalResult()
    
    # Checker-related
    @on('CheckerDeclaration')
    def extract_checker_declaration(self, node) -> SignalResult:
        """[NOT TESTED] CheckerDeclaration: checker declaration"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('CheckerInstanceStatement')
    def extract_checker_instance_statement(self, node) -> SignalResult:
        """[NOT TESTED] CheckerInstanceStatement: checker instance statement"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('CheckerInstantiation')
    def extract_checker_instantiation(self, node) -> SignalResult:
        """[NOT TESTED] CheckerInstantiation: checker instantiation"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('CheckerDataDeclaration')
    def extract_checker_data_declaration(self, node) -> SignalResult:
        """[NOT TESTED] CheckerDataDeclaration: checker data declaration"""
        return SignalResult()
    
    # Coverage-related
    @on('CoverageBins')
    def extract_coverage_bins(self, node) -> SignalResult:
        """[NOT TESTED] CoverageBins: coverage bins"""
        result = SignalResult()
        value = getattr(node, 'value', None) or getattr(node, 'expr', None)
        if value:
            result = result.merge(self.extract(value))
        return result
    
    @on('CoverageBinsArraySize')
    def extract_coverage_bins_array_size(self, node) -> SignalResult:
        """[NOT TESTED] CoverageBinsArraySize: coverage bins array size"""
        result = SignalResult()
        size = getattr(node, 'size', None) or getattr(node, 'expr', None)
        if size:
            result = result.merge(self.extract(size))
        return result
    
    @on('DefaultCoverageBinInitializer')
    def extract_default_coverage_bin_initializer(self, node) -> SignalResult:
        """[NOT TESTED] DefaultCoverageBinInitializer: default coverage bin initializer"""
        return SignalResult()
    
    @on('ExpressionCoverageBinInitializer')
    def extract_expression_coverage_bin_initializer(self, node) -> SignalResult:
        """[NOT TESTED] ExpressionCoverageBinInitializer: expression coverage bin initializer"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    # ElabSystemTask
    @on('ElabSystemTask')
    def extract_elab_system_task(self, node) -> SignalResult:
        """[NOT TESTED] ElabSystemTask: elaboration system task"""
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
        """[NOT TESTED] BindDirective: bind directive"""
        result = SignalResult()
        target = getattr(node, 'target', None) or getattr(node, 'expr', None)
        if target:
            result = result.merge(self.extract(target))
        return result
    
    @on('BindTargetList')
    def extract_bind_target_list(self, node) -> SignalResult:
        """[NOT TESTED] BindTargetList: bind target list"""
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
        """[NOT TESTED] DefaultFunctionPort: default function port"""
        return SignalResult()
    
    # Case and generate constructs
    @on('CaseStatement')
    def extract_case_statement_stmt(self, node) -> SignalResult:
        """[NOT TESTED] CaseStatement: case statement"""
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
        """[NOT TESTED] CaseGenerate: case generate construct"""
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
        """[NOT TESTED] DefaultCaseItem: default case item"""
        result = SignalResult()
        stmts = getattr(node, 'statements', None) or getattr(node, 'body', None)
        if stmts and hasattr(stmts, '__iter__'):
            for stmt in stmts:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('DefaultPropertyCaseItem')
    def extract_default_property_case_item(self, node) -> SignalResult:
        """[NOT TESTED] DefaultPropertyCaseItem: default property case item"""
        return SignalResult()
    
    # Assertion item ports
    @on('AssertionItemPort')
    def extract_assertion_item_port(self, node) -> SignalResult:
        """[NOT TESTED] AssertionItemPort: assertion item port"""
        return SignalResult()
    
    @on('AssertionItemPortList')
    def extract_assertion_item_port_list(self, node) -> SignalResult:
        """[NOT TESTED] AssertionItemPortList: assertion item port list"""
        return SignalResult()
    
    @on('ConcurrentAssertionMember')
    def extract_concurrent_assertion_member(self, node) -> SignalResult:
        """[NOT TESTED] ConcurrentAssertionMember: concurrent assertion member"""
        return SignalResult()
    
    # Coverage constructs
    @on('CovergroupDeclaration')
    def extract_covergroup_declaration(self, node) -> SignalResult:
        """[NOT TESTED] CovergroupDeclaration: covergroup declaration"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'coverpoints', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('Coverpoint')
    def extract_coverpoint(self, node) -> SignalResult:
        """[NOT TESTED] Coverpoint: coverpoint"""
        result = SignalResult()
        transition = getattr(node, 'transition', None) or getattr(node, 'expr', None)
        if transition:
            result = result.merge(self.extract(transition))
        return result
    
    @on('CoverCross')
    def extract_cover_cross(self, node) -> SignalResult:
        """[NOT TESTED] CoverCross: cover cross"""
        return SignalResult()
    
    @on('CoverageOption')
    def extract_coverage_option(self, node) -> SignalResult:
        """[NOT TESTED] CoverageOption: coverage option"""
        return SignalResult()
    
    @on('CoverageIffClause')
    def extract_coverage_iff_clause(self, node) -> SignalResult:
        """[NOT TESTED] CoverageIffClause: coverage iff clause"""
        expr = getattr(node, 'expr', None) or getattr(node, 'condition', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('BlockCoverageEvent')
    def extract_block_coverage_event(self, node) -> SignalResult:
        """[NOT TESTED] BlockCoverageEvent: block coverage event"""
        return SignalResult()
    
    # Bad and invalid expressions
    @on('BadExpression')
    def extract_bad_expression(self, node) -> SignalResult:
        """[NOT TESTED] BadExpression: bad expression"""
        return SignalResult()
    
    # Binary block event expression
    @on('BinaryBlockEventExpression')
    def extract_binary_block_event_expression(self, node) -> SignalResult:
        """[NOT TESTED] BinaryBlockEventExpression: binary block event expression"""
        return SignalResult()
    
    @on('BinaryEventExpression')
    def extract_binary_event_expression(self, node) -> SignalResult:
        """[NOT TESTED] BinaryEventExpression: binary event expression"""
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
        """[NOT TESTED] BlockingEventTriggerStatement: blocking event trigger"""
        event = getattr(node, 'event', None) or getattr(node, 'expr', None)
        if event:
            return self.extract(event)
        return SignalResult()
    
    # Default disable declaration
    @on('DefaultDisableDeclaration')
    def extract_default_disable_declaration(self, node) -> SignalResult:
        """[NOT TESTED] DefaultDisableDeclaration: default disable declaration"""
        expr = getattr(node, 'expr', None) or getattr(node, 'disable', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Conditional pattern
    @on('AssignmentPatternItem')
    def extract_assignment_pattern_item(self, node) -> SignalResult:
        """[NOT TESTED] AssignmentPatternItem: assignment pattern item"""
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
        """[NOT TESTED] AnonymousProgram: anonymous program"""
        return SignalResult()
    
    # Extern interface method
    @on('ExternInterfaceMethod')
    def extract_extern_interface_method(self, node) -> SignalResult:
        """[NOT TESTED] ExternInterfaceMethod: extern interface method"""
        return SignalResult()
    
    # More expression types
    @on('ParenthesizedExpression')
    def extract_parenthesized_expression(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedExpression: parenthesized expression"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Conditional directive expressions
    @on('BinaryConditionalDirectiveExpression')
    def extract_binary_conditional_directive_expr(self, node) -> SignalResult:
        """[NOT TESTED] BinaryConditionalDirectiveExpression: binary conditional directive expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('DefaultPatternKeyExpression')
    def extract_default_pattern_key_expression(self, node) -> SignalResult:
        """[NOT TESTED] DefaultPatternKeyExpression: default pattern key expression"""
        return SignalResult()
    
    # Function return type
    @on('ModportDeclaration')
    def extract_modport_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ModportDeclaration: modport declaration"""
        return SignalResult()
    
    @on('ModportItem')
    def extract_modport_item(self, node) -> SignalResult:
        """[NOT TESTED] ModportItem: modport item"""
        result = SignalResult()
        signal = getattr(node, 'signal', None) or getattr(node, 'expr', None)
        if signal:
            result = result.merge(self.extract(signal))
        return result
    
    @on('FunctionDeclaration')
    def extract_function_declaration(self, node) -> SignalResult:
        """[NOT TESTED] FunctionDeclaration: function declaration"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('TaskDeclaration')
    def extract_task_declaration(self, node) -> SignalResult:
        """[NOT TESTED] TaskDeclaration: task declaration"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('FunctionPrototype')
    def extract_function_prototype(self, node) -> SignalResult:
        """[NOT TESTED] FunctionPrototype: function prototype"""
        return SignalResult()
    
    @on('PackageDeclaration')
    def extract_package_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PackageDeclaration: package declaration"""
        return SignalResult()
    
    @on('ModuleDeclaration')
    def extract_module_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ModuleDeclaration: module declaration"""
        return SignalResult()
    
    @on('InterfaceDeclaration')
    def extract_interface_declaration(self, node) -> SignalResult:
        """[NOT TESTED] InterfaceDeclaration: interface declaration"""
        return SignalResult()
    
    @on('ProgramDeclaration')
    def extract_program_declaration_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ProgramDeclaration: program declaration"""
        return SignalResult()
    
    # Generate constructs
    @on('IfGenerate')
    def extract_if_generate(self, node) -> SignalResult:
        """[NOT TESTED] IfGenerate: if generate construct"""
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
        """[NOT TESTED] LoopGenerate: loop generate construct"""
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
        """[NOT TESTED] GenerateBlock: generate block"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('GenerateRegion')
    def extract_generate_region(self, node) -> SignalResult:
        """[NOT TESTED] GenerateRegion: generate region"""
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
        """[NOT TESTED] ContinuousAssign: continuous assignment"""
        result = SignalResult()
        lvalue = getattr(node, 'lvalue', None)
        if lvalue:
            result = result.merge(self.extract(lvalue))
        rvalue = getattr(node, 'rvalue', None) or getattr(node, 'expr', None)
        if rvalue:
            result = result.merge(self.extract(rvalue))
        return result
    
    @on('PortDeclaration')
    def extract_port_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PortDeclaration: port declaration"""
        result = SignalResult()
        init = getattr(node, 'init', None) or getattr(node, 'value', None)
        if init:
            result = result.merge(self.extract(init))
        return result
    
    @on('ForLoopStatement')
    def extract_for_loop_statement(self, node) -> SignalResult:
        """[NOT TESTED] ForLoopStatement: for loop statement"""
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
        """[NOT TESTED] ForeachLoopStatement: foreach loop statement"""
        result = SignalResult()
        array = getattr(node, 'array', None) or getattr(node, 'expr', None)
        if array:
            result = result.merge(self.extract(array))
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('ReturnStatement')
    def extract_return_statement(self, node) -> SignalResult:
        """[NOT TESTED] ReturnStatement: return statement"""
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('DisableStatement')
    def extract_disable_statement(self, node) -> SignalResult:
        """[NOT TESTED] DisableStatement: disable statement"""
        return SignalResult()
    
    # Wait statements
    @on('WaitStatement')
    def extract_wait_statement_stmt(self, node) -> SignalResult:
        """[NOT TESTED] WaitStatement: wait statement"""
        cond = getattr(node, 'cond', None) or getattr(node, 'expression', None)
        if cond:
            return self.extract(cond)
        return SignalResult()
    
    @on('ParameterDeclaration')
    def extract_parameter_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ParameterDeclaration: parameter declaration"""
        return SignalResult()
    
    # Non-blocking assignment statement
    @on('RandSequenceStatement')
    def extract_rand_sequence_statement(self, node) -> SignalResult:
        """[NOT TESTED] RandSequenceStatement: rand sequence statement"""
        return SignalResult()
    
    # Immediate assertion statements
    @on('ImmediateAssertStatement')
    def extract_immediate_assert_statement(self, node) -> SignalResult:
        """[NOT TESTED] ImmediateAssertStatement: immediate assert statement"""
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
        """[NOT TESTED] ImmediateAssumeStatement: immediate assume statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('ImmediateCoverStatement')
    def extract_immediate_cover_statement(self, node) -> SignalResult:
        """[NOT TESTED] ImmediateCoverStatement: immediate cover statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    # Deferred assertion statements
    @on('DistWeight')
    def extract_dist_weight(self, node) -> SignalResult:
        """[NOT TESTED] DistWeight: dist weight"""
        result = SignalResult()
        weight = getattr(node, 'weight', None) or getattr(node, 'expr', None)
        if weight:
            result = result.merge(self.extract(weight))
        value = getattr(node, 'value', None) or getattr(node, 'expr2', None)
        if value:
            result = result.merge(self.extract(value))
        return result
    
    # Let expression
    @on('ModExpression')
    def extract_mod_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ModExpression: mod expression %"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LoopStatement')
    def extract_loop_statement(self, node) -> SignalResult:
        """[NOT TESTED] LoopStatement: loop statement (for, while, do-while, repeat, foreach)"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        vars_ = getattr(node, 'variables', None) or getattr(node, 'declarations', None)
        if vars_ and hasattr(vars_, '__iter__'):
            for v in vars_:
                if v:
                    result = result.merge(self.extract(v))
        return result
    
    @on('ForVariableDeclaration')
    def extract_for_variable_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ForVariableDeclaration: for loop variable declaration"""
        result = SignalResult()
        var = getattr(node, 'variable', None) or getattr(node, 'var', None)
        if var:
            result = result.merge(self.extract(var))
        init = getattr(node, 'init', None) or getattr(node, 'expr', None)
        if init:
            result = result.merge(self.extract(init))
        return result
    
    @on('DoWhileStatement')
    def extract_do_while_statement(self, node) -> SignalResult:
        """[NOT TESTED] DoWhileStatement: do-while statement"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        cond = getattr(node, 'condition', None) or getattr(node, 'expr', None)
        if cond:
            result = result.merge(self.extract(cond))
        return result
    
    @on('ForeverStatement')
    def extract_forever_statement(self, node) -> SignalResult:
        """[NOT TESTED] ForeverStatement: forever statement"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('LoopConstraint')
    def extract_loop_constraint_stmt(self, node) -> SignalResult:
        """[NOT TESTED] LoopConstraint: loop constraint"""
        result = SignalResult()
        vars_ = getattr(node, 'variables', None) or getattr(node, 'loop_vars', None)
        if vars_ and hasattr(vars_, '__iter__'):
            for v in vars_:
                if v:
                    result = result.merge(self.extract(v))
        constraint = getattr(node, 'constraint', None) or getattr(node, 'body', None)
        if constraint:
            result = result.merge(self.extract(constraint))
        return result
    
    # Jump statements
    @on('JumpStatement')
    def extract_jump_statement(self, node) -> SignalResult:
        """[NOT TESTED] JumpStatement: break, continue, return, disable statements"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'value', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    # Return statement
    @on('DisableForkStatement')
    def extract_disable_fork_statement(self, node) -> SignalResult:
        """[NOT TESTED] DisableForkStatement: disable fork statement"""
        return SignalResult()
    
    # Wait statement
    @on('ProceduralReleaseStatement')
    def extract_procedural_release_statement(self, node) -> SignalResult:
        """[NOT TESTED] ProceduralReleaseStatement: procedural release statement"""
        return SignalResult()
    
    # Event trigger statements
    @on('NonblockingEventTriggerStatement')
    def extract_nonblocking_event_trigger_statement(self, node) -> SignalResult:
        """[NOT TESTED] NonblockingEventTriggerStatement: nonblocking event trigger ->>"""
        return SignalResult()
    
    # Property expressions
    @on('ConditionalPropertyExpr')
    def extract_conditional_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalPropertyExpr: conditional property expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'expr', None)
        if cond:
            result = result.merge(self.extract(cond))
        prop = getattr(node, 'property', None) or getattr(node, 'true_body', None)
        if prop:
            result = result.merge(self.extract(prop))
        else_body = getattr(node, 'else_body', None) or getattr(node, 'false_body', None)
        if else_body:
            result = result.merge(self.extract(else_body))
        return result
    
    @on('SimplePropertyExpr')
    def extract_simple_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] SimplePropertyExpr: simple property expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            return self.extract(prop)
        return result
    
    @on('SimpleSequenceExpr')
    def extract_simple_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] SimpleSequenceExpr: simple sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            return self.extract(seq)
        return result
    
    @on('IffPropertyExpr')
    def extract_iff_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] IffPropertyExpr: property iff expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        iff = getattr(node, 'iff', None) or getattr(node, 'event', None)
        if iff:
            result = result.merge(self.extract(iff))
        return result
    
    @on('ImpliesPropertyExpr')
    def extract_implies_property_expr_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ImpliesPropertyExpr: implies property expression"""
        result = SignalResult()
        left = getattr(node, 'left', None) or getattr(node, 'antecedent', None)
        right = getattr(node, 'right', None) or getattr(node, 'consequent', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('FollowedByPropertyExpr')
    def extract_followed_by_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] FollowedByPropertyExpr: followed_by property expression"""
        result = SignalResult()
        left = getattr(node, 'left', None) or getattr(node, 'antecedent', None)
        right = getattr(node, 'right', None) or getattr(node, 'consequent', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SUntilPropertyExpr')
    def extract_s_until_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] SUntilPropertyExpr: s_until property expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('SUntilWithPropertyExpr')
    def extract_s_until_with_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] SUntilWithPropertyExpr: s_until_with property expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('UntilPropertyExpr')
    def extract_until_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] UntilPropertyExpr: until property expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('UntilWithPropertyExpr')
    def extract_until_with_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] UntilWithPropertyExpr: until_with property expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('StrongWeakPropertyExpr')
    def extract_strong_weak_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] StrongWeakPropertyExpr: strong/weak property expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('AcceptOnPropertyExpr')
    def extract_accept_on_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] AcceptOnPropertyExpr: accept_on property expression"""
        result = SignalResult()
        cond = getattr(node, 'condition', None) or getattr(node, 'expr', None)
        if cond:
            result = result.merge(self.extract(cond))
        prop = getattr(node, 'property', None) or getattr(node, 'body', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    # Sequence expressions
    @on('DelayedSequenceExpr')
    def extract_delayed_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] DelayedSequenceExpr: delayed sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            result = result.merge(self.extract(seq))
        return result
    
    @on('DelayedSequenceElement')
    def extract_delayed_sequence_element(self, node) -> SignalResult:
        """[NOT TESTED] DelayedSequenceElement: delayed sequence element"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('SequenceMatchList')
    def extract_sequence_match_list(self, node) -> SignalResult:
        """[NOT TESTED] SequenceMatchList: sequence match list"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('IntersectSequenceExpr')
    def extract_intersect_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] IntersectSequenceExpr: intersect sequence expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('ParenthesizedSequenceExpr')
    def extract_parenthesized_sequence_expr(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedSequenceExpr: parenthesized sequence expression"""
        result = SignalResult()
        seq = getattr(node, 'sequence', None) or getattr(node, 'expr', None)
        if seq:
            return self.extract(seq)
        return result
    
    @on('ParenthesizedPropertyExpr')
    def extract_parenthesized_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedPropertyExpr: parenthesized property expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            return self.extract(prop)
        return result
    
    @on('UnarySelectPropertyExpr')
    def extract_unary_select_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] UnarySelectPropertyExpr: unary select property expression"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('PropertyDeclaration')
    def extract_property_declaration_stmt(self, node) -> SignalResult:
        """[NOT TESTED] PropertyDeclaration: property declaration"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'body', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('SequenceDeclaration')
    def extract_sequence_declaration_stmt(self, node) -> SignalResult:
        """[NOT TESTED] SequenceDeclaration: sequence declaration"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'body', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('RestrictPropertyStatement')
    def extract_restrict_property_statement(self, node) -> SignalResult:
        """[NOT TESTED] RestrictPropertyStatement: restrict property statement"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    # Invocations and calls
    @on('InvocationExpression')
    def extract_invocation_expression(self, node) -> SignalResult:
        """[NOT TESTED] InvocationExpression: invocation expression"""
        result = SignalResult()
        args = getattr(node, 'arguments', None)
        if args and hasattr(args, '__iter__'):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result
    
    @on('VoidCastedCallStatement')
    def extract_void_casted_call_statement(self, node) -> SignalResult:
        """[NOT TESTED] VoidCastedCallStatement: void casted call statement"""
        result = SignalResult()
        call = getattr(node, 'call', None) or getattr(node, 'expr', None)
        if call:
            result = result.merge(self.extract(call))
        return result
    
    # Declaration-related expressions
    @on('DataDeclaration')
    def extract_data_declaration(self, node) -> SignalResult:
        """[NOT TESTED] DataDeclaration: data declaration (variables, nets)"""
        result = SignalResult()
        items = getattr(node, 'declarators', None) or getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('NetDeclaration')
    def extract_net_declaration(self, node) -> SignalResult:
        """[NOT TESTED] NetDeclaration: net declaration"""
        result = SignalResult()
        items = getattr(node, 'declarators', None) or getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('TypedefDeclaration')
    def extract_typedef_declaration_stmt(self, node) -> SignalResult:
        """[NOT TESTED] TypedefDeclaration: typedef declaration"""
        return SignalResult()

    @on('IdentifierName')
    def extract_identifier_name(self, node) -> SignalResult:
        """[MIGRATED] IdentifierName: 简单信号名
        
        从 visit_identifier_name 迁移而来
        """
        ident = getattr(node, 'identifier', None)
        if ident is None:
            logger.debug(f"[MIGRATED] IdentifierName missing 'identifier' attr")
            return SignalResult()
        
        val = getattr(ident, 'value', None)
        if val is None:
            logger.debug(f"[MIGRATED] IdentifierName.identifier missing 'value' attr")
            return SignalResult()
        
        signal_name = self.adapter.clean_name(str(val).strip())
        return SignalResult(primary=signal_name)

    
    @on('ForwardTypedefDeclaration')
    def extract_forward_typedef_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ForwardTypedefDeclaration: forward typedef declaration"""
        return SignalResult()
    
    @on('ParameterDeclarationStatement')
    def extract_parameter_declaration_statement(self, node) -> SignalResult:
        """[NOT TESTED] ParameterDeclarationStatement: parameter declaration statement"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'parameters', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('TypeParameterDeclaration')
    def extract_type_parameter_declaration(self, node) -> SignalResult:
        """[NOT TESTED] TypeParameterDeclaration: type parameter declaration"""
        return SignalResult()
    
    @on('FunctionPort')
    def extract_function_port(self, node) -> SignalResult:
        """[NOT TESTED] FunctionPort: function port"""
        result = SignalResult()
        var = getattr(node, 'variable', None) or getattr(node, 'var', None)
        if var:
            result = result.merge(self.extract(var))
        return result
    
    @on('FunctionPortList')
    def extract_function_port_list(self, node) -> SignalResult:
        """[NOT TESTED] FunctionPortList: function port list"""
        result = SignalResult()
        ports = getattr(node, 'ports', None)
        if ports and hasattr(ports, '__iter__'):
            for port in ports:
                if port:
                    result = result.merge(self.extract(port))
        return result
    
    @on('LocalVariableDeclaration')
    def extract_local_variable_declaration(self, node) -> SignalResult:
        """[NOT TESTED] LocalVariableDeclaration: local variable declaration"""
        result = SignalResult()
        var = getattr(node, 'variable', None) or getattr(node, 'var', None)
        if var:
            result = result.merge(self.extract(var))
        return result
    
    @on('GenvarDeclaration')
    def extract_genvar_declaration(self, node) -> SignalResult:
        """[NOT TESTED] GenvarDeclaration: genvar declaration"""
        return SignalResult()
    
    @on('NetTypeDeclaration')
    def extract_net_type_declaration(self, node) -> SignalResult:
        """[NOT TESTED] NetTypeDeclaration: net type declaration"""
        return SignalResult()
    
    @on('PackageImportDeclaration')
    def extract_package_import_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PackageImportDeclaration: package import declaration"""
        return SignalResult()
    
    @on('PackageImportItem')
    def extract_package_import_item(self, node) -> SignalResult:
        """[NOT TESTED] PackageImportItem: package import item"""
        return SignalResult()
    
    @on('PackageExportDeclaration')
    def extract_package_export_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PackageExportDeclaration: package export declaration"""
        return SignalResult()
    
    @on('PackageExportAllDeclaration')
    def extract_package_export_all_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PackageExportAllDeclaration: package export all declaration"""
        return SignalResult()
    
    # Clocking block declarations
    @on('ClockingDeclaration')
    def extract_clocking_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ClockingDeclaration: clocking block declaration"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ClockingDirection')
    def extract_clocking_direction(self, node) -> SignalResult:
        """[NOT TESTED] ClockingDirection: clocking direction"""
        return SignalResult()
    
    @on('ClockingItem')
    def extract_clocking_item(self, node) -> SignalResult:
        """[NOT TESTED] ClockingItem: clocking item"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'body', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ClockingSkew')
    def extract_clocking_skew(self, node) -> SignalResult:
        """[NOT TESTED] ClockingSkew: clocking skew"""
        return SignalResult()
    
    @on('DefaultClockingReference')
    def extract_default_clocking_reference(self, node) -> SignalResult:
        """[NOT TESTED] DefaultClockingReference: default clocking reference"""
        return SignalResult()
    
    @on('TimeUnitsDeclaration')
    def extract_time_units_declaration(self, node) -> SignalResult:
        """[NOT TESTED] TimeUnitsDeclaration: time units declaration"""
        return SignalResult()
    
    # Modport declarations
    @on('ModportSimplePortList')
    def extract_modport_simple_port_list(self, node) -> SignalResult:
        """[NOT TESTED] ModportSimplePortList: modport simple port list"""
        result = SignalResult()
        ports = getattr(node, 'ports', None)
        if ports and hasattr(ports, '__iter__'):
            for port in ports:
                if port:
                    result = result.merge(self.extract(port))
        return result
    
    @on('ModportSubroutinePortList')
    def extract_modport_subroutine_port_list(self, node) -> SignalResult:
        """[NOT TESTED] ModportSubroutinePortList: modport subroutine port list"""
        result = SignalResult()
        ports = getattr(node, 'ports', None)
        if ports and hasattr(ports, '__iter__'):
            for port in ports:
                if port:
                    result = result.merge(self.extract(port))
        return result
    
    @on('ModportClockingPort')
    def extract_modport_clocking_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportClockingPort: modport clocking port"""
        return SignalResult()
    
    @on('ModportExplicitPort')
    def extract_modport_explicit_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportExplicitPort: modport explicit port"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'signal', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ModportNamedPort')
    def extract_modport_named_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportNamedPort: modport named port"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'signal', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    # Interface port header
    @on('InterfacePortHeader')
    def extract_interface_port_header(self, node) -> SignalResult:
        """[NOT TESTED] InterfacePortHeader: interface port header"""
        return SignalResult()
    
    @on('InterfaceHeader')
    def extract_interface_header_stmt(self, node) -> SignalResult:
        """[NOT TESTED] InterfaceHeader: interface header"""
        return SignalResult()
    
    @on('ModuleHeader')
    def extract_module_header(self, node) -> SignalResult:
        """[NOT TESTED] ModuleHeader: module header"""
        result = SignalResult()
        params = getattr(node, 'parameters', None)
        if params and hasattr(params, '__iter__'):
            for p in params:
                if p:
                    result = result.merge(self.extract(p))
        return result
    
    @on('PackageHeader')
    def extract_package_header(self, node) -> SignalResult:
        """[NOT TESTED] PackageHeader: package header"""
        return SignalResult()
    
    @on('ProgramHeader')
    def extract_program_header(self, node) -> SignalResult:
        """[NOT TESTED] ProgramHeader: program header"""
        return SignalResult()
    
    # Block statements
    @on('AlwaysBlock')
    def extract_always_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysBlock: always block"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('AlwaysCombBlock')
    def extract_always_comb_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysCombBlock: always_comb block"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('AlwaysFFBlock')
    def extract_always_ff_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysFFBlock: always_ff block"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('AlwaysLatchBlock')
    def extract_always_latch_block(self, node) -> SignalResult:
        """[NOT TESTED] AlwaysLatchBlock: always_latch block"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('InitialBlock')
    def extract_initial_block(self, node) -> SignalResult:
        """[NOT TESTED] InitialBlock: initial block"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('FinalBlock')
    def extract_final_block(self, node) -> SignalResult:
        """[NOT TESTED] FinalBlock: final block"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('SequentialBlockStatement')
    def extract_sequential_block_statement(self, node) -> SignalResult:
        """[NOT TESTED] SequentialBlockStatement: sequential block statement"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('ParallelBlockStatement')
    def extract_parallel_block_statement(self, node) -> SignalResult:
        """[NOT TESTED] ParallelBlockStatement: parallel block statement"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statements', None)
        if body and hasattr(body, '__iter__'):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result
    
    @on('ActionBlock')
    def extract_action_block(self, node) -> SignalResult:
        """[NOT TESTED] ActionBlock: action block"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('RsCodeBlock')
    def extract_rs_code_block(self, node) -> SignalResult:
        """[NOT TESTED] RsCodeBlock: randsequence code block"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('RsCase')
    def extract_rs_case(self, node) -> SignalResult:
        """[NOT TESTED] RsCase: randsequence case"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('RsElseClause')
    def extract_rs_else_clause(self, node) -> SignalResult:
        """[NOT TESTED] RsElseClause: randsequence else clause"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'block', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('RsWeightClause')
    def extract_rs_weight_clause(self, node) -> SignalResult:
        """[NOT TESTED] RsWeightClause: randsequence weight clause"""
        return SignalResult()
    
    # Expression patterns
    @on('ExpressionPattern')
    def extract_expression_pattern(self, node) -> SignalResult:
        """[NOT TESTED] ExpressionPattern: expression pattern"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'pattern', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('PatternCaseItem')
    def extract_pattern_case_item(self, node) -> SignalResult:
        """[NOT TESTED] PatternCaseItem: pattern case item"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'patterns', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Streaming expressions
    @on('StreamingConcatenationExpression')
    def extract_streaming_concatenation_expression(self, node) -> SignalResult:
        """[NOT TESTED] StreamingConcatenationExpression: streaming concatenation expression"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'streams', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('StreamExpressionWithRange')
    def extract_stream_expression_with_range(self, node) -> SignalResult:
        """[NOT TESTED] StreamExpressionWithRange: stream expression with range"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'expr', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Expression with clauses
    @on('ExpressionOrDist')
    def extract_expression_or_dist(self, node) -> SignalResult:
        """[NOT TESTED] ExpressionOrDist: expression or dist expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        dist = getattr(node, 'dist', None)
        if dist:
            result = result.merge(self.extract(dist))
        return result
    
    @on('WithClause')
    def extract_with_clause(self, node) -> SignalResult:
        """[NOT TESTED] WithClause: with clause"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'function', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('WithFunctionClause')
    def extract_with_function_clause(self, node) -> SignalResult:
        """[NOT TESTED] WithFunctionClause: with function clause"""
        result = SignalResult()
        func = getattr(node, 'function', None) or getattr(node, 'expr', None)
        if func:
            result = result.merge(self.extract(func))
        return result
    
    @on('WithFunctionSample')
    def extract_with_function_sample(self, node) -> SignalResult:
        """[NOT TESTED] WithFunctionSample: with function sample"""
        return SignalResult()
    
    # Queue and literal expressions
    @on('EmptyQueueExpression')
    def extract_empty_queue_expression(self, node) -> SignalResult:
        """[NOT TESTED] EmptyQueueExpression: empty queue expression {}"""
        return SignalResult()
    
    @on('WildcardLiteralExpression')
    def extract_wildcard_literal_expression(self, node) -> SignalResult:
        """[NOT TESTED] WildcardLiteralExpression: wildcard literal expression"""
        return SignalResult()
    
    @on('NullLiteralExpression')
    def extract_null_literal_expression(self, node) -> SignalResult:
        """[NOT TESTED] NullLiteralExpression: null literal expression"""
        return SignalResult()
    
    @on('StringLiteralExpression')
    def extract_string_literal_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] StringLiteralExpression: string literal expression"""
        return SignalResult()
    
    @on('TimeLiteralExpression')
    def extract_time_literal_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] TimeLiteralExpression: time literal expression"""
        return SignalResult()
    
    @on('RealLiteralExpression')
    def extract_real_literal_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] RealLiteralExpression: real literal expression"""
        return SignalResult()
    
    @on('IntegerLiteralExpression')
    def extract_integer_literal_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] IntegerLiteralExpression: integer literal expression"""
        return SignalResult()
    
    @on('UnbasedUnsizedLiteralExpression')
    def extract_unbased_unsized_literal_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] UnbasedUnsizedLiteralExpression: unbased unsized literal expression"""
        return SignalResult()
    
    # Signed cast expression
    @on('SignedCastExpression')
    def extract_signed_cast_expression(self, node) -> SignalResult:
        """[NOT TESTED] SignedCastExpression: signed cast expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    # Unary operators
    @on('UnaryPlusExpression')
    def extract_unary_plus_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] UnaryPlusExpression: unary plus expression +"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryMinusExpression')
    def extract_unary_minus_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] UnaryMinusExpression: unary minus expression -"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryBitwiseNotExpression')
    def extract_unary_bitwise_not_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseNotExpression: unary bitwise not expression ~"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryLogicalNotExpression')
    def extract_unary_logical_not_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryLogicalNotExpression: unary logical not expression !"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryBitwiseAndExpression')
    def extract_unary_bitwise_and_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseAndExpression: unary bitwise and expression &"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryBitwiseOrExpression')
    def extract_unary_bitwise_or_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseOrExpression: unary bitwise or expression |"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryBitwiseXorExpression')
    def extract_unary_bitwise_xor_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseXorExpression: unary bitwise xor expression ^"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryBitwiseNandExpression')
    def extract_unary_bitwise_nand_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseNandExpression: unary bitwise nand expression ~&"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryBitwiseNorExpression')
    def extract_unary_bitwise_nor_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseNorExpression: unary bitwise nor expression ~|"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryBitwiseXnorExpression')
    def extract_unary_bitwise_xnor_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryBitwiseXnorExpression: unary bitwise xnor expression ^~"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryPreincrementExpression')
    def extract_unary_preincrement_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryPreincrementExpression: pre-increment expression ++expr"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('UnaryPredecrementExpression')
    def extract_unary_predecrement_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryPredecrementExpression: pre-decrement expression --expr"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PostincrementExpression')
    def extract_postincrement_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] PostincrementExpression: post-increment expression expr++"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    @on('PostdecrementExpression')
    def extract_postdecrement_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] PostdecrementExpression: post-decrement expression expr--"""
        expr = getattr(node, 'expr', None) or getattr(node, 'operand', None)
        if expr:
            return self.extract(expr)
        return SignalResult()
    
    # Comparison expressions (missing)
    @on('LessThanEqualExpression')
    def extract_less_than_equal_expression(self, node) -> SignalResult:
        """[NOT TESTED] LessThanEqualExpression: <= expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('GreaterThanEqualExpression')
    def extract_greater_than_equal_expression(self, node) -> SignalResult:
        """[NOT TESTED] GreaterThanEqualExpression: >= expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Logical expressions
    @on('LogicalAndExpression')
    def extract_logical_and_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] LogicalAndExpression: && expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LogicalOrExpression')
    def extract_logical_or_expression_stmt(self, node) -> SignalResult:
        """[NOT TESTED] LogicalOrExpression: || expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LogicalEquivalenceExpression')
    def extract_logical_equivalence_expression(self, node) -> SignalResult:
        """[NOT TESTED] LogicalEquivalenceExpression: <-> expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LogicalImplicationExpression')
    def extract_logical_implication_expression(self, node) -> SignalResult:
        """[NOT TESTED] LogicalImplicationExpression: -> expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Logical shift expressions
    @on('LogicalShiftLeftExpression')
    def extract_logical_shift_left_expression(self, node) -> SignalResult:
        """[NOT TESTED] LogicalShiftLeftExpression: << expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LogicalShiftRightExpression')
    def extract_logical_shift_right_expression(self, node) -> SignalResult:
        """[NOT TESTED] LogicalShiftRightExpression: >> expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Pragma expressions
    @on('SimplePragmaExpression')
    def extract_simple_pragma_expression(self, node) -> SignalResult:
        """[NOT TESTED] SimplePragmaExpression: simple pragma expression"""
        return SignalResult()
    
    @on('NumberPragmaExpression')
    def extract_number_pragma_expression(self, node) -> SignalResult:
        """[NOT TESTED] NumberPragmaExpression: number pragma expression"""
        return SignalResult()
    
    @on('NameValuePragmaExpression')
    def extract_name_value_pragma_expression(self, node) -> SignalResult:
        """[NOT TESTED] NameValuePragmaExpression: name value pragma expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'value', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ParenPragmaExpression')
    def extract_paren_pragma_expression(self, node) -> SignalResult:
        """[NOT TESTED] ParenPragmaExpression: parenthesized pragma expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    # Paren expression list
    @on('ParenExpressionList')
    def extract_paren_expression_list(self, node) -> SignalResult:
        """[NOT TESTED] ParenExpressionList: parenthesized expression list"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Event control expressions
    @on('EventControlWithExpression')
    def extract_event_control_with_expression(self, node) -> SignalResult:
        """[NOT TESTED] EventControlWithExpression: event control with expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'condition', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('RepeatedEventControl')
    def extract_repeated_event_control(self, node) -> SignalResult:
        """[NOT TESTED] RepeatedEventControl: repeated event control"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'events', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('SignalEventExpression')
    def extract_signal_event_expression(self, node) -> SignalResult:
        """[NOT TESTED] SignalEventExpression: signal event expression"""
        result = SignalResult()
        signal = getattr(node, 'signal', None) or getattr(node, 'expr', None)
        if signal:
            result = result.merge(self.extract(signal))
        return result
    
    @on('PrimaryBlockEventExpression')
    def extract_primary_block_event_expression(self, node) -> SignalResult:
        """[NOT TESTED] PrimaryBlockEventExpression: primary block event expression"""
        return SignalResult()
    
    # Case items
    @on('StandardCaseItem')
    def extract_standard_case_item(self, node) -> SignalResult:
        """[NOT TESTED] StandardCaseItem: standard case item"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('StandardPropertyCaseItem')
    def extract_standard_property_case_item(self, node) -> SignalResult:
        """[NOT TESTED] StandardPropertyCaseItem: standard property case item"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('DefaultRsCaseItem')
    def extract_default_rs_case_item(self, node) -> SignalResult:
        """[NOT TESTED] DefaultRsCaseItem: default randsequence case item"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'block', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('StandardRsCaseItem')
    def extract_standard_rs_case_item(self, node) -> SignalResult:
        """[NOT TESTED] StandardRsCaseItem: standard randsequence case item"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    # Clause expressions
    @on('IntersectClause')
    def extract_intersect_clause(self, node) -> SignalResult:
        """[NOT TESTED] IntersectClause: intersect clause"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('EqualsTypeClause')
    def extract_equals_type_clause(self, node) -> SignalResult:
        """[NOT TESTED] EqualsTypeClause: equals type clause"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'type', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('EqualsValueClause')
    def extract_equals_value_clause(self, node) -> SignalResult:
        """[NOT TESTED] EqualsValueClause: equals value clause"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'value', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    # More clauses and expressions
    @on('ElseClause')
    def extract_else_clause(self, node) -> SignalResult:
        """[NOT TESTED] ElseClause: else clause"""
        result = SignalResult()
        body = getattr(node, 'body', None) or getattr(node, 'statement', None)
        if body:
            result = result.merge(self.extract(body))
        return result
    
    @on('ElseConstraintClause')
    def extract_else_constraint_clause(self, node) -> SignalResult:
        """[NOT TESTED] ElseConstraintClause: else constraint clause"""
        result = SignalResult()
        constraint = getattr(node, 'constraint', None) or getattr(node, 'body', None)
        if constraint:
            result = result.merge(self.extract(constraint))
        return result
    
    @on('ElsePropertyClause')
    def extract_else_property_clause(self, node) -> SignalResult:
        """[NOT TESTED] ElsePropertyClause: else property clause"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'body', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('ImplementsClause')
    def extract_implements_clause(self, node) -> SignalResult:
        """[NOT TESTED] ImplementsClause: implements clause"""
        return SignalResult()
    
    @on('ExtendsClause')
    def extract_extends_clause(self, node) -> SignalResult:
        """[NOT TESTED] ExtendsClause: extends clause"""
        return SignalResult()
    
    @on('IfNonePathDeclaration')
    def extract_if_none_path_declaration(self, node) -> SignalResult:
        """[NOT TESTED] IfNonePathDeclaration: ifnone path declaration"""
        return SignalResult()
    
    @on('ConditionalPathDeclaration')
    def extract_conditional_path_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalPathDeclaration: conditional path declaration"""
        return SignalResult()
    
    @on('PathDeclaration')
    def extract_path_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PathDeclaration: path declaration"""
        return SignalResult()
    
    @on('PulseStyleDeclaration')
    def extract_pulse_style_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PulseStyleDeclaration: pulse style declaration"""
        return SignalResult()
    
    @on('SimpleBinsSelectExpr')
    def extract_simple_bins_select_expr(self, node) -> SignalResult:
        """[NOT TESTED] SimpleBinsSelectExpr: simple bins select expression"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ParenthesizedBinsSelectExpr')
    def extract_parenthesized_bins_select_expr(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedBinsSelectExpr: parenthesized bins select expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'bins', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('MatchesClause')
    def extract_matches_clause(self, node) -> SignalResult:
        """[NOT TESTED] MatchesClause: matches clause"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('ColonExpressionClause')
    def extract_colon_expression_clause(self, node) -> SignalResult:
        """[NOT TESTED] ColonExpressionClause: colon expression clause"""
        result = SignalResult()
        expr = getattr(node, 'expr', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('DotMemberClause')
    def extract_dot_member_clause(self, node) -> SignalResult:
        """[NOT TESTED] DotMemberClause: dot member clause"""
        return SignalResult()
    
    @on('EqualsAssertionArgClause')
    def extract_equals_assertion_arg_clause(self, node) -> SignalResult:
        """[NOT TESTED] EqualsAssertionArgClause: equals assertion arg clause"""
        return SignalResult()
    
    @on('IffEventClause')
    def extract_iff_event_clause(self, node) -> SignalResult:
        """[NOT TESTED] IffEventClause: iff event clause"""
        return SignalResult()
    
    @on('NamedBlockClause')
    def extract_named_block_clause(self, node) -> SignalResult:
        """[NOT TESTED] NamedBlockClause: named block clause"""
        return SignalResult()
    
    @on('DividerClause')
    def extract_divider_clause(self, node) -> SignalResult:
        """[NOT TESTED] DividerClause: divider clause"""
        return SignalResult()
    
    @on('RandJoinClause')
    def extract_rand_join_clause(self, node) -> SignalResult:
        """[NOT TESTED] RandJoinClause: rand join clause"""
        return SignalResult()
    
    @on('DefaultExtendsClauseArg')
    def extract_default_extends_clause_arg(self, node) -> SignalResult:
        """[NOT TESTED] DefaultExtendsClauseArg: default extends clause arg"""
        return SignalResult()
    
    @on('TimingCheckEventArg')
    def extract_timing_check_event_arg(self, node) -> SignalResult:
        """[NOT TESTED] TimingCheckEventArg: timing check event arg"""
        return SignalResult()
    
    @on('TimingCheckEventCondition')
    def extract_timing_check_event_condition(self, node) -> SignalResult:
        """[NOT TESTED] TimingCheckEventCondition: timing check event condition"""
        return SignalResult()
    
    @on('ExpressionTimingCheckArg')
    def extract_expression_timing_check_arg(self, node) -> SignalResult:
        """[NOT TESTED] ExpressionTimingCheckArg: expression timing check arg"""
        result = SignalResult()
        expr = getattr(node, 'expr', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ModAssignmentExpression')
    def extract_mod_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] ModAssignmentExpression: mod assignment expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('NonblockingAssignmentExpression')
    def extract_nonblocking_assignment_expression(self, node) -> SignalResult:
        """[NOT TESTED] NonblockingAssignmentExpression: nonblocking assignment expression"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    # Last 21 missing handlers
    @on('ConfigDeclaration')
    def extract_config_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ConfigDeclaration: config declaration"""
        return SignalResult()
    
    @on('ConfigUseClause')
    def extract_config_use_clause(self, node) -> SignalResult:
        """[NOT TESTED] ConfigUseClause: config use clause"""
        return SignalResult()
    
    @on('ExternModuleDecl')
    def extract_extern_module_decl(self, node) -> SignalResult:
        """[NOT TESTED] ExternModuleDecl: extern module declaration"""
        return SignalResult()
    
    @on('IdWithExprCoverageBinInitializer')
    def extract_id_with_expr_coverage_bin_initializer(self, node) -> SignalResult:
        """[NOT TESTED] IdWithExprCoverageBinInitializer: id with expr coverage bin initializer"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ImplicationConstraint')
    def extract_implication_constraint(self, node) -> SignalResult:
        """[NOT TESTED] ImplicationConstraint: implication constraint"""
        result = SignalResult()
        left = getattr(node, 'left', None) or getattr(node, 'condition', None)
        right = getattr(node, 'right', None) or getattr(node, 'constraint', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result
    
    @on('LibraryDeclaration')
    def extract_library_declaration(self, node) -> SignalResult:
        """[NOT TESTED] LibraryDeclaration: library declaration"""
        return SignalResult()
    
    @on('LibraryIncDirClause')
    def extract_library_inc_dir_clause(self, node) -> SignalResult:
        """[NOT TESTED] LibraryIncDirClause: library include directory clause"""
        return SignalResult()
    
    @on('ModportSubroutinePort')
    def extract_modport_subroutine_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportSubroutinePort: modport subroutine port"""
        return SignalResult()
    
    @on('ParenthesizedConditionalDirectiveExpression')
    def extract_parenthesized_conditional_directive_expression(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedConditionalDirectiveExpression: parenthesized conditional directive expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('ParenthesizedEventExpression')
    def extract_parenthesized_event_expression(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedEventExpression: parenthesized event expression"""
        result = SignalResult()
        event = getattr(node, 'event', None) or getattr(node, 'expr', None)
        if event:
            result = result.merge(self.extract(event))
        return result
    
    @on('PropertySpec')
    def extract_property_spec(self, node) -> SignalResult:
        """[NOT TESTED] PropertySpec: property spec"""
        result = SignalResult()
        prop = getattr(node, 'property', None) or getattr(node, 'expr', None)
        if prop:
            result = result.merge(self.extract(prop))
        return result
    
    @on('SpecifyBlock')
    def extract_specify_block(self, node) -> SignalResult:
        """[NOT TESTED] SpecifyBlock: specify block"""
        return SignalResult()
    
    @on('SpecparamDeclaration')
    def extract_specparam_declaration(self, node) -> SignalResult:
        """[NOT TESTED] SpecparamDeclaration: specparam declaration"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'value', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('SuperNewDefaultedArgsExpression')
    def extract_super_new_defaulted_args_expression(self, node) -> SignalResult:
        """[NOT TESTED] SuperNewDefaultedArgsExpression: super.new with defaulted args expression"""
        return SignalResult()
    
    @on('TimingControlExpression')
    def extract_timing_control_expression(self, node) -> SignalResult:
        """[NOT TESTED] TimingControlExpression: timing control expression"""
        return SignalResult()
    
    @on('TimingControlStatement')
    def extract_timing_control_statement(self, node) -> SignalResult:
        """[NOT TESTED] TimingControlStatement: timing control statement"""
        return SignalResult()
    
    @on('UdpDeclaration')
    def extract_udp_declaration(self, node) -> SignalResult:
        """[NOT TESTED] UdpDeclaration: UDP declaration (Verilog primitive)"""
        return SignalResult()
    
    @on('UnaryConditionalDirectiveExpression')
    def extract_unary_conditional_directive_expression(self, node) -> SignalResult:
        """[NOT TESTED] UnaryConditionalDirectiveExpression: unary conditional directive expression"""
        result = SignalResult()
        expr = getattr(node, 'expr', None) or getattr(node, 'expression', None)
        if expr:
            result = result.merge(self.extract(expr))
        return result
    
    @on('UniquenessConstraint')
    def extract_uniqueness_constraint(self, node) -> SignalResult:
        """[NOT TESTED] UniquenessConstraint: uniqueness constraint"""
        result = SignalResult()
        items = getattr(node, 'items', None)
        if items and hasattr(items, '__iter__'):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('UserDefinedNetDeclaration')
    def extract_user_defined_net_declaration(self, node) -> SignalResult:
        """[NOT TESTED] UserDefinedNetDeclaration: user defined net declaration"""
        return SignalResult()
    
    @on('VirtualInterfaceType')
    def extract_virtual_interface_type(self, node) -> SignalResult:
        """[NOT TESTED] VirtualInterfaceType: virtual interface type"""
        return SignalResult()

    @on('UdpSimpleField')
    def extract_udpsimplefield(self, node) -> SignalResult:
        """[NOT TESTED] UdpSimpleField: Udpsimplefield"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('UnconnectedDriveDirective')
    def extract_unconnecteddrivedirective(self, node) -> SignalResult:
        """[NOT TESTED] UnconnectedDriveDirective: Unconnecteddrivedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('UndefDirective')
    def extract_undefdirective(self, node) -> SignalResult:
        """[NOT TESTED] UndefDirective: Undefdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('UndefineAllDirective')
    def extract_undefinealldirective(self, node) -> SignalResult:
        """[NOT TESTED] UndefineAllDirective: Undefinealldirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('UnionType')
    def extract_uniontype(self, node) -> SignalResult:
        """[NOT TESTED] UnionType: Uniontype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('UnitScope')
    def extract_unitscope(self, node) -> SignalResult:
        """[NOT TESTED] UnitScope: Unitscope"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('Unknown')
    def extract_unknown(self, node) -> SignalResult:
        """[NOT TESTED] Unknown: Unknown"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('Untyped')
    def extract_untyped(self, node) -> SignalResult:
        """[NOT TESTED] Untyped: Untyped"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('VariablePortHeader')
    def extract_variableportheader(self, node) -> SignalResult:
        """[NOT TESTED] VariablePortHeader: Variableportheader"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('WildcardDimensionSpecifier')
    def extract_wildcarddimensionspecifier(self, node) -> SignalResult:
        """[NOT TESTED] WildcardDimensionSpecifier: Wildcarddimensionspecifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('WildcardPortConnection')
    def extract_wildcardportconnection(self, node) -> SignalResult:
        """[NOT TESTED] WildcardPortConnection: Wildcardportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('WildcardPortList')
    def extract_wildcardportlist(self, node) -> SignalResult:
        """[NOT TESTED] WildcardPortList: Wildcardportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('WildcardUdpPortList')
    def extract_wildcardudpportlist(self, node) -> SignalResult:
        """[NOT TESTED] WildcardUdpPortList: Wildcardudpportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('StructType')
    def extract_structtype(self, node) -> SignalResult:
        """[NOT TESTED] StructType: Structtype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('StructUnionMember')
    def extract_structunionmember(self, node) -> SignalResult:
        """[NOT TESTED] StructUnionMember: Structunionmember"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('SuperHandle')
    def extract_superhandle(self, node) -> SignalResult:
        """[NOT TESTED] SuperHandle: Superhandle"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('SystemName')
    def extract_systemname(self, node) -> SignalResult:
        """[NOT TESTED] SystemName: Systemname"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('SystemTimingCheck')
    def extract_systemtimingcheck(self, node) -> SignalResult:
        """[NOT TESTED] SystemTimingCheck: Systemtimingcheck"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ThisHandle')
    def extract_thishandle(self, node) -> SignalResult:
        """[NOT TESTED] ThisHandle: Thishandle"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('TimeScaleDirective')
    def extract_timescaledirective(self, node) -> SignalResult:
        """[NOT TESTED] TimeScaleDirective: Timescaledirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('TimeType')
    def extract_timetype(self, node) -> SignalResult:
        """[NOT TESTED] TimeType: Timetype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('TokenList')
    def extract_tokenlist(self, node) -> SignalResult:
        """[NOT TESTED] TokenList: Tokenlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('TransListCoverageBinInitializer')
    def extract_translistcoveragebininitializer(self, node) -> SignalResult:
        """[NOT TESTED] TransListCoverageBinInitializer: Translistcoveragebininitializer"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('TransRange')
    def extract_transrange(self, node) -> SignalResult:
        """[NOT TESTED] TransRange: Transrange"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('TransRepeatRange')
    def extract_transrepeatrange(self, node) -> SignalResult:
        """[NOT TESTED] TransRepeatRange: Transrepeatrange"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('TransSet')
    def extract_transset(self, node) -> SignalResult:
        """[NOT TESTED] TransSet: Transset"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('TypeAssignment')
    def extract_typeassignment(self, node) -> SignalResult:
        """[NOT TESTED] TypeAssignment: Typeassignment"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('UdpBody')
    def extract_udpbody(self, node) -> SignalResult:
        """[NOT TESTED] UdpBody: Udpbody"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('UdpEdgeField')
    def extract_udpedgefield(self, node) -> SignalResult:
        """[NOT TESTED] UdpEdgeField: Udpedgefield"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('UdpEntry')
    def extract_udpentry(self, node) -> SignalResult:
        """[NOT TESTED] UdpEntry: Udpentry"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('UdpInitialStmt')
    def extract_udpinitialstmt(self, node) -> SignalResult:
        """[NOT TESTED] UdpInitialStmt: Udpinitialstmt"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('UdpInputPortDecl')
    def extract_udpinputportdecl(self, node) -> SignalResult:
        """[NOT TESTED] UdpInputPortDecl: Udpinputportdecl"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('UdpOutputPortDecl')
    def extract_udpoutputportdecl(self, node) -> SignalResult:
        """[NOT TESTED] UdpOutputPortDecl: Udpoutputportdecl"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('PragmaDirective')
    def extract_pragmadirective(self, node) -> SignalResult:
        """[NOT TESTED] PragmaDirective: Pragmadirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('PrimitiveInstantiation')
    def extract_primitiveinstantiation(self, node) -> SignalResult:
        """[NOT TESTED] PrimitiveInstantiation: Primitiveinstantiation"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('Production')
    def extract_production(self, node) -> SignalResult:
        """[NOT TESTED] Production: Production"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ProtectDirective')
    def extract_protectdirective(self, node) -> SignalResult:
        """[NOT TESTED] ProtectDirective: Protectdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ProtectedDirective')
    def extract_protecteddirective(self, node) -> SignalResult:
        """[NOT TESTED] ProtectedDirective: Protecteddirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('PullStrength')
    def extract_pullstrength(self, node) -> SignalResult:
        """[NOT TESTED] PullStrength: Pullstrength"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('QueueDimensionSpecifier')
    def extract_queuedimensionspecifier(self, node) -> SignalResult:
        """[NOT TESTED] QueueDimensionSpecifier: Queuedimensionspecifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('RangeCoverageBinInitializer')
    def extract_rangecoveragebininitializer(self, node) -> SignalResult:
        """[NOT TESTED] RangeCoverageBinInitializer: Rangecoveragebininitializer"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('RangeDimensionSpecifier')
    def extract_rangedimensionspecifier(self, node) -> SignalResult:
        """[NOT TESTED] RangeDimensionSpecifier: Rangedimensionspecifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('RangeList')
    def extract_rangelist(self, node) -> SignalResult:
        """[NOT TESTED] RangeList: Rangelist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('RealTimeType')
    def extract_realtimetype(self, node) -> SignalResult:
        """[NOT TESTED] RealTimeType: Realtimetype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ResetAllDirective')
    def extract_resetalldirective(self, node) -> SignalResult:
        """[NOT TESTED] ResetAllDirective: Resetalldirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('RootScope')
    def extract_rootscope(self, node) -> SignalResult:
        """[NOT TESTED] RootScope: Rootscope"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('RsIfElse')
    def extract_rsifelse(self, node) -> SignalResult:
        """[NOT TESTED] RsIfElse: Rsifelse"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('RsProdItem')
    def extract_rsproditem(self, node) -> SignalResult:
        """[NOT TESTED] RsProdItem: Rsproditem"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('RsRepeat')
    def extract_rsrepeat(self, node) -> SignalResult:
        """[NOT TESTED] RsRepeat: Rsrepeat"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('RsRule')
    def extract_rsrule(self, node) -> SignalResult:
        """[NOT TESTED] RsRule: Rsrule"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('SimplePathSuffix')
    def extract_simplepathsuffix(self, node) -> SignalResult:
        """[NOT TESTED] SimplePathSuffix: Simplepathsuffix"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('SimpleRangeSelect')
    def extract_simplerangeselect(self, node) -> SignalResult:
        """[NOT TESTED] SimpleRangeSelect: Simplerangeselect"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('SpecparamDeclarator')
    def extract_specparamdeclarator(self, node) -> SignalResult:
        """[NOT TESTED] SpecparamDeclarator: Specparamdeclarator"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('NamedLabel')
    def extract_namedlabel(self, node) -> SignalResult:
        """[NOT TESTED] NamedLabel: Namedlabel"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('NamedParamAssignment')
    def extract_namedparamassignment(self, node) -> SignalResult:
        """[NOT TESTED] NamedParamAssignment: Namedparamassignment"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('NamedPortConnection')
    def extract_namedportconnection(self, node) -> SignalResult:
        """[NOT TESTED] NamedPortConnection: Namedportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('NamedStructurePatternMember')
    def extract_namedstructurepatternmember(self, node) -> SignalResult:
        """[NOT TESTED] NamedStructurePatternMember: Namedstructurepatternmember"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('NetAlias')
    def extract_netalias(self, node) -> SignalResult:
        """[NOT TESTED] NetAlias: Netalias"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('NetPortHeader')
    def extract_netportheader(self, node) -> SignalResult:
        """[NOT TESTED] NetPortHeader: Netportheader"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('NoUnconnectedDriveDirective')
    def extract_nounconnecteddrivedirective(self, node) -> SignalResult:
        """[NOT TESTED] NoUnconnectedDriveDirective: Nounconnecteddrivedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('NonAnsiPortList')
    def extract_nonansiportlist(self, node) -> SignalResult:
        """[NOT TESTED] NonAnsiPortList: Nonansiportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('NonAnsiUdpPortList')
    def extract_nonansiudpportlist(self, node) -> SignalResult:
        """[NOT TESTED] NonAnsiUdpPortList: Nonansiudpportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('OneStepDelay')
    def extract_onestepdelay(self, node) -> SignalResult:
        """[NOT TESTED] OneStepDelay: Onestepdelay"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('OrderedArgument')
    def extract_orderedargument(self, node) -> SignalResult:
        """[NOT TESTED] OrderedArgument: Orderedargument"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('OrderedParamAssignment')
    def extract_orderedparamassignment(self, node) -> SignalResult:
        """[NOT TESTED] OrderedParamAssignment: Orderedparamassignment"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('OrderedPortConnection')
    def extract_orderedportconnection(self, node) -> SignalResult:
        """[NOT TESTED] OrderedPortConnection: Orderedportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('OrderedStructurePatternMember')
    def extract_orderedstructurepatternmember(self, node) -> SignalResult:
        """[NOT TESTED] OrderedStructurePatternMember: Orderedstructurepatternmember"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ParameterPortList')
    def extract_parameterportlist(self, node) -> SignalResult:
        """[NOT TESTED] ParameterPortList: Parameterportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ParameterValueAssignment')
    def extract_parametervalueassignment(self, node) -> SignalResult:
        """[NOT TESTED] ParameterValueAssignment: Parametervalueassignment"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ParenthesizedPattern')
    def extract_parenthesizedpattern(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedPattern: Parenthesizedpattern"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('PathDescription')
    def extract_pathdescription(self, node) -> SignalResult:
        """[NOT TESTED] PathDescription: Pathdescription"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('PortConcatenation')
    def extract_portconcatenation(self, node) -> SignalResult:
        """[NOT TESTED] PortConcatenation: Portconcatenation"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('PortReference')
    def extract_portreference(self, node) -> SignalResult:
        """[NOT TESTED] PortReference: Portreference"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('IdentifierSelectName')
    def extract_identifier_select_name(self, node) -> SignalResult:
        """[MIGRATED] IdentifierSelectName: data[3] etc with bit/range select
        
        From visit_identifier_select - handles complex selectors
        """
        base_name = None
        
        # Get base identifier name
        if hasattr(node, 'identifier'):
            ident = node.identifier
            if hasattr(ident, 'value'):
                base_name = str(ident.value).strip()
            else:
                base_name = str(ident).strip()
        
        if not base_name:
            base_name = str(node).strip().split('[')[0]
        
        # Get selectors (bit/range selects)
        selectors = getattr(node, 'selectors', None)
        if selectors and hasattr(selectors, '__iter__') and not isinstance(selectors, str):
            for i in range(len(selectors)):
                sel = selectors[i]
                sel_kind = str(getattr(sel, 'kind', ''))
                
                if 'ElementSelect' in sel_kind:
                    bit_select = getattr(sel, 'selector', None)
                    if bit_select:
                        bit_select_kind = str(getattr(bit_select, 'kind', ''))
                        
                        if 'SimpleRange' in bit_select_kind:
                            left_expr = getattr(bit_select, 'left', None)
                            right_expr = getattr(bit_select, 'right', None)
                            
                            param_map = self._get_param_map()
                            left_val = self._evaluate_expr(left_expr, param_map) if left_expr else None
                            right_val = self._evaluate_expr(right_expr, param_map) if right_expr else None
                            
                            if left_val is not None or right_val is not None:
                                left_str = str(left_val) if left_val is not None else '?'
                                right_str = str(right_val) if right_val is not None else '?'
                                base_name = f"{base_name}[{left_str}:{right_str}]"
                                break
                        else:
                            selector_expr = getattr(bit_select, 'expr', None)
                            if selector_expr:
                                param_map = self._get_param_map()
                                evaluated = self._evaluate_expr(selector_expr, param_map)
                                if evaluated is not None:
                                    base_name = f"{base_name}[{evaluated}]"
                                    break
                
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
                            base_name = f"{base_name}[{left_str}:{right_str}]"
                            break
        
        clean_name = self.adapter.clean_name(base_name) if base_name else None
        return SignalResult(primary=clean_name) if clean_name else SignalResult()

    def extract_identifierselectname(self, node) -> SignalResult:
        """[NOT TESTED] IdentifierSelectName: Identifierselectname"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('IfDefDirective')
    def extract_ifdefdirective(self, node) -> SignalResult:
        """[NOT TESTED] IfDefDirective: Ifdefdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('IfNDefDirective')
    def extract_ifndefdirective(self, node) -> SignalResult:
        """[NOT TESTED] IfNDefDirective: Ifndefdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ImmediateAssertionMember')
    def extract_immediateassertionmember(self, node) -> SignalResult:
        """[NOT TESTED] ImmediateAssertionMember: Immediateassertionmember"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ImplicitType')
    def extract_implicittype(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitType: Implicittype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('IncludeDirective')
    def extract_includedirective(self, node) -> SignalResult:
        """[NOT TESTED] IncludeDirective: Includedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('InstanceConfigRule')
    def extract_instanceconfigrule(self, node) -> SignalResult:
        """[NOT TESTED] InstanceConfigRule: Instanceconfigrule"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('InstanceName')
    def extract_instancename(self, node) -> SignalResult:
        """[NOT TESTED] InstanceName: Instancename"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('LibraryIncludeStatement')
    def extract_libraryincludestatement(self, node) -> SignalResult:
        """[NOT TESTED] LibraryIncludeStatement: Libraryincludestatement"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('LibraryMap')
    def extract_librarymap(self, node) -> SignalResult:
        """[NOT TESTED] LibraryMap: Librarymap"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('LineDirective')
    def extract_linedirective(self, node) -> SignalResult:
        """[NOT TESTED] LineDirective: Linedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('LocalScope')
    def extract_localscope(self, node) -> SignalResult:
        """[NOT TESTED] LocalScope: Localscope"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('MacroActualArgument')
    def extract_macroactualargument(self, node) -> SignalResult:
        """[NOT TESTED] MacroActualArgument: Macroactualargument"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('MacroActualArgumentList')
    def extract_macroactualargumentlist(self, node) -> SignalResult:
        """[NOT TESTED] MacroActualArgumentList: Macroactualargumentlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('MacroArgumentDefault')
    def extract_macroargumentdefault(self, node) -> SignalResult:
        """[NOT TESTED] MacroArgumentDefault: Macroargumentdefault"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('MacroFormalArgument')
    def extract_macroformalargument(self, node) -> SignalResult:
        """[NOT TESTED] MacroFormalArgument: Macroformalargument"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('MacroFormalArgumentList')
    def extract_macroformalargumentlist(self, node) -> SignalResult:
        """[NOT TESTED] MacroFormalArgumentList: Macroformalargumentlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('MacroUsage')
    def extract_macrousage(self, node) -> SignalResult:
        """[NOT TESTED] MacroUsage: Macrousage"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('NamedArgument')
    def extract_namedargument(self, node) -> SignalResult:
        """[NOT TESTED] NamedArgument: Namedargument"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('NamedConditionalDirectiveExpression')
    def extract_namedconditionaldirectiveexpression(self, node) -> SignalResult:
        """[NOT TESTED] NamedConditionalDirectiveExpression: Namedconditionaldirectiveexpression"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ElsIfDirective')
    def extract_elsifdirective(self, node) -> SignalResult:
        """[NOT TESTED] ElsIfDirective: Elsifdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ElseDirective')
    def extract_elsedirective(self, node) -> SignalResult:
        """[NOT TESTED] ElseDirective: Elsedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EmptyIdentifierName')
    def extract_emptyidentifiername(self, node) -> SignalResult:
        """[NOT TESTED] EmptyIdentifierName: Emptyidentifiername"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EmptyMember')
    def extract_emptymember(self, node) -> SignalResult:
        """[NOT TESTED] EmptyMember: Emptymember"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EmptyNonAnsiPort')
    def extract_emptynonansiport(self, node) -> SignalResult:
        """[NOT TESTED] EmptyNonAnsiPort: Emptynonansiport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EmptyPortConnection')
    def extract_emptyportconnection(self, node) -> SignalResult:
        """[NOT TESTED] EmptyPortConnection: Emptyportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EmptyTimingCheckArg')
    def extract_emptytimingcheckarg(self, node) -> SignalResult:
        """[NOT TESTED] EmptyTimingCheckArg: Emptytimingcheckarg"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EndCellDefineDirective')
    def extract_endcelldefinedirective(self, node) -> SignalResult:
        """[NOT TESTED] EndCellDefineDirective: Endcelldefinedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EndIfDirective')
    def extract_endifdirective(self, node) -> SignalResult:
        """[NOT TESTED] EndIfDirective: Endifdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EndKeywordsDirective')
    def extract_endkeywordsdirective(self, node) -> SignalResult:
        """[NOT TESTED] EndKeywordsDirective: Endkeywordsdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EndProtectDirective')
    def extract_endprotectdirective(self, node) -> SignalResult:
        """[NOT TESTED] EndProtectDirective: Endprotectdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EndProtectedDirective')
    def extract_endprotecteddirective(self, node) -> SignalResult:
        """[NOT TESTED] EndProtectedDirective: Endprotecteddirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EnumType')
    def extract_enumtype(self, node) -> SignalResult:
        """[NOT TESTED] EnumType: Enumtype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ExplicitAnsiPort')
    def extract_explicitansiport(self, node) -> SignalResult:
        """[NOT TESTED] ExplicitAnsiPort: Explicitansiport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ExplicitNonAnsiPort')
    def extract_explicitnonansiport(self, node) -> SignalResult:
        """[NOT TESTED] ExplicitNonAnsiPort: Explicitnonansiport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ExternUdpDecl')
    def extract_externudpdecl(self, node) -> SignalResult:
        """[NOT TESTED] ExternUdpDecl: Externudpdecl"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('FilePathSpec')
    def extract_filepathspec(self, node) -> SignalResult:
        """[NOT TESTED] FilePathSpec: Filepathspec"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ForeachLoopList')
    def extract_foreachlooplist(self, node) -> SignalResult:
        """[NOT TESTED] ForeachLoopList: Foreachlooplist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ForwardTypeRestriction')
    def extract_forwardtyperestriction(self, node) -> SignalResult:
        """[NOT TESTED] ForwardTypeRestriction: Forwardtyperestriction"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('HierarchyInstantiation')
    def extract_hierarchyinstantiation(self, node) -> SignalResult:
        """[NOT TESTED] HierarchyInstantiation: Hierarchyinstantiation"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DefaultConfigRule')
    def extract_defaultconfigrule(self, node) -> SignalResult:
        """[NOT TESTED] DefaultConfigRule: Defaultconfigrule"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DefaultDecayTimeDirective')
    def extract_defaultdecaytimedirective(self, node) -> SignalResult:
        """[NOT TESTED] DefaultDecayTimeDirective: Defaultdecaytimedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DefaultDistItem')
    def extract_defaultdistitem(self, node) -> SignalResult:
        """[NOT TESTED] DefaultDistItem: Defaultdistitem"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DefaultNetTypeDirective')
    def extract_defaultnettypedirective(self, node) -> SignalResult:
        """[NOT TESTED] DefaultNetTypeDirective: Defaultnettypedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DefaultSkewItem')
    def extract_defaultskewitem(self, node) -> SignalResult:
        """[NOT TESTED] DefaultSkewItem: Defaultskewitem"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DefaultTriregStrengthDirective')
    def extract_defaulttriregstrengthdirective(self, node) -> SignalResult:
        """[NOT TESTED] DefaultTriregStrengthDirective: Defaulttriregstrengthdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DeferredAssertion')
    def extract_deferredassertion(self, node) -> SignalResult:
        """[NOT TESTED] DeferredAssertion: Deferredassertion"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DefineDirective')
    def extract_definedirective(self, node) -> SignalResult:
        """[NOT TESTED] DefineDirective: Definedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('Delay3')
    def extract_delay3(self, node) -> SignalResult:
        """[NOT TESTED] Delay3: Delay3"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DelayModeDistributedDirective')
    def extract_delaymodedistributeddirective(self, node) -> SignalResult:
        """[NOT TESTED] DelayModeDistributedDirective: Delaymodedistributeddirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DelayModePathDirective')
    def extract_delaymodepathdirective(self, node) -> SignalResult:
        """[NOT TESTED] DelayModePathDirective: Delaymodepathdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DelayModeUnitDirective')
    def extract_delaymodeunitdirective(self, node) -> SignalResult:
        """[NOT TESTED] DelayModeUnitDirective: Delaymodeunitdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DelayModeZeroDirective')
    def extract_delaymodezerodirective(self, node) -> SignalResult:
        """[NOT TESTED] DelayModeZeroDirective: Delaymodezerodirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DisableIff')
    def extract_disableiff(self, node) -> SignalResult:
        """[NOT TESTED] DisableIff: Disableiff"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DistItem')
    def extract_distitem(self, node) -> SignalResult:
        """[NOT TESTED] DistItem: Distitem"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DriveStrength')
    def extract_drivestrength(self, node) -> SignalResult:
        """[NOT TESTED] DriveStrength: Drivestrength"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EdgeControlSpecifier')
    def extract_edgecontrolspecifier(self, node) -> SignalResult:
        """[NOT TESTED] EdgeControlSpecifier: Edgecontrolspecifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EdgeDescriptor')
    def extract_edgedescriptor(self, node) -> SignalResult:
        """[NOT TESTED] EdgeDescriptor: Edgedescriptor"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('EdgeSensitivePathSuffix')
    def extract_edgesensitivepathsuffix(self, node) -> SignalResult:
        """[NOT TESTED] EdgeSensitivePathSuffix: Edgesensitivepathsuffix"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ElementSelect')
    def extract_elementselect(self, node) -> SignalResult:
        """[NOT TESTED] ElementSelect: Elementselect"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('AnsiPortList')
    def extract_ansiportlist(self, node) -> SignalResult:
        """[NOT TESTED] AnsiPortList: Ansiportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('AnsiUdpPortList')
    def extract_ansiudpportlist(self, node) -> SignalResult:
        """[NOT TESTED] AnsiUdpPortList: Ansiudpportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ArgumentList')
    def extract_argumentlist(self, node) -> SignalResult:
        """[NOT TESTED] ArgumentList: Argumentlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('AttributeInstance')
    def extract_attributeinstance(self, node) -> SignalResult:
        """[NOT TESTED] AttributeInstance: Attributeinstance"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('AttributeSpec')
    def extract_attributespec(self, node) -> SignalResult:
        """[NOT TESTED] AttributeSpec: Attributespec"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('BeginKeywordsDirective')
    def extract_beginkeywordsdirective(self, node) -> SignalResult:
        """[NOT TESTED] BeginKeywordsDirective: Beginkeywordsdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('CellConfigRule')
    def extract_cellconfigrule(self, node) -> SignalResult:
        """[NOT TESTED] CellConfigRule: Cellconfigrule"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('CellDefineDirective')
    def extract_celldefinedirective(self, node) -> SignalResult:
        """[NOT TESTED] CellDefineDirective: Celldefinedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ChargeStrength')
    def extract_chargestrength(self, node) -> SignalResult:
        """[NOT TESTED] ChargeStrength: Chargestrength"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('CompilationUnit')
    def extract_compilationunit(self, node) -> SignalResult:
        """[NOT TESTED] CompilationUnit: Compilationunit"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ConditionalPredicate')
    def extract_conditionalpredicate(self, node) -> SignalResult:
        """[NOT TESTED] ConditionalPredicate: Conditionalpredicate"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ConfigCellIdentifier')
    def extract_configcellidentifier(self, node) -> SignalResult:
        """[NOT TESTED] ConfigCellIdentifier: Configcellidentifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ConfigInstanceIdentifier')
    def extract_configinstanceidentifier(self, node) -> SignalResult:
        """[NOT TESTED] ConfigInstanceIdentifier: Configinstanceidentifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ConfigLiblist')
    def extract_configliblist(self, node) -> SignalResult:
        """[NOT TESTED] ConfigLiblist: Configliblist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('ConstructorName')
    def extract_constructorname(self, node) -> SignalResult:
        """[NOT TESTED] ConstructorName: Constructorname"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('CycleDelay')
    def extract_cycledelay(self, node) -> SignalResult:
        """[NOT TESTED] CycleDelay: Cycledelay"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DPIExport')
    def extract_dpiexport(self, node) -> SignalResult:
        """[NOT TESTED] DPIExport: Dpiexport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DPIImport')
    def extract_dpiimport(self, node) -> SignalResult:
        """[NOT TESTED] DPIImport: Dpiimport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DefParam')
    def extract_defparam(self, node) -> SignalResult:
        """[NOT TESTED] DefParam: Defparam"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on('DefParamAssignment')
    def extract_defparamassignment(self, node) -> SignalResult:
        """[NOT TESTED] DefParamAssignment: Defparamassignment"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, 'items', None) or getattr(node, 'elements', None) or getattr(node, 'members', None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    
    @on('Declarator')
    def extract_declarator(self, node) -> SignalResult:
        """[NOT TESTED] Declarator: variable declarator"""
        result = SignalResult()
        name = getattr(node, 'name', None) or getattr(node, 'symbol', None)
        if name:
            if hasattr(name, 'name'):
                result.add_signal(str(name.name))
            else:
                result.add_signal(str(name))
        return result
    
    @on('HierarchicalInstance')
    def extract_hierarchical_instance(self, node) -> SignalResult:
        """[NOT TESTED] HierarchicalInstance: module instance"""
        result = SignalResult()
        name = getattr(node, 'name', None)
        if name:
            result.add_signal(str(name))
        return result
    
    @on('ImplicitAnsiPort')
    def extract_implicit_ansi_port(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitAnsiPort: implicit ansi port"""
        result = SignalResult()
        name = getattr(node, 'name', None)
        if name:
            result.add_signal(str(name))
        return result
    
    @on('ImplicitNonAnsiPort')
    def extract_implicit_non_ansi_port(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitNonAnsiPort: implicit non-ansi port"""
        result = SignalResult()
        name = getattr(node, 'name', None)
        if name:
            result.add_signal(str(name))
        return result
    
    @on('NamedType')
    def extract_named_type(self, node) -> SignalResult:
        """[NOT TESTED] NamedType: named type"""
        result = SignalResult()
        name = getattr(node, 'name', None)
        if name:
            result.add_signal(str(name))
        return result
    
    @on('SeparatedList')
    def extract_separated_list(self, node) -> SignalResult:
        """[NOT TESTED] SeparatedList: separated list"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'elements', None)
        if items:
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('SyntaxList')
    def extract_syntax_list(self, node) -> SignalResult:
        """[NOT TESTED] SyntaxList: syntax list"""
        result = SignalResult()
        items = getattr(node, 'items', None) or getattr(node, 'elements', None)
        if items:
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result
    
    @on('VariableDimension')
    def extract_variable_dimension(self, node) -> SignalResult:
        """[NOT TESTED] VariableDimension: variable dimension"""
        result = SignalResult()
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
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