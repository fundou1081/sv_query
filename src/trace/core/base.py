from pyslang import SyntaxKind, TokenKind
#==============================================================================
# base.py - AST Walker 基类
# 公共 AST 遍历基础设施
#==============================================================================

from typing import Callable, Optional, List, Any, Dict
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
        """获取模块名
        
        优先使用 header.name.value/text
        如果为空（参数化模块的 pyslang bug），从源码提取
        """
        # 方式1: header.name
        if hasattr(module, 'header') and module.header:
            if hasattr(module.header, 'name'):
                name = module.header.name
                name_str = name.value if hasattr(name, 'value') else str(name)
                result = name_str.strip() if name_str else None
                if result:
                    return result
                # name 为空时，尝试 valueText
                name_text = getattr(name, 'valueText', None)
                if name_text:
                    result = name_text.strip()
                    if result:
                        return result
        
        # 方式2: 直接 module.name
        if hasattr(module, 'name'):
            n = module.name
            name_str = n.value if hasattr(n, 'value') else str(n)
            result = name_str.strip() if name_str else None
            if result:
                return result
        
        # 方式3: 从 sourceRange 提取 (修复参数化模块的 pyslang bug)
        try:
            if hasattr(module, 'header') and module.header:
                rng = getattr(module.header, 'sourceRange', None)
                if rng and hasattr(self.parser, 'trees'):
                    for fname, tree in self.parser.trees.items():
                        if tree and hasattr(tree, 'sourceManager'):
                            sm = tree.sourceManager
                            # 获取 header 的位置 (起始位置包含 "module " 后面是名字)
                            start_loc = rng.start
                            # buffer offset 是从 0 开始的
                            buf_id = start_loc.buffer
                            src_text = sm.getSourceText(buf_id)
                            # 从 start offset 开始，找到模块名
                            offset = start_loc.offset
                            if offset > 0 and src_text:
                                # 跳过 "module " 找名字
                                remaining = src_text[offset:]
                                import re
                                m = re.match(r'module\s+(\w+)', remaining)
                                if m:
                                    return m.group(1)
        except Exception:
            pass
        
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
    
    def get_classes(self) -> List:
        """获取所有类声明"""
        classes = []
        for fname, tree in self.parser.trees.items():
            if tree and hasattr(tree, 'root'):
                classes.extend(self._extract_classes(tree.root))
        return classes
    
    def get_interfaces(self) -> List:
        """获取所有接口声明"""
        interfaces = []
        for fname, tree in self.parser.trees.items():
            if tree and hasattr(tree, 'root'):
                interfaces.extend(self._extract_interfaces(tree.root))
        return interfaces
    
    def _extract_classes(self, node) -> List:
        """提取类声明"""
        classes = []
        if node is None:
            return classes
        
        # 检查是否是 ClassDeclaration
        try:
            if hasattr(node, 'kind'):
                if node.kind == SyntaxKind.ClassDeclaration:
                    classes.append(node)
        except (ValueError, AttributeError):
            # pyslang AST 节点可能被垃圾回收导致 kind 访问出错
            pass
        
        # 递归子节点
        try:
            for child in self.iter_children(node):
                classes.extend(self._extract_classes(child))
        except (ValueError, AttributeError, TypeError):
            pass
        
        return classes
    
    def _extract_interfaces(self, node) -> List:
        """提取接口声明"""
        interfaces = []
        if node is None:
            return interfaces
        
        # 检查是否是 InterfaceDeclaration
        try:
            if hasattr(node, 'kind'):
                if node.kind == SyntaxKind.InterfaceDeclaration:
                    interfaces.append(node)
        except (ValueError, AttributeError):
            pass
        
        # 递归子节点
        try:
            for child in self.iter_children(node):
                interfaces.extend(self._extract_interfaces(child))
        except (ValueError, AttributeError, TypeError):
            pass
        
        return interfaces
    
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
        
        # 直接调用 find_modport
        find_modport(module)
        
        return modports
    
    def get_modport_info(self, modport) -> dict:
        """获取 modport 详细信息 (名称、方向、端口列表)"""
        info = {
            'name': '',
            'direction': '',
            'ports': []
        }
        
        if modport is None:
            return info
        
        try:
            # 获取端口信息
            if hasattr(modport, 'items'):
                items = list(modport.items)
                for item in items:
                    # 获取 modport 名称 (在 ModportItem 中)
                    item_name = getattr(item, 'name', None)
                    if item_name:
                        info['name'] = item_name.value if hasattr(item_name, 'value') else str(item_name)
                    
                    # 获取端口方向信息 (ports 是 SeparatedList)
                    if hasattr(item, 'ports'):
                        ports = list(item.ports)
                        for port in ports:
                            port_kind = getattr(port, 'kind', None)
                            # SeparatedList 包含 ModportSimplePortList
                            if port_kind and 'SeparatedList' in str(port_kind):
                                for child in port:
                                    child_kind = getattr(child, 'kind', None)
                                    if child_kind and 'ModportSimplePortList' in str(child_kind):
                                        info['direction'] = str(getattr(child, 'direction', ''))
                                        if hasattr(child, 'ports'):
                                            port_names = str(getattr(child, 'ports', ''))
                                            info['ports'] = [p.strip() for p in port_names.split(',')]
        except (ValueError, AttributeError, TypeError):
            pass
        
        return info
    
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
    def extract_port_width(self, port) -> tuple:
        """从端口声明提取位宽 (MSB, LSB)
        
        端口结构: port.header.dataType.dimensions[0].specifier.selector.left/right
        left/right 是 LiteralExpressionSyntax，其 .literal.valueText 包含数值字符串
        """
        if not port or not hasattr(port, 'header'):
            return (0, 0)
        
        header = port.header
        if not hasattr(header, 'dataType') or not header.dataType:
            return (0, 0)
        
        dt = header.dataType
        if not hasattr(dt, 'dimensions') or not dt.dimensions:
            return (0, 0)
        
        dims = dt.dimensions
        for dim in dims:
            if hasattr(dim, 'kind') and str(dim.kind) == 'SyntaxKind.VariableDimension':
                spec = getattr(dim, 'specifier', None)
                if spec:
                    sel = getattr(spec, 'selector', None)
                    if sel:
                        # 使用 getattr 安全获取，避免访问不存在的属性导致 segfault
                        left_expr = getattr(sel, 'left', None)
                        right_expr = getattr(sel, 'right', None)
                        if left_expr is not None or right_expr is not None:
                            msb = self._extract_int_value(left_expr)
                            lsb = self._extract_int_value(right_expr)
                            return (msb, lsb)
        
        return (0, 0)
    
    def _extract_int_value(self, expr) -> int:
        """从表达式提取整数值
        
        处理 LiteralExpressionSyntax，其 .literal.valueText 包含数值字符串
        也处理直接的 int 值
        """
        if expr is None:
            return 0
        
        # 直接是 int
        if isinstance(expr, int):
            return expr
        
        # 安全检查: 确保 expr 有 literal 属性
        if not hasattr(expr, 'literal'):
            # 尝试直接转 int
            try:
                return int(str(expr))
            except (ValueError, TypeError):
                return 0
        
        # LiteralExpressionSyntax - 获取 literal.token
        try:
            lit = expr.literal
            if lit and hasattr(lit, 'valueText'):
                return int(lit.valueText)
        except (ValueError, AttributeError, TypeError):
            pass
        
        # 尝试 str 转换作为最后的手段
        try:
            return int(str(expr))
        except (ValueError, TypeError):
            return 0

    def extract_data_width(self, data_decl) -> tuple:
        """从数据声明提取位宽 (MSB, LSB)
        
        数据声明结构: data_decl.type.dimensions[0].specifier.selector.left/right
        """
        if not data_decl:
            return (0, 0)
        
        if not hasattr(data_decl, 'type') or not data_decl.type:
            return (0, 0)
        
        dt = data_decl.type
        if not hasattr(dt, 'dimensions') or not dt.dimensions:
            return (0, 0)
        
        dims = dt.dimensions
        for dim in dims:
            if hasattr(dim, 'kind') and str(dim.kind) == 'SyntaxKind.VariableDimension':
                if hasattr(dim, 'specifier') and dim.specifier:
                    spec = dim.specifier
                    if hasattr(spec, 'selector'):
                        sel = spec.selector
                        msb = int(sel.left) if hasattr(sel, 'left') and sel.left else 0
                        lsb = int(sel.right) if hasattr(sel, 'right') and sel.right else 0
                        return (msb, lsb)
        
        return (0, 0)

    
    def _extract_bit_width(self, node) -> tuple:
        """提取信号位宽 (MSB, LSB)
        
        支持两种 API:
        1. 新 API: node.dimensions[0].specifier.selector.left/right
        2. 旧 API: node.dims[0].range.left/right
        """
        # 默认宽度 (scalar = 1 bit)
        msb, lsb = 0, 0
        
        # 尝试从 dimensions 获取 (新 API)
        if hasattr(node, 'dimensions') and node.dimensions:
            dims = node.dimensions
            for dim in dims:
                if hasattr(dim, 'kind') and str(dim.kind) == 'SyntaxKind.VariableDimension':
                    if hasattr(dim, 'specifier') and dim.specifier:
                        spec = dim.specifier
                        if hasattr(spec, 'selector'):
                            sel = spec.selector
                            msb = self._extract_int_value(sel.left)
                            lsb = self._extract_int_value(sel.right)
                            return (msb, lsb)
        
        # 尝试从 dims 获取 (旧 API / 兼容性)
        if hasattr(node, 'dims') and node.dims:
            dims = node.dims
            if hasattr(dims, '__iter__') and not isinstance(dims, str):
                for dim in dims:
                    if hasattr(dim, 'range'):
                        rng = dim.range
                        if rng:
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
            
            # 遍历找 HierarchyInstantiation (模块实例化语法节点)
            def find_inst(node):
                if node is None:
                    return
                kind = getattr(node, 'kind', None)
                kind_str = str(kind) if kind else ''
                # SyntaxKind.HierarchyInstantiation 包含 "HierarchyInstantiation"
                if kind and 'HierarchyInstantiation' in kind_str:
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
    
    def get_generate_instances(self, trees: dict = None) -> List:
        """Find HierarchyInstantiation nodes inside generate blocks.
        
        This is needed because pyslang's get_module_instances doesn't find
        instances inside generate for/if/case blocks.
        """
        instances = []
        
        for fname, tree in (trees or {}).items():
            if not tree or not hasattr(tree, 'root'):
                continue
            
            def walk(node, depth=0, max_depth=30):
                if depth > max_depth or node is None:
                    return
                kind = getattr(node, 'kind', None)
                kind_str = str(kind) if kind else ''
                
                # Check for LoopGenerate
                if kind == SyntaxKind.LoopGenerate:
                    if hasattr(node, 'block'):
                        block = node.block
                        if hasattr(block, 'members'):
                            for item in block.members:
                                item_kind = getattr(item, 'kind', None)
                                item_kind_str = str(item_kind) if item_kind else ''
                                if 'HierarchyInstantiation' in item_kind_str:
                                    instances.append(item)
                
                # Check for IfGenerate
                if kind == SyntaxKind.IfGenerate:
                    # Handle 'then' block
                    if hasattr(node, 'block'):
                        then_block = node.block
                        if hasattr(then_block, 'members'):
                            for item in then_block.members:
                                item_kind = getattr(item, 'kind', None)
                                item_kind_str = str(item_kind) if item_kind else ''
                                if 'HierarchyInstantiation' in item_kind_str:
                                    instances.append(item)
                    # Handle 'else' block
                    if hasattr(node, 'elseClause'):
                        else_block = node.elseClause.clause
                        if hasattr(else_block, 'members'):
                            for item in else_block.members:
                                item_kind = getattr(item, 'kind', None)
                                item_kind_str = str(item_kind) if item_kind else ''
                                if 'HierarchyInstantiation' in item_kind_str:
                                    instances.append(item)
                
                # Continue walking for other nodes
                for attr in dir(node):
                    if attr.startswith('_') or attr in ['parent', 'sourceRange']:
                        continue
                    try:
                        child = getattr(node, attr)
                        if callable(child):
                            continue
                        if hasattr(child, '__iter__') and not isinstance(child, str):
                            for c in child:
                                if hasattr(c, 'kind'):
                                    walk(c, depth+1, max_depth)
                        elif hasattr(child, 'kind'):
                            walk(child, depth+1, max_depth)
                    except:
                        pass
            
            walk(tree.root)
        
        return instances
    

    def get_instance_connection(self, instance) -> List:
        """获取实例的端口连接 [(port_name, signal_name), ...]"""
        connections = []
        
        # 获取 connections 属性
        # HierarchyInstantiation 有 connections 在 instance.instances[0] 上
        conn_attr = None
        if hasattr(instance, 'connections'):
            conn_attr = instance.connections
        elif hasattr(instance, 'instances') and instance.instances:
            conn_attr = instance.instances[0].connections
        
        if not conn_attr:
            return connections
        
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
                    
                    elif hasattr(item, 'kind') and 'NamedPortConnection' in str(item.kind):
                        port_name = None
                        signal_name = None
                        if hasattr(item, 'name'):
                            n = item.name
                            port_name = n.value if hasattr(n, 'value') else str(n)
                        # Signal extraction: conn.expr is PropertyExpr with conn.expr.expr being SequenceExpr
                        if hasattr(item, 'expr') and hasattr(item.expr, 'expr') and item.expr.expr:
                            signal = item.expr.expr
                            if hasattr(signal, 'expr') and signal.expr:  # IdentifierNameSyntax -> name attribute
                                if hasattr(signal.expr, 'identifier') and hasattr(signal.expr.identifier, 'value'):
                                    signal_name = signal.expr.identifier.value
                            elif hasattr(signal, 'identifier') and hasattr(signal.identifier, 'value'):
                                signal_name = signal.identifier.value
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
        stmts = []
        # [P2] 递归收集所有赋值，包括 generate 块内的
        self._collect_assignments_recursive(module, stmts)
        return stmts
    
    def get_class_members(self, cls) -> List:
        """获取类的成员声明 (rand 变量等)"""
        members = []
        if cls is None:
            return members
        
        # ClassDeclaration 有 items 属性
        if hasattr(cls, 'items'):
            items = cls.items
            if items and hasattr(items, '__iter__') and not isinstance(items, str):
                for item in items:
                    try:
                        kind = getattr(item, 'kind', None)
                        if kind:
                            # ClassPropertyDeclaration - rand 变量
                            if kind == SyntaxKind.ClassPropertyDeclaration:
                                members.append(item)
                            # ConstraintDeclaration - 约束块
                            elif 'Constraint' in str(kind):
                                members.append(item)
                            # ClassMethodDeclaration - 方法
                            elif 'ClassMethod' in str(kind):
                                members.append(item)
                    except (ValueError, AttributeError):
                        # pyslang AST 节点可能被垃圾回收导致 kind 访问出错
                        pass
        return members
    
    def _collect_assignments_recursive(self, node, stmts):
        """递归收集所有赋值语句，包括嵌套在 generate 等结构内的"""
        if node is None:
            return
        
        kind = getattr(node, 'kind', None)
        if kind:
            # 如果是赋值类型，直接添加
            if kind in [SyntaxKind.ContinuousAssign, SyntaxKind.DataDeclaration]:
                stmts.append(node)
                return  # 不再递归进入
            
            # [P2] ExpressionStatement (procedural blocking assignment like data = a;)
            if kind == SyntaxKind.ExpressionStatement:
                stmts.append(node)
                return
        
        # [P2] 特殊处理 GenerateBlock - 内容在 members 属性中，不要迭代
        if kind == SyntaxKind.GenerateBlock:
            if hasattr(node, 'members'):
                for item in node.members:
                    self._collect_assignments_recursive(item, stmts)
            return
        
        # [P2] 特殊处理 IfGenerate.block - 不是迭代，是单个节点
        if kind == SyntaxKind.IfGenerate:
            if hasattr(node, 'block'):
                block = getattr(node, 'block')
                self._collect_assignments_recursive(block, stmts)
            if hasattr(node, 'elseClause') and getattr(node, 'elseClause'):
                else_block = getattr(node, 'elseClause')
                self._collect_assignments_recursive(else_block, stmts)
            return
        
        # [P2] 特殊处理 Fork/Join - TokenKind.ForkKeyword 后面是 SyntaxList
        # 需要手动遍历来检测 ForkKeyword
        if kind == SyntaxKind.SyntaxList:
            # 检查是否在 fork 块内
            items = list(node) if hasattr(node, '__iter__') else []
            
            for idx, item in enumerate(items):
                item_kind = getattr(item, 'kind', None)
                
                
                # 检测 ForkKeyword - kind 本身就是 TokenKind
                if item_kind == TokenKind.ForkKeyword:
                    
                    # 下一个应该是包含 fork 内语句的 SyntaxList
                    if idx + 1 < len(items):
                        next_item = items[idx + 1]
                        next_kind = getattr(next_item, 'kind', None)
                        
                        if next_kind == SyntaxKind.SyntaxList:
                            # 递归处理 fork 内语句
                            for fork_stmt in next_item:
                                self._collect_assignments_recursive(fork_stmt, stmts)
                    return
        
        # 否则递归进入子节点
        # 优先检查是否可以直接迭代 (如 BlockStatementSyntax)
        if hasattr(node, '__iter__') and not isinstance(node, str):
            for item in node:
                self._collect_assignments_recursive(item, stmts)
            return
        
        for attr in ['members', 'body', 'statements', 'items', 'children', 'block', 'elseClause']:
            if hasattr(node, attr):
                child = getattr(node, attr)
                if child and hasattr(child, '__iter__') and not isinstance(child, str):
                    for item in child:
                        self._collect_assignments_recursive(item, stmts)
                elif child:
                    self._collect_assignments_recursive(child, stmts)
    
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
    


    def get_task_declarations(self, module) -> List:
        """获取 module 中的 task 声明"""
        tasks = []
        if not module or not hasattr(module, 'members'):
            return tasks
        
        for member in module.members:
            if hasattr(member, 'kind'):
                kind = str(member.kind)
                if 'TaskDeclaration' in kind:
                    tasks.append(member)
        
        return tasks
    
    def get_function_declarations(self, module) -> List:
        """获取 module 中的 function 声明"""
        functions = []
        if not module or not hasattr(module, 'members'):
            return functions
        
        for member in module.members:
            if hasattr(member, 'kind'):
                kind = str(member.kind)
                if 'FunctionDeclaration' in kind:
                    functions.append(member)
        
        return functions
    
    def get_task_name(self, task_decl) -> str:
        """从 task 声明中提取名称"""
        prototype = getattr(task_decl, 'prototype', None)
        if prototype:
            name = getattr(prototype, 'name', None)
            if name:
                return str(name).strip()
        return ""
    
    def get_function_name(self, func_decl) -> str:
        """从 function 声明中提取名称"""
        prototype = getattr(func_decl, 'prototype', None)
        if prototype:
            name = getattr(prototype, 'name', None)
            if name:
                return str(name).strip()
        return ""
    
    def get_task_params(self, task_decl) -> List:
        """
        获取 task 的参数列表
        返回: [(direction, name), ...]
        direction: 'input', 'output', 'inout', 'ref'
        """
        params = []
        items = getattr(task_decl, 'items', [])
        
        for item in items:
            kind = str(getattr(item, 'kind', ''))
            if 'PortDeclaration' not in kind:
                continue
            
            header = getattr(item, 'header', None)
            direction = 'input'
            if header:
                direction_attr = getattr(header, 'direction', None)
                if direction_attr:
                    # direction_attr 是 Token，检查其 kind
                    d_kind = str(getattr(direction_attr, 'kind', ''))
                    if 'Output' in d_kind:
                        direction = 'output'
                    elif 'Inout' in d_kind:
                        direction = 'inout'
                    elif 'Ref' in d_kind:
                        direction = 'ref'
            
            declarators = getattr(item, 'declarators', [])
            for decl in declarators:
                decl_kind = str(getattr(decl, 'kind', ''))
                if 'Declarator' in decl_kind:
                    name = str(decl).strip()
                    params.append((direction, name))
        
        return params
    
    def get_function_params(self, func_decl) -> List:
        """
        获取 function 的参数列表
        返回: [(direction, name), ...]
        """
        params = []
        items = getattr(func_decl, 'items', [])
        
        for item in items:
            kind = str(getattr(item, 'kind', ''))
            if 'PortDeclaration' not in kind:
                continue
            
            header = getattr(item, 'header', None)
            direction = 'input'
            if header:
                direction_attr = getattr(header, 'direction', None)
                if direction_attr:
                    d = str(direction_attr).strip()
                    if 'Output' in d:
                        direction = 'output'
            
            declarators = getattr(item, 'declarators', [])
            for decl in declarators:
                decl_kind = str(getattr(decl, 'kind', ''))
                if 'Declarator' in decl_kind:
                    name = str(decl).strip()
                    params.append((direction, name))
        
        return params



    def _extract_signals_from_expr(self, expr) -> List[str]:
        """递归提取表达式中的所有信号"""
        if expr is None:
            return []
        
        kind = getattr(expr, 'kind', None)
        kind_str = str(kind) if kind else ''
        
        # 二元表达式 (a + b, a & b, etc.)
        if any(x in kind_str for x in ['Binary', 'And', 'Or', 'Xor', 'Add', 'Sub']):
            signals = []
            l = getattr(expr, 'left', None)
            r = getattr(expr, 'right', None)
            if l: signals.extend(self._extract_signals_from_expr(l))
            if r: signals.extend(self._extract_signals_from_expr(r))
            return signals
        
        # 标识符
        result = str(expr).strip()
        if result:
            return [result]
        return []
    
    def _analyze_stmt_for_drivers(self, stmt, drivers, depth=0):
        """
        递归分析语句中的驱动关系
        支持: ExpressionStatement, ConditionalStatement, SequentialBlock, LoopStatement
        """
        if stmt is None or depth > 20:
            return
        
        kind = str(getattr(stmt, 'kind', ''))
        
        # ExpressionStatement: 直接赋值
        if 'ExpressionStatement' in kind:
            expr = getattr(stmt, 'expr', None)
            if not expr:
                return
            left = getattr(expr, 'left', None)
            right = getattr(expr, 'right', None)
            if left and right:
                left_name = str(left).strip()
                right_signals = self._extract_signals_from_expr(right)
                if left_name:
                    # 如果变量已存在，追加驱动源；否则创建新列表
                    if left_name in drivers:
                        drivers[left_name].extend(right_signals)
                    else:
                        drivers[left_name] = right_signals
            return
        
        # ConditionalStatement: if-else
        if 'Conditional' in kind and 'Statement' in kind:
            # 处理 then 分支
            then_stmt = getattr(stmt, 'statement', None) or getattr(stmt, 'body', None)
            if then_stmt:
                self._analyze_stmt_for_drivers(then_stmt, drivers, depth+1)
            
            # 处理 else 分支
            else_clause = getattr(stmt, 'elseClause', None)
            if else_clause:
                # elseClause 可能是另一个 ConditionalStatement 或 SequentialBlock
                else_kind = str(getattr(else_clause, 'kind', ''))
                if 'ElseClause' in else_kind:
                    else_stmt = getattr(else_clause, 'clause', None)
                    if else_stmt:
                        self._analyze_stmt_for_drivers(else_stmt, drivers, depth+1)
                else:
                    self._analyze_stmt_for_drivers(else_clause, drivers, depth+1)
            return
        
        # SequentialBlockStatement: begin...end 块
        if 'SequentialBlock' in kind:
            # SequentialBlockStatement 的属性可能是 items 或 statements
            for attr in ['items', 'statements', 'body']:
                block_items = getattr(stmt, attr, None)
                if block_items and hasattr(block_items, '__iter__'):
                    for item in block_items:
                        self._analyze_stmt_for_drivers(item, drivers, depth+1)
                    return
            return
        
        # ParallelBlockStatement: fork...join 块
        if 'ParallelBlock' in kind:
            for attr in ['items', 'statements', 'body', 'blocks']:
                block_items = getattr(stmt, attr, None)
                if block_items and hasattr(block_items, '__iter__'):
                    for item in block_items:
                        self._analyze_stmt_for_drivers(item, drivers, depth+1)
                    return
            return
        
        # LoopStatement: for, while
        if 'Loop' in kind and 'Statement' in kind:
            # 循环体
            loop_body = getattr(stmt, 'statement', None) or getattr(stmt, 'body', None)
            if loop_body:
                self._analyze_stmt_for_drivers(loop_body, drivers, depth+1)
            return
        
        # CaseStatement
        if 'Case' in kind and 'Statement' in kind:
            for attr in ['items', 'statements']:
                case_items = getattr(stmt, attr, None)
                if case_items and hasattr(case_items, '__iter__'):
                    for item in case_items:
                        self._analyze_stmt_for_drivers(item, drivers, depth+1)
            return
    
    def analyze_task_internal_drivers(self, task_decl) -> Dict[str, List[str]]:
        """
        分析 task 内部的驱动关系
        返回: {internal_var: [source_vars]}
        例如: task 内 out = in + 1; 返回 {'out': ['in', '1']}
        """
        drivers = {}
        
        # 遍历 task 的 items
        for item in getattr(task_decl, 'items', []):
            self._analyze_stmt_for_drivers(item, drivers)
        
        return drivers


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
