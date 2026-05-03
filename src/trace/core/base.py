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
#pyslang 接口适配器
#==============================================================================

class PyslangAdapter:
    """pyslang 适配器 - 将 pyslang AST 转换为内部表示"""
    
    def __init__(self, parser):
        self.parser = parser
        self._cache = {}
    
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
            if node.kind == 'ModuleDeclaration':
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
    
    def get_port_declarations(self, module) -> List:
        """获取端口声明"""
        return self._get_declarations_by_type(module, 'PortDeclaration')
    
    def get_data_declarations(self, module) -> List:
        """获取数据声明"""
        return self._get_declarations_by_type(module, 'DataDeclaration')
    
    def _get_declarations_by_type(self, module, decl_type: str) -> List:
        """按类型获取声明"""
        decls = []
        if not module or not hasattr(module, 'members'):
            return decls
        
        for member in module.members:
            if hasattr(member, 'kind') and member.kind == decl_type:
                decls.append(member)
        
        return decls
    
    def get_assignments(self, module) -> List:
        """获取赋值语句"""
        return self._get_statements_by_type(module, 'Assign')
    
    def get_always_blocks(self, module) -> List:
        """获取 always 块"""
        always_blocks = []
        if not module or not hasattr(module, 'members'):
            return always_blocks
        
        for member in module.members:
            if hasattr(member, 'kind'):
                if member.kind in ['AlwaysFF', 'AlwaysComb', 'AlwaysLatch']:
                    always_blocks.append(member)
        
        return always_blocks
    
    def _get_statements_by_type(self, module, stmt_type: str) -> List:
        """按类型获取语句"""
        stmts = []
        if not module or not hasattr(module, 'members'):
            return stmts
        
        for member in module.members:
            if hasattr(member, 'kind') and member.kind == stmt_type:
                stmts.append(member)
        
        return stmts


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
