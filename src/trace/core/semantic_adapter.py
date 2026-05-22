#==============================================================================
# semantic_adapter.py - Semantic AST 适配器
#
# 将 Semantic AST (RootSymbol) 适配为 GraphBuilder 期望的接口
# 遵循铁律1: 必须使用 Semantic AST (Compilation + getRoot())
#==============================================================================

from typing import Dict, List, Optional, Iterator, Callable, Any
import sys

# 确保 pyslang bindings 在 path 中
PYSLLANG_BINDINGS_PATH = '/Users/fundou/my_dv_proj/slang/build/bindings'
if PYSLLANG_BINDINGS_PATH not in sys.path:
    sys.path.insert(0, PYSLLANG_BINDINGS_PATH)

import pyslang


class SemanticAdapter:
    """
    Semantic AST 适配器

    将 Semantic AST (RootSymbol) 适配为统一接口,供 GraphBuilder 使用。

    主要差异 (Semantic AST vs SyntaxTree):
    - RootSymbol 包含 InstanceSymbol 列表,而非 ModuleDeclaration 列表
    - InstanceSymbol.body 包含模块成员
    - 使用 root.visit(callback) 遍历
    - 节点是语义符号 (Symbol),不是语法节点 (SyntaxNode)
    """

    def __init__(self, root, compiler=None):
        """
        Args:
            root: Semantic AST root (RootSymbol from comp.getRoot())
            compiler: Optional SVCompiler for accessing getDefinitions()
        """
        self._root = root
        self._compiler = compiler

    @property
    def root(self):
        """返回 Semantic AST root"""
        return self._root

    @property
    def parser(self):
        """兼容属性: 返回 self 用于模拟 parser.trees"""
        return self

    @property
    def trees(self):
        """兼容属性: 返回空字典 (Semantic AST 不需要 trees)"""
        return {}

    def items(self):
        """兼容方法: 返回空迭代器 (Semantic AST 不使用 SyntaxTree)"""
        return iter([])

    # =========================================================================
    # 模块和实例相关
    # =========================================================================

    def get_modules(self) -> List:
        """获取所有模块定义 (InstanceSymbol)

        Semantic AST 中,每个模块定义对应一个 InstanceSymbol。
        我们从 root 遍历获取所有 InstanceSymbol,包括嵌套的。
        """
        modules = []
        seen_ids = set()

        def collect_instances(node):
            if node is None:
                return

            kind = getattr(node, 'kind', None)
            kind_str = str(kind) if kind else 'None'
            name = getattr(node, 'name', None)
            name_str = str(name) if name else '_anon_'

            key = (kind_str, name_str)
            if key in seen_ids:
                return
            seen_ids.add(key)

            if kind_str == 'SymbolKind.Instance':
                modules.append(node)
                # 递归收集嵌套实例
                body = getattr(node, 'body', None)
                if isinstance(body, pyslang.InstanceBodySymbol):
                    for child in body:
                        collect_instances(child)

        # 遍历 root.topInstances 获取顶级模块实例
        for inst in self._root.topInstances:
            collect_instances(inst)

        return modules

    def get_module_instances(self) -> List:
        """获取所有模块实例 (SemanticInstanceWrapper)

        递归遍历所有模块的 body,找出嵌套的实例

        Args:
            trees: 兼容 SyntaxTree 接口,此参数被忽略

        Returns:
            SemanticInstanceWrapper 列表,包装 InstanceSymbol
        """
        wrappers = []
        # 使用 (kind, name) 作为唯一标识,而非 hash
        # pyslang 对象池会导致不同对象共享 hash,id() 也不稳定
        visited_names = set()

        def find_instances(node, parent_path=''):
            if node is None:
                return

            kind = getattr(node, 'kind', None)
            kind_str = str(kind) if kind else 'None'
            name = getattr(node, 'name', None)
            name_str = str(name) if name else '_anon_'

            # path_str 用于 GenerateBlock/GenerateBlockArray 的递归传递
            # 初始化为 parent_path，确保在所有分支都有定义
            path_str = parent_path

            # 使用 (kind, name) 作为唯一标识
            key = (kind_str, name_str)
            if key in visited_names:
                return
            visited_names.add(key)

            # 直接的 InstanceSymbol
            if kind_str == 'SymbolKind.Instance':
                # 检查是否是 Definition (顶层模块定义) vs 嵌套实例
                # InstanceSymbol 同时用于顶层定义和嵌套实例
                # DefinitionSymbol 的 hierarchicalPath 是模块名本身 (如 "top", "unused")
                # 嵌套实例的 hierarchicalPath 包含父路径 (如 "top.sub")
                hierarchical_path = getattr(node, 'hierarchicalPath', None)
                path_str = str(hierarchical_path) if hierarchical_path else ''
                
                # 如果是顶层定义 (路径中不包含 '.') 且 parent_path 为空
                # 则认为是顶层模块定义,跳过不添加
                # 但仍然递归检查其 body 是否包含嵌套实例
                if not parent_path and '.' not in path_str and path_str:
                    # 是顶层模块定义,递归检查其 body
                    body = getattr(node, 'body', None)
                    if isinstance(body, pyslang.InstanceBodySymbol):
                        for child in body:
                            find_instances(child, path_str)
                    return
                    
                parent_name = parent_path if parent_path else None
                wrappers.append(SemanticInstanceWrapper(node, parent_module=parent_name))
                # 递归检查 body 中的嵌套实例
                body = getattr(node, 'body', None)
                if isinstance(body, pyslang.InstanceBodySymbol):
                    for child in body:
                        find_instances(child, f"{parent_path}.{name_str}" if parent_path else name_str)
            
            # GenerateBlockArray: 遍历 entries 找到其中的实例
            elif kind_str == 'SymbolKind.GenerateBlockArray':
                entries = getattr(node, 'entries', None)
                gen_name = name_str
                if entries:
                    for idx, entry in enumerate(entries):
                        # entry 是 GenerateBlock,迭代它获取实例
                        for child in entry:
                            child_kind = str(getattr(child, 'kind', ''))
                            if 'Instance' in child_kind:
                                # 构建完整路径: parent.GEN.u_dut (或 parent.GEN[0].u_dut)
                                child_path = f"{parent_path}.{gen_name}.{getattr(child, 'name', '_anon')}"
                                find_instances(child, child_path)
            
            # GenerateBlock: 直接迭代获取实例
            elif kind_str == 'SymbolKind.GenerateBlock':
                for child in node:
                    find_instances(child, path_str)

        # 遍历 root 下的所有项
        for item in self._root:
            find_instances(item)

        return wrappers

    def get_module_name(self, module) -> str:
        """获取模块名称

        Semantic AST: 对于 InstanceSymbol,返回 definition.name;
                      对于 DefinitionSymbol,返回 name
        """
        kind_str = str(getattr(module, 'kind', ''))

        if 'Instance' in kind_str:
            # InstanceSymbol: definition.name 是模块类型
            defn = getattr(module, 'definition', None)
            if defn and hasattr(defn, 'name'):
                return str(defn.name)

        if hasattr(module, 'name'):
            return str(module.name)
        return 'unknown'

    def get_classes(self) -> List:
        """获取所有类定义"""
        classes = []
        
        # Semantic AST: RootSymbol[0] is CompilationUnitSymbol, iterate it for classes
        comp_unit = self._root[0] if len(self._root) > 0 else None
        if comp_unit:
            for item in comp_unit:
                kind_str = str(getattr(item, 'kind', ''))
                if 'Class' in kind_str:
                    classes.append(item)
        
        return classes

    def get_interfaces(self) -> List:
        """获取所有接口定义 (Semantic AST)"""
        interfaces = []
        
        # Use _compiler.get_compilation().getDefinitions() to get all definitions
        if self._compiler:
            compilation = self._compiler.get_compilation()
            for defn in compilation.getDefinitions():
                kind_str = str(defn.kind)
                # Check if it's a Definition
                if 'Definition' in kind_str and hasattr(defn, 'syntax'):
                    # Check syntax.kind for InterfaceDeclaration
                    syntax_kind = str(getattr(defn.syntax, 'kind', ''))
                    if 'Interface' in syntax_kind:
                        interfaces.append(defn)
        
        return interfaces

    def get_modport_declarations(self, interface) -> List:
        """获取 interface 的 modport 声明 (Semantic AST)"""
        modports = []
        if not interface:
            return modports
        
        # Get modports from interface.syntax.members
        if hasattr(interface, 'syntax'):
            syntax = interface.syntax
            if hasattr(syntax, 'members') and syntax.members:
                for member in syntax.members:
                    member_kind = str(getattr(member, 'kind', ''))
                    if 'Modport' in member_kind:
                        modports.append(member)
        
        return modports

    def get_modport_info(self, modport) -> dict:
        """获取 modport 详细信息 (名称、方向、端口列表) (Semantic AST)"""
        info = {
            'name': '',
            'direction': '',
            'ports': []
        }
        
        if modport is None:
            return info
        
        try:
            # Get modport name from ModportItem list
            if hasattr(modport, 'items') and modport.items:
                for item in modport.items:
                    item_name = getattr(item, 'name', None)
                    if item_name:
                        info['name'] = str(item_name).strip()
                    
                    # Get port directions from item.ports (AnsiPortListSyntax)
                    if hasattr(item, 'ports') and item.ports:
                        # ports is AnsiPortListSyntax containing: Token(open paren), SeparatedList, Token(close paren)
                        # SeparatedList contains ModportSimplePortList items
                        sep_list = item.ports[1] if len(item.ports) > 1 else None
                        if sep_list and hasattr(sep_list, '__iter__'):
                            for port_item in sep_list:
                                port_kind = getattr(port_item, 'kind', None)
                                port_kind_str = str(port_kind) if port_kind else ''
                                
                                if 'ModportSimplePortList' in port_kind_str:
                                    # direction is on the ModportSimplePortList
                                    direction = getattr(port_item, 'direction', None)
                                    if direction:
                                        info['direction'] = str(direction)
                                    
                                    # ports is AnsiPortListSyntax with ModportNamedPort items
                                    port_names = getattr(port_item, 'ports', None)
                                    if port_names and hasattr(port_names, '__iter__'):
                                        for pn in port_names:
                                            pn_kind = getattr(pn, 'kind', None)
                                            if pn_kind and 'ModportNamedPort' in str(pn_kind):
                                                pn_name = getattr(pn, 'name', None)
                                                if pn_name:
                                                    info['ports'].append(str(pn_name).strip())
        except Exception as e:
            pass
        
        return info

    def get_generate_instances(self) -> List:
        """获取 generate 实例 (Semantic AST 暂不支持 generate 语法)

        Args:
            trees: 兼容 SyntaxTree 接口,此参数被忽略

        Returns:
            空列表 (Semantic AST 不单独处理 generate)
        """
        return []

    def get_instance_connection(self, instance) -> List:
        """获取实例的端口连接

        Semantic AST: 从 InstanceSymbol.portConnections 获取
        Returns:
            [(port_name, signal_name), ...]
        """
        connections = []

        # 如果是包装器,从 _symbol 获取
        if hasattr(instance, '_symbol'):
            inst_sym = instance._symbol
        else:
            inst_sym = instance

        # Semantic AST: InstanceSymbol 有 portConnections 属性
        if hasattr(inst_sym, 'portConnections'):
            for conn in inst_sym.portConnections:
                # port 属性有 name
                port_name = '?'
                if hasattr(conn, 'port') and hasattr(conn.port, 'name'):
                    port_name = str(conn.port.name)

                # expression 是 NamedValue,其 symbol 是信号
                # 也可能是 Assignment 表达式 (用于 output 端口连接，如 .q(signal))
                signal_name = '?'
                if hasattr(conn, 'expression') and hasattr(conn.expression, 'symbol'):
                    # NamedValue expression
                    signal_name = str(conn.expression.symbol.name)
                elif hasattr(conn, 'expression'):
                    expr = conn.expression
                    # Check if it's an Assignment expression (output port connection)
                    expr_kind = str(getattr(expr, 'kind', ''))
                    if 'Assignment' in expr_kind:
                        # For Assignment expression (.q(signal)), signal is in left side
                        left = getattr(expr, 'left', None)
                        if left and hasattr(left, 'symbol'):
                            signal_name = str(left.symbol.name)

                if port_name != '?' and signal_name != '?':
                    connections.append((port_name, signal_name))

        return connections

    # =========================================================================
    # 端口相关
    # =========================================================================

    def get_port_declarations(self, module) -> List:
        """获取模块的端口声明

        Semantic AST: 从 DefinitionSymbol.body 遍历查找 PortSymbol
        """
        ports = []

        # DefinitionSymbol 有 body 属性,遍历其成员
        if hasattr(module, 'body') and module.body:
            body = module.body
            for member in body:
                kind_str = str(getattr(member, 'kind', ''))
                if 'Port' in kind_str:
                    ports.append(member)

        return ports

    def get_port_names(self, module) -> List[str]:
        """获取模块的端口名称列表"""
        ports = self.get_port_declarations(module)
        names = []
        for port in ports:
            name = getattr(port, 'name', None)
            if name:
                names.append(str(name))
        return names

    def get_port_name(self, port_decl) -> str:
        """获取单个端口声明的名称"""
        name = getattr(port_decl, 'name', None)
        if name:
            return str(name)
        return 'unknown'

    def get_port_name_and_direction(self, port_decl) -> tuple:
        """获取端口名称和方向

        Returns:
            (name: str, direction: str) - direction: 'input', 'output', 'inout'
        """
        name = None
        direction = 'input'  # 默认

        if hasattr(port_decl, 'name'):
            name = str(port_decl.name)

        # 检查端口方向
        if hasattr(port_decl, 'direction'):
            dir_val = port_decl.direction
            if hasattr(dir_val, 'name'):
                dir_str = str(dir_val.name).lower()
                # [FIX] Check inout BEFORE output, since 'inout' contains 'out'
                if 'inout' in dir_str:
                    direction = 'inout'
                elif 'out' in dir_str:
                    direction = 'output'
                else:
                    direction = 'input'

        return (name, direction)

    def extract_port_width(self, port_decl, scope=None) -> tuple:
        """提取端口位宽

        Uses the semantic type.range (which has resolved left/right values)
        rather than declaredType.width (which only works for literal integers).

        Returns:
            (width: int, msb: int, lsb: int)
        """
        # Semantic AST: use port.type which has pre-resolved range from compiler
        port_type = getattr(port_decl, 'type', None)
        if port_type:
            # PackedArrayType has range with left/right already evaluated
            if hasattr(port_type, 'range') and port_type.range:
                r = port_type.range
                left = int(r.left) if hasattr(r.left, 'value') else int(r.left)
                right = int(r.right) if hasattr(r.right, 'value') else int(r.right)
                msb = max(left, right)
                lsb = min(left, right)
                return (msb, lsb)
            # ScalarType -> 1 bit
            elif hasattr(port_type, 'kind') and 'ScalarType' in str(port_type.kind):
                return (1, 0)

        # Fallback: try declaredType.width for literal values
        declared_type = getattr(port_decl, 'declaredType', None)
        if declared_type:
            if hasattr(declared_type, 'width'):
                w = declared_type.width
                if hasattr(w, 'value') and w.value is not None:
                    try:
                        v = int(w.value)
                        return (v, 0, v - 1)
                    except (ValueError, TypeError):
                        pass

        # 默认 1 位
        return (1, 0, 0)

    # =========================================================================
    # 赋值语句
    # =========================================================================

    def get_assignments(self, module) -> List:
        """获取模块的连续赋值语句

        Semantic AST: 遍历 always_ff/always_comb/连续赋值
        """
        assignments = []

        def find_assignments(node):
            if node is None:
                return
            kind = str(getattr(node, 'kind', ''))

            # ContinuousAssign 语法
            if 'ContinuousAssign' in kind:
                assignments.append(node)
            # AssignmentExpression (procedural)
            elif 'AssignmentExpression' in kind:
                assignments.append(node)

            # 递归遍历子节点
            for child in self._iter_children(node):
                find_assignments(child)

        if hasattr(module, 'body') and module.body:
            for member in module.body:
                find_assignments(member)

        return assignments

    # =========================================================================
    # Always 块
    # =========================================================================

    def get_always_blocks(self, module) -> List:
        """获取模块的 always_ff/always_comb/always_latch 块

        Semantic AST: ProceduralBlockSymbol
        """
        always_blocks = []

        if hasattr(module, 'body') and module.body:
            for member in module.body:
                kind = str(getattr(member, 'kind', ''))
                if 'ProceduralBlock' in kind:
                    always_blocks.append(member)

        return always_blocks

    # =========================================================================
    # Task 和 Function
    # =========================================================================

    def get_task_declarations(self, module) -> List:
        """获取模块的 task 声明"""
        tasks = []

        if hasattr(module, 'body') and module.body:
            for member in module.body:
                kind = str(getattr(member, 'kind', ''))
                # Semantic AST: SubroutineSymbol has kind=SymbolKind.Subroutine
                # Use subroutineKind to determine if it's a Task or Function
                if 'Subroutine' in kind:
                    sk = getattr(member, 'subroutineKind', None)
                    if sk and 'Task' in str(sk):
                        tasks.append(member)
                elif 'Task' in kind:
                    tasks.append(member)

        return tasks

    def get_function_declarations(self, module) -> List:
        """获取模块的 function 声明"""
        funcs = []

        if hasattr(module, 'body') and module.body:
            for member in module.body:
                kind = str(getattr(member, 'kind', ''))
                # Semantic AST: SubroutineSymbol with subroutineKind=Function
                if 'Subroutine' in kind:
                    sk = getattr(member, 'subroutineKind', None)
                    if sk and 'Function' in str(sk):
                        funcs.append(member)
                elif 'Function' in kind:
                    funcs.append(member)

        return funcs

    def get_task_name(self, task) -> str:
        """获取 task 名称"""
        return str(getattr(task, 'name', 'unknown'))

    def get_function_name(self, func) -> str:
        """获取 function 名称"""
        return str(getattr(func, 'name', 'unknown'))

    # =========================================================================
    # 参数相关
    # =========================================================================

    def get_module_parameters(self, module) -> List:
        """获取模块的参数声明"""
        params = []

        if hasattr(module, 'body') and module.body:
            for member in module.body:
                kind = str(getattr(member, 'kind', ''))
                if 'Parameter' in kind:
                    # 返回 dict 格式以兼容现有代码
                    param_name = getattr(member, 'name', None)
                    param_value = getattr(member, 'value', None)
                    if param_name:
                        params.append({
                            'name': str(param_name),
                            'value': str(param_value) if param_value else ''
                        })

        return params

    # =========================================================================
    # 信号和驱动相关
    # =========================================================================

    def get_drivers(self, signal_name: str) -> List:
        """获取信号的驱动源 (Semantic AST 暂不支持)"""
        return []

    def get_loads(self, signal_name: str) -> List:
        """获取信号的负载 (Semantic AST 暂不支持)"""
        return []

    def get_net_declarations(self, module) -> List:
        """获取模块的 net/wire 声明"""
        nets = []

        if hasattr(module, 'body') and module.body:
            for member in module.body:
                kind = str(getattr(member, 'kind', ''))
                if 'Net' in kind:
                    nets.append(member)

        return nets

    def get_variable_declarations(self, module) -> List:
        """获取模块的变量声明"""
        vars = []

        if hasattr(module, 'body') and module.body:
            for member in module.body:
                kind = str(getattr(member, 'kind', ''))
                if 'Variable' in kind or 'Net' in kind:
                    vars.append(member)

        return vars

    def get_data_declarations(self, module) -> List:
        """获取模块的数据声明 (wire, reg, logic 等)"""
        decls = []

        if hasattr(module, 'body') and module.body:
            for member in module.body:
                kind = str(getattr(member, 'kind', ''))
                if 'DataDeclaration' in kind or 'Net' in kind or 'Variable' in kind:
                    decls.append(member)

        return decls

    def get_signal_name(self, signal) -> str:
        """获取信号名称"""
        if hasattr(signal, 'name'):
            return str(signal.name)
        return 'unknown'

    def get_task_params(self, task) -> List:
        """获取 task 的参数列表
        
        Semantic AST: SubroutineSymbol.arguments is a list of FormalArgument symbols
        Each FormalArgument has name, direction, and declaredType
        """
        params = []
        
        if hasattr(task, 'arguments'):
            for arg in task.arguments:
                param_info = {
                    'name': getattr(arg, 'name', 'unknown'),
                    'direction': str(getattr(arg, 'direction', 'None')),
                    'width': (0, 0),  # TODO: extract from declaredType
                }
                params.append(param_info)
        
        return params

    def analyze_task_internal_drivers(self, task) -> Dict:
        """分析 task 内部的驱动
        
        Semantic AST: SubroutineSymbol.body contains the task body statements
        Find assignments to output parameters
        
        Returns:
            Dict: {param_name: [rhs_signal_names]}
        """
        drivers = {}
        
        # Get task body
        body = getattr(task, 'body', None)
        if not body:
            return drivers
        
        # Check if body is a Statement
        stmt_kind = getattr(body, 'kind', None)
        
        # Handle ExpressionStatement wrapping an AssignmentExpression
        # e.g., out = in + 1
        if 'ExpressionStatement' in str(stmt_kind):
            expr = getattr(body, 'expr', None)
            if expr and 'Assignment' in str(expr.kind):
                lhs = getattr(expr, 'left', None)
                rhs = getattr(expr, 'right', None)
                
                if lhs and rhs:
                    # Get the left-hand side symbol (should be a FormalArgument)
                    lhs_sym = getattr(lhs, 'symbol', None)
                    if lhs_sym:
                        lhs_name = getattr(lhs_sym, 'name', None)
                        if lhs_name:
                            # Extract RHS signal names
                            rhs_signals = self._extract_signals_from_expr(rhs)
                            drivers[lhs_name] = rhs_signals
        
        return drivers

    def _extract_signals_from_expr(self, expr) -> List[str]:
        """从表达式中提取所有信号名称"""
        signals = []
        if expr is None:
            return signals
        
        kind_str = str(getattr(expr, 'kind', ''))
        
        # NamedValue: direct signal reference
        if 'NamedValue' in kind_str:
            sym = getattr(expr, 'symbol', None)
            if sym:
                sig_name = getattr(sym, 'name', None)
                if sig_name:
                    signals.append(sig_name)
        
        # Binary/Unary expressions: recurse into left/right operands
        elif 'Binary' in kind_str:
            left = getattr(expr, 'left', None)
            right = getattr(expr, 'right', None)
            if left:
                signals.extend(self._extract_signals_from_expr(left))
            if right:
                signals.extend(self._extract_signals_from_expr(right))
        
        elif 'Unary' in kind_str:
            operand = getattr(expr, 'operand', None)
            if operand:
                signals.extend(self._extract_signals_from_expr(operand))
        
        elif 'Conversion' in kind_str:
            operand = getattr(expr, 'operand', None)
            if operand:
                signals.extend(self._extract_signals_from_expr(operand))
        
        return signals

    def get_interface_modport_signals(self, interface, modport=None) -> List:
        """获取 interface 的 modport 信号 (Semantic AST 暂不支持)"""
        return []

    def get_interface_members(self, interface_port_symbol) -> List[str]:
        """获取 interface 端口的成员信号列表
        
        Args:
            interface_port_symbol: InterfacePortSymbol (from body.lookupName('ifc'))
            
        Returns:
            List[str]: 成员信号名称列表，如 ['data', 'valid']
        """
        members = []
        
        try:
            # Get interface definition from InterfacePortSymbol
            iface_def = getattr(interface_port_symbol, 'interfaceDef', None)
            if not iface_def:
                return members
            
            # Get members from syntax.members
            if hasattr(iface_def, 'syntax'):
                syntax = iface_def.syntax
                if hasattr(syntax, 'members'):
                    for m in syntax.members:
                        # DataDeclarationSyntax has declarators
                        if hasattr(m, 'declarators'):
                            for decl in m.declarators:
                                if hasattr(decl, 'name'):
                                    name = decl.name
                                    if hasattr(name, 'value'):
                                        members.append(str(name.value).strip())
                                    else:
                                        members.append(str(name).strip())
        except Exception as e:
            pass
        
        return members

    def get_function_params(self, func) -> List:
        """获取 function 的参数列表

        Semantic AST: FormalArgument symbols with direction and name
        Returns: List[Tuple[str, str]] - [(direction, name), ...]
        """
        params = []
        for arg in getattr(func, 'arguments', []):
            direction = str(getattr(arg, 'direction', 'Input')).split('.')[-1].lower()
            name = getattr(arg, 'name', 'unknown')
            if name:
                params.append((direction, str(name)))
        return params

    def analyze_task_internal_drivers(self, task_or_func) -> Dict:
        """分析 task/function 内部的驱动关系
        
        Handles:
        1. Functions: assignment to function name (implicit return)
        2. Tasks with output parameters: assignment to parameter name
        3. For loops, while loops, if-else inside tasks
        
        Returns:
            Dict: {var_name: [rhs_signal_names]}
        """
        drivers = {}
        func_name = getattr(task_or_func, 'name', None)
        if not func_name:
            return drivers
        func_name = str(func_name)

        body = getattr(task_or_func, 'body', None)
        if not body:
            return drivers

        # Recursively collect assignment statements from the body
        self._collect_drivers_from_stmt(body, func_name, drivers)

        return drivers

    def _collect_drivers_from_stmt(self, stmt, func_name, drivers):
        """Recursively collect driver information from statements"""
        if stmt is None:
            return
        
        stmt_kind = str(getattr(stmt, 'kind', ''))
        
        # ExpressionStatement: assignment like out = in + 1
        if 'ExpressionStatement' in stmt_kind:
            expr = getattr(stmt, 'expr', None)
            if expr and 'Assignment' in str(getattr(expr, 'kind', '')):
                self._extract_assignment_drivers(expr, func_name, drivers)
            return
        
        # BlockStatement: begin...end block containing multiple statements
        if 'Block' in stmt_kind and 'Statement' in stmt_kind:
            body = getattr(stmt, 'body', None)
            if body:
                # Handle StatementList
                stmt_list = getattr(body, 'list', None) or list(body) if hasattr(body, '__iter__') else [body]
                for s in stmt_list:
                    self._collect_drivers_from_stmt(s, func_name, drivers)
            return
        
        # ForLoopStatement: for (...) statement
        if 'ForLoop' in stmt_kind:
            for_body = getattr(stmt, 'body', None)
            if for_body:
                self._collect_drivers_from_stmt(for_body, func_name, drivers)
            return
        
        # WhileLoopStatement: while (...) statement
        if 'WhileLoop' in stmt_kind:
            while_body = getattr(stmt, 'body', None)
            if while_body:
                self._collect_drivers_from_stmt(while_body, func_name, drivers)
            return
        
        # ConditionalStatement: if (...) statement or if (...) ... else ...
        if 'Conditional' in stmt_kind and 'Statement' in stmt_kind:
            # Handle ifTrue (then branch)
            if_true = getattr(stmt, 'ifTrue', None) or getattr(stmt, 'statement', None)
            if if_true:
                self._collect_drivers_from_stmt(if_true, func_name, drivers)
            # Handle ifFalse (else branch)
            if_false = getattr(stmt, 'ifFalse', None)
            if if_false:
                self._collect_drivers_from_stmt(if_false, func_name, drivers)
            return
        
        # SequentialBlock: begin...end in procedural context
        if 'SequentialBlock' in stmt_kind:
            items = getattr(stmt, 'items', None)
            if items:
                for s in items:
                    self._collect_drivers_from_stmt(s, func_name, drivers)
            return
        
        # ForkStatement: fork...join for parallel statements
        if 'Fork' in stmt_kind:
            items = getattr(stmt, 'items', None)
            if items:
                for s in items:
                    self._collect_drivers_from_stmt(s, func_name, drivers)
            return
        
        # StatementList: list of statements inside a block (from pyslang)
        if 'List' in stmt_kind and 'Statement' in stmt_kind:
            stmt_list = getattr(stmt, 'list', None)
            if stmt_list:
                for s in stmt_list:
                    self._collect_drivers_from_stmt(s, func_name, drivers)
            return

    def _extract_assignment_drivers(self, expr, func_name, drivers):
        """Extract driver info from an AssignmentExpression"""
        lhs = getattr(expr, 'left', None)
        rhs = getattr(expr, 'right', None)
        
        if not lhs or not rhs:
            return
        
        # Get the left-hand side symbol and name
        # Handle both direct NamedValue and ElementSelect (signal[bit])
        lhs_symbol = getattr(lhs, 'symbol', None)
        lhs_name = None
        
        if lhs_symbol:
            lhs_name = getattr(lhs_symbol, 'name', None)
        else:
            # Maybe it's an ElementSelect - check .value.symbol
            lhs_value = getattr(lhs, 'value', None)
            if lhs_value:
                lhs_symbol = getattr(lhs_value, 'symbol', None)
                if lhs_symbol:
                    lhs_name = getattr(lhs_symbol, 'name', None)
        
        if not lhs_name:
            return
        
        # Extract RHS signal names
        rhs_signals = self._extract_signals_from_expr(rhs)
        
        # Only update if we have actual signal sources (not just literals)
        # This prevents overwriting real drivers with empty results from literals
        if rhs_signals:
            drivers[lhs_name] = rhs_signals

    def _extract_signals_from_expr(self, expr) -> List[str]:
        """从表达式中提取所有信号名

        Handles:
        - NamedValue: signal reference
        - ElementSelect: signal[bit] -> extract signal name
        - RangeSelect: signal[msb:lsb] -> extract signal name
        - Concatenation: {a, b, c}
        - BinaryExpression: a ^ b, a + b, etc.
        - UnaryExpression
        - IntegerLiteral: index value (not a signal)
        """
        signals = []
        if expr is None:
            return signals

        kind = getattr(expr, 'kind', None)
        if not kind:
            return signals

        kind_str = str(kind)

        # NamedValue: signal reference
        if 'NamedValue' in kind_str:
            sym = getattr(expr, 'symbol', None)
            if sym:
                name = getattr(sym, 'name', None)
                if name:
                    signals.append(str(name))
            return signals

        # Concatenation: {a, b, c}
        if 'Concatenation' in kind_str:
            for op in getattr(expr, 'operands', []):
                signals.extend(self._extract_signals_from_expr(op))
            return signals

        # BinaryExpression: a ^ b, a + b, etc.
        if 'Binary' in kind_str:
            signals.extend(self._extract_signals_from_expr(getattr(expr, 'left', None)))
            signals.extend(self._extract_signals_from_expr(getattr(expr, 'right', None)))
            return signals

        # UnaryExpression
        if 'Unary' in kind_str:
            signals.extend(self._extract_signals_from_expr(getattr(expr, 'operand', None)))
            return signals

        # ConversionExpression (type casting) - recurse into operand
        if 'Conversion' in kind_str:
            signals.extend(self._extract_signals_from_expr(getattr(expr, 'operand', None)))
            return signals

        # ElementSelect: signal[bit] - extract full name signal[bit]
        if 'ElementSelect' in kind_str:
            # Get the base signal
            base_signals = self._extract_signals_from_expr(getattr(expr, 'value', None))
            # Get the selector (bit index)
            selector = getattr(expr, 'selector', None)
            if selector and base_signals:
                # selector is an expression (IntegerLiteral or ParameterExpression)
                sel_kind = getattr(selector, 'kind', None)
                if sel_kind:
                    sel_kind_str = str(sel_kind)
                    if 'IntegerLiteral' in sel_kind_str:
                        # Get the integer value
                        sel_val = getattr(selector, 'value', None)
                        if sel_val is not None:
                            for base in base_signals:
                                signals.append(f"{base}[{sel_val}]")
                            return signals
                    elif 'Parameter' in sel_kind_str:
                        # Parameter expression - try to get value
                        try:
                            sel_val = str(selector)  # Fallback to string representation
                        except:
                            sel_val = getattr(selector, 'name', None) or str(selector)
                        for base in base_signals:
                            signals.append(f"{base}[{sel_val}]")
                        return signals
            # Fallback: just return base signal
            return base_signals

        # RangeSelect: signal[msb:lsb] - extract full name signal[msb:lsb]
        if 'RangeSelect' in kind_str:
            # Get the base signal
            base_signals = self._extract_signals_from_expr(getattr(expr, 'value', None))
            # Get the range (left/right or selector with left/right)
            left = getattr(expr, 'left', None)
            right = getattr(expr, 'right', None)
            if not left or not right:
                # Maybe stored as selector with left/right
                selector = getattr(expr, 'selector', None)
                if selector:
                    left = getattr(selector, 'left', None)
                    right = getattr(selector, 'right', None)
            if left and right:
                left_val = getattr(left, 'value', None)
                right_val = getattr(right, 'value', None)
                for base in base_signals:
                    if left_val is not None and right_val is not None:
                        signals.append(f"{base}[{left_val}:{right_val}]")
                    else:
                        signals.append(f"{base}[?:?]")
                return signals
            # Fallback: just return base signal
            return base_signals

        # IntegerLiteral: not a signal
        if 'IntegerLiteral' in kind_str:
            return signals

        return signals

    def extract_data_width(self, data_decl) -> tuple:
        """提取数据声明的位宽 (wire, reg, logic 等)"""
        # Semantic AST: 尝试从 declaredType 获取位宽
        declared_type = getattr(data_decl, 'declaredType', None)
        if declared_type:
            if hasattr(declared_type, 'width'):
                w = declared_type.width
                if hasattr(w, 'value'):
                    return (int(w.value), 0, int(w.value) - 1)

        # 默认 1 位
        return (1, 0, 0)

    # =========================================================================
    # 遍历
    # =========================================================================

    def visit(self, callback: Callable):
        """遍历 Semantic AST 所有节点"""
        self._root.visit(callback)

    def visit_module(self, module, callback: Callable):
        """遍历模块的所有节点"""
        if hasattr(module, 'body') and module.body:
            module.body.visit(callback)

    def _iter_children(self, node) -> List:
        """安全遍历子节点"""
        if node is None:
            return []

        children = []

        # 处理可迭代对象
        if hasattr(node, '__iter__') and not isinstance(node, (str, bytes)):
            try:
                for child in node:
                    children.append(child)
            except:
                pass

        # 处理常见属性
        for attr in ['members', 'body', 'statement', 'statements',
                     'left', 'right', 'expr', 'condition', 'consequent', 'alternate']:
            child = getattr(node, attr, None)
            if child:
                if isinstance(child, list):
                    children.extend(child)
                elif hasattr(child, 'kind'):
                    children.append(child)

        return children

    # =========================================================================
    # 工具方法
    # =========================================================================

    def clean_name(self, name: str) -> str:
        """清理信号名称 (移除多余空白等)"""
        if not name:
            return ''
        return ' '.join(name.split()).strip()

    def iter_modules(self) -> Iterator:
        """迭代模块 (InstanceSymbol)"""
        for item in self._root:
            if hasattr(item, 'kind'):
                kind_str = str(item.kind)
                if 'Instance' in kind_str:
                    yield item

    def get_definition(self, name: str):
        """获取模块/类定义"""
        for item in self._root:
            if hasattr(item, 'name') and item.name == name:
                return item
        return None


# =============================================================================
# Semantic AST 实例包装器 - 兼容 GraphBuilder 的实例期望
# =============================================================================

class SemanticInstanceWrapper:
    """
    Semantic AST 实例包装器

    将 Semantic AST InstanceSymbol 适配为 GraphBuilder 期望的接口格式。
    这样可以在不修改 GraphBuilder 的情况下使用 Semantic AST。
    """

    def __init__(self, instance_symbol, parent_module=None):
        self._symbol = instance_symbol
        self.name = instance_symbol.name
        self.type = type('TypeToken', (), {'value': self._get_module_type()})()
        self.parent_module = parent_module  # 父模块名

        # 构造 .instances[0].decl.name 结构供 GraphBuilder 使用
        self.instances = [SemanticInstanceDeclWrapper(instance_symbol)]

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return f"SemanticInstanceWrapper({self.name})"

    def _get_module_type(self) -> str:
        """获取模块类型名"""
        if hasattr(self._symbol, 'definition'):
            defn = self._symbol.definition
            if hasattr(defn, 'name'):
                return str(defn.name)
        return str(self.name)

    def get_parent_module(self) -> str:
        """获取父模块名,供 GraphBuilder._get_parent_module_name 使用"""
        return self.parent_module or 'top'

    def _get_parent_module_safe(self) -> str:
        """安全获取父模块名,用于 GraphBuilder 的 _get_parent_module_name 兼容

        这个方法模拟 GraphBuilder._get_parent_module_name 的行为,
        但在 parent 为 None 时返回 type.value(模块类型名)而非 'unknown'。
        """
        if self.parent_module:
            return self.parent_module
        # 对于顶级模块,parent 为 None,此时返回 type.value(即模块类型名)
        # 这样 inst_module_name 就能正确设为 'top'
        return self.type.value if self.type.value else str(self.name)

    @property
    def parent(self):
        """兼容属性:返回类似 SyntaxTree 的 parent 节点结构

        对于顶级模块(parent_module is None),返回 None
        这样 _get_parent_module_name 会使用 fallback 逻辑。
        """
        if self.parent_module:
            class ParentModule:
                def __init__(self, name):
                    self.name = name
                    self.header = type('Header', (), {'name': type('Name', (), {'rawText': name})()})()
            return ParentModule(self.parent_module)
        return None


class SemanticInstanceDeclWrapper:
    """包装 InstanceSymbol 的 declaration 部分"""

    def __init__(self, instance_symbol):
        self._symbol = instance_symbol

    @property
    def name(self):
        """返回实例名称作为 TokenValue"""
        class TokenValue:
            def __init__(self, val):
                self.value = val
        return TokenValue(self._symbol.name)