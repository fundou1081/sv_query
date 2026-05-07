from pyslang import SyntaxKind
#==============================================================================
# base.py - AST Walker 基类
# 公共 AST 遍历基础设施
#==============================================================================

from typing import Callable, Optional, List, Any
from abc import ABC, abstractmethod

class ASTWalker:
    """公共AST遍历基类"""
    
    def __init__(self, parser=None):
        self.parser = parser
    
    def walk_all(self, callback: Callable):
        """遍历所有文件的AST"""
        if not self.parser or not hasattr(self.parser, 'trees'):
            return
            
        for fname, tree in self.parser.trees.items():
            if not tree or not tree.root:
                continue
            self._visit_node(tree.root, callback)
    
    def walk_file(self, fname: str, callback: Callable):
        """遍历单个文件的AST"""
        if not self.parser or not hasattr(self.parser, 'trees'):
            return
            
        tree = self.parser.trees.get(fname)
        if tree and tree.root:
            self._visit_node(tree.root, callback)
    
    def _visit_node(self, node, callback: Callable):
        """递归访问节点"""
        if node is None:
            return
        
        # 调用回调
        callback(node)
        
        # 遍历子节点
        children = self.iter_children(node)
        for child in children:
            self._visit_node(child, callback)
    
    def iter_children(self, node) -> List:
        """安全遍历子节点"""
        if node is None:
            return []
        
        # 通用属性访问
        if hasattr(node, 'children'):
            return node.children
        elif hasattr(node, 'members'):
            return node.members
        elif hasattr(node, 'body'):
            return node.body
        
        return []


#==============================================================================
class PyslangAdapter:
    """pyslang 适配器 - 将 pyslang AST 转换为内部表示"""
    
    def __init__(self, parser):
        self.parser = parser
        self._cache = {}
    
    def get_module_name(self, module) -> str:
        """获取模块名"""
        # 方式1: header.name
        if hasattr(module, 'header') and module.header:
            if hasattr(module.header, 'name'):
                name = module.header.name
                name_str = name.value if hasattr(name, 'value') else str(name)
                result = name_str.strip() if name_str else None
                if result:
                    return result
        
        # 方式2: 直接 module.name
        if hasattr(module, 'name'):
            n = module.name
            name_str = n.value if hasattr(n, 'value') else str(n)
            result = name_str.strip() if name_str else None
            if result:
                return result
        
        return "unknown"
    
    def clean_name(self, name) -> str:
        """清理名称：去除前后空格和换行"""
        if not name:
            return ""
        s = str(name).strip()
        # 去除多余空白
        s = ' '.join(s.split())
        return s
    
    def get_modules(self) -> List:
        """获取所有模块"""
        modules = []
        for fname, tree in self.parser.trees.items():
            if tree and hasattr(tree, 'root'):
                modules.extend(self._extract_modules(tree.root))
        return modules
    
    def _extract_modules(self, node) -> List:
        """提取模块"""
        modules = []
        if node is None:
            return modules
            
        # 检查是否是 ModuleDeclaration
        if hasattr(node, 'kind'):
            if node.kind == SyntaxKind.ModuleDeclaration:
                modules.append(node)
        
        # 递归子节点
        for child in self.iter_children(node):
            modules.extend(self._extract_modules(child))
        
        return modules
    
    def iter_children(self, node) -> List:
        return ASTWalker.iter_children(self, node)
    
    def get_module(self, name: str):
        """按名称获取模块"""
        for module in self.get_modules():
            if hasattr(module, 'name') and module.name == name:
                return module
        return None
    
    def get_modport_declarations(self, module) -> List:
        """获取 modport 声明"""
        modports = []
        if not module:
            return modports
        
        # 查找 ModportDeclaration
        def find_modport(node):
            if node is None:
                return
            kind = getattr(node, 'kind', None)
            if kind and 'Modport' in str(kind):
                modports.append(node)
            for attr in ['members', 'body']:
                if hasattr(node, attr):
                    child = getattr(node, attr)
                    if hasattr(child, '__iter__') and not isinstance(child, str):
                        for c in child:
                            find_modport(c)
        
        if hasattr(module, '__iter__') and not isinstance(module, str):
            for m in module:
                find_modport(m)
        else:
            find_modport(module)
        
        return modports
    
    # 现有的 get_port_declarations
    def get_port_declarations(self, module) -> List:
        """获取端口声明 - 从 header.ports 遍历"""
        ports = []
        if not module:
            return ports
        
        # pyslang: module.header.ports 是 AnsiPortListSyntax [paren, list, paren]
        if hasattr(module, 'header') and module.header:
            header = module.header
            if hasattr(header, 'ports'):
                port_list = header.ports
                # port_list[1] 是实际的端口列表
            if port_list and len(port_list) > 1:
                    actual_ports = port_list[1]
                    if hasattr(actual_ports, 'elements'):
                        for port in actual_ports.elements:
                            if hasattr(port, 'kind') and port.kind == SyntaxKind.ImplicitAnsiPort:
                                ports.append(port)
                    elif hasattr(actual_ports, '__iter__'):
                        for port in actual_ports:
                            if hasattr(port, 'kind') and port.kind == SyntaxKind.ImplicitAnsiPort:
                                ports.append(port)
        
        return ports
    

    def get_port_names(self, module) -> List[str]:
        """获取端口名称列表"""
        ports = []
        port_decls = self.get_port_declarations(module)
        for port in port_decls:
            name, direction = self.get_port_name_and_direction(port)
            if name:
                ports.append(name)
        return ports

    def get_port_name_and_direction(self, port) -> tuple:
        """获取端口名称和方向 (name, direction)"""
        if not port:
            return None, 'unknown'
        
        # 名称: port.declarator.name
        name = None
        if hasattr(port, 'declarator') and port.declarator:
            decl = port.declarator
            if hasattr(decl, 'name'):
                n = decl.name
                name = n.value if hasattr(n, 'value') else str(n)
        
        # 方向: port.header.direction
        direction = 'unknown'
        if hasattr(port, 'header') and port.header:
            header = port.header
            if hasattr(header, 'direction'):
                direction = str(header.direction)
        
        return name, direction
    
    def _extract_bit_width(self, node) -> tuple:
        """提取信号位宽 (MSB, LSB)"""
        # 默认宽度
        msb, lsb = 0, 0
        
        # 尝试从 dims 获取
        if hasattr(node, 'dims') and node.dims:
            dims = node.dims
            if hasattr(dims, '__iter__') and not isinstance(dims, str):
                for dim in dims:
                    if hasattr(dim, 'range'):
                        rng = dim.range
                        if rng:
                            # 查看范围
                            if hasattr(rng, 'left'):
                                left = rng.left
                                msb = int(str(left.value)) if hasattr(left, 'value') else 0
                            if hasattr(rng, 'right'):
                                right = rng.right
                                lsb = int(str(right.value)) if hasattr(right, 'value') else 0
                            return (msb, lsb)
        return (msb, lsb)

    
    def get_module_instances(self, trees: dict = None) -> List:
        """获取模块实例化"""
        instances = []
        
        for fname, tree in (trees or {}).items():
            if not tree or not hasattr(tree, 'root'):
                continue
            
            # 遍历找 HierarchicalInstance
            def find_inst(node):
                if node is None:
                    return
                kind = getattr(node, 'kind', None)
                if kind and 'Instance' in str(kind) and hasattr(node, 'decl'):
                    instances.append(node)
                for attr in dir(node):
                    if attr.startswith('_') or attr in ['parent', 'sourceRange']:
                        continue
                    try:
                        child = getattr(node, attr)
                        if callable(child):
                            continue
                        if hasattr(child, '__iter__') and not isinstance(child, str):
                            for c in child:
                                find_inst(c)
                        elif hasattr(child, 'kind'):
                            find_inst(child)
                    except:
                        pass
            
            find_inst(tree.root)
        
        return instances
    

    def get_instance_connection(self, instance) -> List:
        """获取实例的端口连接 [(port_name, signal_name), ...]"""
        connections = []
        
        if not hasattr(instance, 'connections'):
            return connections
        
        conn_attr = instance.connections
        
        # 方式1: connections 是 SyntaxNode (pyslang 对象)
        if hasattr(conn_attr, 'kind'):
            kind_str = str(conn_attr.kind)
            
            if 'SeparatedList' in kind_str:
                idx = 0
                for item in conn_attr:
                    if hasattr(item, 'kind') and 'Token' in str(item.kind):
                        continue
                    
                    if hasattr(item, 'kind') and 'OrderedPort' in str(item.kind):
                        if hasattr(item, 'expr'):
                            expr = item.expr
                            signal_name = expr.value if hasattr(expr, 'value') else str(expr)
                            if signal_name:
                                connections.append(('_pos_' + str(idx), signal_name))
                                idx += 1
                    
                    elif hasattr(item, 'kind') and 'NamedPort' in str(item.kind):
                        port_name = None
                        signal_name = None
                        if hasattr(item, 'name'):
                            n = item.name
                            port_name = n.value if hasattr(n, 'value') else str(n)
                        if hasattr(item, 'expr'):
                            e = item.expr
                            signal_name = e.value if hasattr(e, 'value') else str(e)
                        if port_name and signal_name:
                            connections.append((port_name, signal_name))
        
        elif isinstance(conn_attr, str):
            conn_str = conn_attr.strip()
            if not conn_str:
                return connections
            
            if conn_str.startswith('(') and conn_str.endswith(')'):
                conn_str = conn_str[1:-1]
            
            if conn_str.startswith('.'):
                import re
                pattern = r'\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)'
                matches = re.findall(pattern, conn_str)
                for pn, sn in matches:
                    if pn and sn:
                        connections.append((pn, sn))
            else:
                parts = [p.strip() for p in conn_str.split(',')]
                for idx, sn in enumerate(parts):
                    if sn:
                        connections.append(('_pos_' + str(idx), sn))
        
        return connections
    def get_data_declarations(self, module) -> List:
        """获取数据声明"""
        return self._get_declarations_by_kind(module, SyntaxKind.DataDeclaration)
    
    def _get_declarations_by_type(self, module, decl_type: str) -> List:
        """按类型获取声明"""
        decls = []
        if not module or not hasattr(module, 'members'):
            return decls
        
        for member in module.members:
            if hasattr(member, 'kind') and member.kind.value == getattr(SyntaxKind, decl_type.replace("PortDeclaration", "PortDeclaration").replace("DataDeclaration", "DataDeclaration"), SyntaxKind.DataDeclaration).value:
                decls.append(member)
        
        return decls
    
    def get_assignments(self, module) -> List:
        """获取赋值语句 (包括连续赋值和数据声明)"""
        stmts = self._get_statements_by_kind(module, SyntaxKind.ContinuousAssign)
        # [P1] DataDeclaration - 包括 class 实例化 my_cls obj = new()
        stmts.extend(self._get_statements_by_kind(module, SyntaxKind.DataDeclaration))
        return stmts
    
    def get_always_blocks(self, module) -> List:
        """获取 always 块"""
        always_blocks = []
        if not module or not hasattr(module, 'members'):
            return always_blocks
        
        for member in module.members:
            if hasattr(member, 'kind'):
                if member.kind in [SyntaxKind.AlwaysBlock, SyntaxKind.AlwaysFFBlock, SyntaxKind.AlwaysCombBlock, SyntaxKind.AlwaysLatchBlock, SyntaxKind.InitialBlock]:
                    always_blocks.append(member)
        
        return always_blocks
    
    def _get_statements_by_kind(self, module, kind: SyntaxKind) -> List:
        """按 SyntaxKind 获取语句"""
        stmts = []
        if not module or not hasattr(module, 'members'):
            return stmts
        
        for member in module.members:
            if hasattr(member, 'kind') and member.kind == kind:
                stmts.append(member)
        
        return stmts
    
    def _get_declarations_by_kind(self, module, kind: SyntaxKind) -> List:
        """按 SyntaxKind 获取声明"""
        decls = []
        if not module or not hasattr(module, 'members'):
            return decls
        
        for member in module.members:
            if hasattr(member, 'kind') and member.kind == kind:
                decls.append(member)
        
        return decls


#==============================================================================
# 具体收集器实现
#==============================================================================

class DriverCollector(ASTWalker):
    """Driver 收集器"""
    
    def __init__(self, parser):
        super().__init__(parser)
        self.drivers = {}  # signal -> [drivers]
        self._collect()
    
    def _collect(self):
        """收集所有驱动关系"""
        def visitor(node):
            self._process_node(node)
        
        self.walk_all(visitor)
    
    def _process_node(self, node):
        """处理节点"""
        if not hasattr(node, 'kind'):
            return
        
        # assign 语句: lhs = rhs
        if node.kind == 'ContinuousAssign':
            self._process_assign(node)
        
        # always 块
        elif node.kind in ['AlwaysFF', 'AlwaysComb', 'AlwaysLatch']:
            self._process_always(node)
    
    def _process_assign(self, node):
        """处理 assign"""
        if not hasattr(node, 'lhs') or not hasattr(node, 'rhs'):
            return
        
        lhs = self._get_signal_name(node.lhs)
        rhs = self._get_signal_name(node.rhs)
        
        if lhs and rhs:
            if lhs not in self.drivers:
                self.drivers[lhs] = []
            self.drivers[lhs].append(rhs)
    
    def _process_always(self, node):
        """处理 always 块"""
        if not hasattr(node, 'body'):
            return
        
        # 简化: 提取阻塞赋值
        for stmt in node.body:
            if hasattr(stmt, 'kind') and stmt.kind == 'BlockingAssign':
                lhs = self._get_signal_name(stmt.lhs)
                rhs = self._get_signal_name(stmt.rhs)
                if lhs and rhs:
                    if lhs not in self.drivers:
                        self.drivers[lhs] = []
                    self.drivers[lhs].append(rhs)
    
    def _get_signal_name(self, node) -> Optional[str]:
        """获取信号名"""
        if node is None:
            return None
        
        if hasattr(node, 'name'):
            return node.name
        elif hasattr(node, 'symbol'):
            return node.symbol
        
        return None
    
    def get_drivers(self, signal: str) -> List[str]:
        return self.drivers.get(signal, [])


class LoadCollector(ASTWalker):
    """Load 收集器"""
    
    def __init__(self, parser):
        super().__init__(parser)
        self.loads = {}  # signal -> [loads]
        self._collect()
    
    def _collect(self):
        def visitor(node):
            self._process_node(node)
        self.walk_all(visitor)
    
    def _process_node(self, node):
        if not hasattr(node, 'kind'):
            return
        
        if node.kind == 'ContinuousAssign':
            if hasattr(node, 'lhs') and hasattr(node, 'rhs'):
                rhs = self._get_signal_name(node.rhs)
                lhs = self._get_signal_name(node.lhs)
                if rhs and lhs:
                    if rhs not in self.loads:
                        self.loads[rhs] = []
                    self.loads[rhs].append(lhs)
    
    def _get_signal_name(self, node) -> Optional[str]:
        if node is None:
            return None
        if hasattr(node, 'name'):
            return node.name
        return None
    
    def get_loads(self, signal: str) -> List[str]:
        return self.loads.get(signal, [])


class ConnectionCollector(ASTWalker):
    """模块端口连接收集器"""
    
    def __init__(self, parser):
        super().__init__(parser)
        self.connections = []  # (module, port, external_signal)
        self._collect()
    
    def _collect(self):
        def visitor(node):
            self._process_node(node)
        self.walk_all(visitor)
    
    def _process_node(self, node):
        if not hasattr(node, 'kind'):
            return
        
        # ModuleInstantiation
        if node.kind == 'ModuleInstantiation':
            self._process_instantiation(node)
    
    def _process_instantiation(self, node):
        if not hasattr(node, 'module') or not hasattr(node, 'port_connections'):
            return
        
        module_name = self._get_signal_name(node.module)
        for port in node.port_connections:
            if hasattr(port, 'port') and hasattr(port, 'signal'):
                self.connections.append((
                    module_name,
                    self._get_signal_name(port.port),
                    self._get_signal_name(port.signal)
                ))
    
    def _get_signal_name(self, node) -> Optional[str]:
        if node is None:
            return None
        if hasattr(node, 'name'):
            return node.name
        return None

    # [P2] case 语句提取
    def get_case_statements(self, module) -> List:
        """获取 case 语句"""
        cases = []
        if not module or not hasattr(module, 'members'):
            return cases
        
        for member in module.members:
            if hasattr(member, 'kind'):
                # CaseStatement 或_case_generate
                kind_str = str(member.kind)
                if 'Case' in kind_str:
                    cases.append(member)
        
        return cases
    
    # [P2] 提取 always 块内的 case 语句
    def get_case_in_always(self, always_block) -> List:
        """从 always 块中提取 case 语句"""
        cases = []
        
        def find_case(node):
            if node is None:
                return
            kind = getattr(node, 'kind', None)
            if kind:
                kind_str = str(kind)
                if 'Case' in kind_str:
                    cases.append(node)
            # 遍历子节点
            for attr in ['body', 'statement', 'cases']:
                if hasattr(node, attr):
                    child = getattr(node, attr)
                    if hasattr(child, '__iter__') and not isinstance(child, str):
                        for c in child:
                            find_case(c)
        
        if always_block:
            find_case(always_block)
        
        return cases
