from pyslang import SyntaxKind, TokenKind
#==============================================================================
# base.py - AST Walker 基类
# 公共 AST 遍历基础设施
#==============================================================================

import logging
from typing import Callable, Optional, List, Any, Dict
from abc import ABC, abstractmethod

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

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
    
    def get_module_parameters(self, module) -> List[dict]:
        """获取模块参数列表
        
        Returns:
            List of dict: [{'name': str, 'value': str, 'type': str}, ...]
        """
        params = []
        
        if not module or not hasattr(module, 'header'):
            return params
        
        header = module.header
        if not header or not hasattr(header, 'parameters'):
            return params
        
        param_list = header.parameters
        if not param_list or not hasattr(param_list, 'declarations'):
            return params
        
        # param_list.declarations 是 ParameterDeclarationSyntax (SeparatedList)
        decls = param_list.declarations
        
        # 遍历参数声明 (可能有多个 DeclaratorSyntax 用逗号分隔)
        # decls 是 ParameterDeclarationSyntax，里面有 declarators
        for decl in decls:
            if not hasattr(decl, 'declarators'):
                continue
            
            declarators = decl.declarators
            
            # declarators 是 SyntaxNode (SeparatedList)，包含 DeclaratorSyntax 和 Comma
            for item in declarators:
                if not hasattr(item, 'kind') or 'Declarator' not in str(item.kind):
                    continue
                
                param_info = {'name': '', 'value': '', 'type': 'parameter'}
                
                # 获取参数名称
                if hasattr(item, 'name') and item.name:
                    name = item.name
                    param_info['name'] = name.value if hasattr(name, 'value') else str(name)
                
                # 获取参数值
                if hasattr(item, 'initializer') and item.initializer:
                    # initializer 是 EqualsValueClauseSyntax，有 equals 和 expr 属性
                    init = item.initializer
                    if hasattr(init, 'expr') and init.expr:
                        # expr 是实际的值表达式
                        if hasattr(init.expr, 'value'):
                            # LiteralExpressionSyntax 有 value 属性 (带格式如 1'b1)
                            val = init.expr.value
                            # 使用 valueText 获取原始值 (如 "1")
                            if hasattr(val, 'valueText'):
                                param_info['value'] = str(val.valueText)
                            else:
                                param_info['value'] = str(val)
                        elif hasattr(init.expr, 'literal'):
                            # 备选方案
                            lit = init.expr.literal
                            if hasattr(lit, 'valueText'):
                                param_info['value'] = str(lit.valueText)
                            elif hasattr(lit, 'value'):
                                param_info['value'] = str(lit.value)
                            else:
                                param_info['value'] = str(lit).strip()
                        else:
                            param_info['value'] = str(init.expr).strip()
                    else:
                        param_info['value'] = str(init).strip().lstrip('= ')
                
                params.append(param_info)
        
        return params
    
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
    

    def get_interface_modport_signals(self, interface_name: str, modport_name: str) -> Dict[str, str]:
        """[P0-3] 获取 interface 中指定 modport 的所有信号及其方向
        
        Args:
            interface_name: 接口名称 (如 "bus_if")
            modport_name: modport 名称 (如 "master")
            
        Returns:
            Dict[signal_name, direction], 如 {"data": "output", "addr": "input"}
        """
        result = {}
        
        interfaces = self.get_interfaces()
        for iface in interfaces:
            # 获取 interface 名称
            iface_def_name = None
            if hasattr(iface, 'header') and hasattr(iface.header, 'name'):
                iface_def_name = iface.header.name.value if hasattr(iface.header.name, 'value') else str(iface.header.name)
            
            if iface_def_name != interface_name:
                continue
            
            # 在 interface members 中找 ModportDeclaration
            if hasattr(iface, 'members'):
                for member in iface.members:
                    kind = str(getattr(member, 'kind', ''))
                    if 'ModportDeclaration' not in kind:
                        continue
                    
                    # 处理 items (通常只有一个 ModportItem)
                    if hasattr(member, 'items'):
                        items = list(member.items) if hasattr(member.items, '__iter__') else [member.items]
                        for item in items:
                            item_name = getattr(item, 'name', None)
                            if not item_name:
                                continue
                            actual_name = item_name.value if hasattr(item_name, 'value') else str(item_name)
                            if actual_name != modport_name:
                                continue
                            
                            # 解析 ports (AnsiPortListSyntax)
                            if hasattr(item, 'ports'):
                                ports = item.ports
                                if hasattr(ports, 'ports'):
                                    actual_ports = ports.ports
                                    if hasattr(actual_ports, '__iter__') and not isinstance(actual_ports, str):
                                        for p in actual_ports:
                                            if not hasattr(p, 'kind') or 'ModportSimplePortList' not in str(p.kind):
                                                continue
                                            direction = str(getattr(p, 'direction', '')).lower().strip()
                                            ports_list = getattr(p, 'ports', '')
                                            signal_names = str(ports_list).split(',')
                                            for sig in signal_names:
                                                sig = sig.strip()
                                                if sig:
                                                    result[sig] = direction
        
        return result

    # 现有的 get_port_declarations
    def get_port_declarations(self, module) -> List:
        """"获取端口声明
        
        支持 ANSI 和非ANSI 两种端口声明格式:
        - ANSI: module (...);
        - 非ANSI: module (port_names); ... input/output declarations
        - 混合: module (port_names); input/output declarations (部分在members)
        """
        ports = []
        if not module:
            return ports
        
        # 先检查 header 是否有 ANSI 端口 (input [7:0] data 这种)
        header_has_ansi = False
        header_has_non_ansi = False
        
        if hasattr(module, 'header') and module.header:
            header = module.header
            if hasattr(header, 'ports'):
                port_list = header.ports
                if port_list and len(port_list) > 1:
                    actual_ports = port_list[1]
                    if hasattr(actual_ports, 'kind') and actual_ports.kind == SyntaxKind.SeparatedList:
                        for port in actual_ports:
                            if hasattr(port, 'kind'):
                                if port.kind == SyntaxKind.ImplicitAnsiPort:
                                    header_has_ansi = True
                                    break
                                elif port.kind == SyntaxKind.ImplicitNonAnsiPort:
                                    header_has_non_ansi = True
        
        # 如果 header 有 ANSI 端口，使用 header 的端口 + members 的 PortDeclaration
        if header_has_ansi:
            if hasattr(module, 'header') and module.header:
                header = module.header
                if hasattr(header, 'ports'):
                    port_list = header.ports
                    if port_list and len(port_list) > 1:
                        actual_ports = port_list[1]
                        if hasattr(actual_ports, 'kind') and actual_ports.kind == SyntaxKind.SeparatedList:
                            for port in actual_ports:
                                if hasattr(port, 'kind') and port.kind == SyntaxKind.ImplicitAnsiPort:
                                    ports.append(port)
            # 也添加 members 中的 PortDeclaration (每个 Declarator 作为一个端口)
            if hasattr(module, 'members'):
                for member in module.members:
                    if hasattr(member, 'kind') and member.kind == SyntaxKind.PortDeclaration:
                        # 展开每个 declarator (跳过 Token 对象如逗号)
                        if hasattr(member, 'declarators') and member.declarators:
                            for decl in member.declarators:
                                if hasattr(decl, 'kind') and decl.kind == SyntaxKind.Declarator:
                                    # 创建一个伪 PortDeclaration 对象
                                    class PseudoPort:
                                        def __init__(self, port_decl, decl):
                                            self._port_decl = port_decl
                                            self._decl = decl
                                            self.kind = SyntaxKind.PortDeclaration
                                        @property
                                        def header(self):
                                            return self._port_decl.header
                                        @property
                                        def declarators(self):
                                            return [self._decl]
                                    ports.append(PseudoPort(member, decl))
        # 否则如果 header 有非ANSI 端口，解析 members 中的 PortDeclaration
        elif header_has_non_ansi:
            # 使用 members 中的 PortDeclaration (每个 Declarator 作为一个端口)
            if hasattr(module, 'members'):
                for member in module.members:
                    if hasattr(member, 'kind') and member.kind == SyntaxKind.PortDeclaration:
                        # 展开每个 declarator (跳过 Token 对象如逗号)
                        if hasattr(member, 'declarators') and member.declarators:
                            for decl in member.declarators:
                                if hasattr(decl, 'kind') and decl.kind == SyntaxKind.Declarator:
                                    class PseudoPort:
                                        def __init__(self, port_decl, decl):
                                            self._port_decl = port_decl
                                            self._decl = decl
                                            self.kind = SyntaxKind.PortDeclaration
                                        @property
                                        def header(self):
                                            return self._port_decl.header
                                        @property
                                        def declarators(self):
                                            return [self._decl]
                                    ports.append(PseudoPort(member, decl))
        # 如果 header 没有任何端口，尝试使用 members
        else:
            if hasattr(module, 'members'):
                for member in module.members:
                    if hasattr(member, 'kind') and member.kind == SyntaxKind.PortDeclaration:
                        # 展开每个 declarator (跳过 Token 对象如逗号)
                        if hasattr(member, 'declarators') and member.declarators:
                            for decl in member.declarators:
                                if hasattr(decl, 'kind') and decl.kind == SyntaxKind.Declarator:
                                    class PseudoPort:
                                        def __init__(self, port_decl, decl):
                                            self._port_decl = port_decl
                                            self._decl = decl
                                            self.kind = SyntaxKind.PortDeclaration
                                        @property
                                        def header(self):
                                            return self._port_decl.header
                                        @property
                                        def declarators(self):
                                            return [self._decl]
                                    ports.append(PseudoPort(member, decl))
        
        return ports



    def _get_port_name_non_ansi(self, port) -> str:
        """"获取非ANSI端口的名称"""
        # ImplicitNonAnsiPort 有 name 属性
        if hasattr(port, 'name'):
            name = port.name
            if hasattr(name, 'value'):
                return name.value
            elif hasattr(name, 'text'):
                return name.text
            return str(name)
        return None

    def _get_port_direction_non_ansi(self, module, port_name: str) -> str:
        """"从模块体的 PortDeclaration 获取端口方向"""
        if not module or not port_name:
            return 'unknown'
        
        # 直接遍历 module 的子节点（不需要 parser）
        target_name = port_name.strip()
        
        for node in module.members:
            if hasattr(node, 'kind') and node.kind == SyntaxKind.PortDeclaration:
                # 获取方向
                direction = 'unknown'
                if hasattr(node.header, 'direction'):
                    dir_tok = node.header.direction
                    if hasattr(dir_tok, 'kind'):
                        kind = dir_tok.kind
                        if kind == TokenKind.InputKeyword:
                            direction = 'input'
                        elif kind == TokenKind.OutputKeyword:
                            direction = 'output'
                        elif kind == TokenKind.InOutKeyword:
                            direction = 'inout'
                        elif kind == TokenKind.RefKeyword:
                            direction = 'ref'
                
                # 检查所有 declarators
                if hasattr(node, 'declarators') and node.declarators:
                    for decl in node.declarators:
                        if hasattr(decl, 'name'):
                            name = decl.name
                            decl_name = name.value if hasattr(name, 'value') else str(name)
                            if decl_name and decl_name.strip() == target_name:
                                return direction
        
        return 'unknown'

    def _get_parser_for_module(self, module) -> Optional[Any]:
        """"获取模块对应的 parser (未使用，保留为了兼容性)"""
        return None
    

    def get_port_names(self, module) -> List[str]:
        """获取端口名称列表"""
        ports = []
        port_decls = self.get_port_declarations(module)
        for port in port_decls:
            name, direction = self.get_port_name_and_direction(port, module)
            if name:
                ports.append(name)
        return ports

    def get_port_name(self, port) -> Optional[str]:
        """获取端口名称"""
        name, _ = self.get_port_name_and_direction(port)
        return name

    def get_port_name_and_direction(self, port, module=None) -> tuple:
        """获取端口名称和方向 (name, direction)
        
        从 AST TokenKind 获取方向，而非 str() (避免注释干扰)
        支持 ANSI 和非ANSI 端口声明
        """
        if not port:
            return None, 'unknown'
        
        name = None
        direction = 'unknown'
        
        if hasattr(port, 'kind'):
            port_kind = port.kind
            
            if port_kind == SyntaxKind.ImplicitAnsiPort:
                # ANSI 格式: port.declarator.name
                if hasattr(port, 'declarator') and port.declarator:
                    decl = port.declarator
                    if hasattr(decl, 'name'):
                        n = decl.name
                        name = n.value if hasattr(n, 'value') else str(n)
                # 方向: port.header.direction
                # [FIX] Issue 11: 逗号分隔的端口继承方向
                if hasattr(port, 'header') and port.header:
                    header = port.header
                    if hasattr(header, 'direction'):
                        dir_tok = header.direction
                        if dir_tok and hasattr(dir_tok, 'kind') and dir_tok.kind != TokenKind.Unknown:
                            kind = dir_tok.kind
                            if kind == TokenKind.InputKeyword:
                                direction = 'input'
                            elif kind == TokenKind.OutputKeyword:
                                direction = 'output'
                            elif kind == TokenKind.InOutKeyword:
                                direction = 'inout'
                            elif kind == TokenKind.RefKeyword:
                                direction = 'ref'
                        else:
                            # 继承前一个端口的方向
                            direction = self._inherit_direction_from_previous(port, module)
            
            elif port_kind == SyntaxKind.ImplicitNonAnsiPort:
                # 非ANSI 格式: port.expr.name.value
                if hasattr(port, 'expr') and port.expr:
                    expr = port.expr
                    if hasattr(expr, 'name'):
                        n = expr.name
                        name = n.value if hasattr(n, 'value') else str(n)
                # 方向需要从模块体的 PortDeclaration 查找
                if module and name:
                    direction = self._get_port_direction_non_ansi(module, name)
            
            elif port_kind == SyntaxKind.PortDeclaration:
                # 非ANSI 端口声明: output reg [7:0] out;
                # 名称从 declarators[0].name 获取
                if hasattr(port, 'declarators') and port.declarators:
                    decl = port.declarators[0]
                    if hasattr(decl, 'name'):
                        n = decl.name
                        name = n.value if hasattr(n, 'value') else str(n)
                # 方向从 header.direction 获取
                if hasattr(port, 'header') and port.header:
                    header = port.header
                    if hasattr(header, 'direction'):
                        dir_tok = header.direction
                        if dir_tok and hasattr(dir_tok, 'kind') and dir_tok.kind != TokenKind.Unknown:
                            kind = dir_tok.kind
                            if kind == TokenKind.InputKeyword:
                                direction = 'input'
                            elif kind == TokenKind.OutputKeyword:
                                direction = 'output'
                            elif kind == TokenKind.InOutKeyword:
                                direction = 'inout'
                            elif kind == TokenKind.RefKeyword:
                                direction = 'ref'
        
        return name, direction
    

    def _inherit_direction_from_previous(self, port, module) -> str:
        """Issue 11 fix: 从同组的前一个端口继承方向
        
        input clk, resetn 解析时 resetn 没有 direction，需要从 clk 继承
        """
        if not module or not hasattr(module, 'header') or not module.header:
            return 'unknown'
        
        header = module.header
        if not hasattr(header, 'ports') or not header.ports:
            return 'unknown'
        
        port_list = header.ports
        if len(port_list) < 2:
            return 'unknown'
        
        actual_ports = port_list[1]  # SeparatedList
        
        # 找到当前端口的索引
        current_idx = None
        for idx, p in enumerate(actual_ports):
            if hasattr(p, 'kind') and p.kind == SyntaxKind.ImplicitAnsiPort:
                if p is port:
                    current_idx = idx
                    break
        
        if current_idx is None or current_idx == 0:
            return 'unknown'
        
        # 向前查找最近的有方向的端口
        for prev_idx in range(current_idx - 1, -1, -1):
            prev_port = actual_ports[prev_idx]
            if not hasattr(prev_port, 'kind') or prev_port.kind != SyntaxKind.ImplicitAnsiPort:
                continue
            if hasattr(prev_port, 'header') and prev_port.header:
                dir_tok = prev_port.header.direction
                if dir_tok and hasattr(dir_tok, 'kind') and dir_tok.kind != TokenKind.Unknown:
                    kind = dir_tok.kind
                    if kind == TokenKind.InputKeyword:
                        return 'input'
                    elif kind == TokenKind.OutputKeyword:
                        return 'output'
                    elif kind == TokenKind.InOutKeyword:
                        return 'inout'
                    elif kind == TokenKind.RefKeyword:
                        return 'ref'
        
        return 'unknown'

    def extract_port_width(self, port, scope=None) -> dict | tuple:
        """提取位宽信息
        
        [理想方案] 基于 AST SyntaxKind 的递归表达式求值器
        
        Args:
            port: 端口声明 (ImplicitAnsiPortSyntax)
            scope: 可选，Module 或 Class 上下文，自动从中提取参数进行求值
        
        Returns:
            如果 scope 提供: dict with eval results
                - msb_raw, msb_eval, msb_is_param
                - lsb_raw, lsb_eval, lsb_is_param
            如果 scope 为 None: tuple (msb, lsb) - 向后兼容
        """
        param_map = {}
        
        # 从 scope (module/class) 中提取参数
        if scope is not None:
            kind = getattr(scope, 'kind', None)
            if kind == SyntaxKind.ModuleDeclaration:
                params = self.get_module_parameters(scope)
                
                # 第一遍: 收集所有参数值 (包括表达式)
                # 构建 param_expr_map: {name: expression_node}
                # 构建 param_raw_map: {name: raw_string}
                param_expr_map = {}
                param_raw_map = {}
                
                for p in params:
                    name = p['name']
                    raw_val = p['value']
                    param_raw_map[name] = raw_val
                    
                    # 尝试解析为整数
                    try:
                        param_expr_map[name] = ('literal', int(raw_val))
                    except ValueError:
                        # 无法直接解析，存储表达式供后续递归求值
                        param_expr_map[name] = ('expr', raw_val)
                
                # 第二遍: 预填充所有字面量参数
                int_params = {}  # 已解析的整数参数
                for name, expr_info in param_expr_map.items():
                    if expr_info[0] == 'literal':
                        int_params[name] = expr_info[1]
                
                # 第三遍: 迭代解析参数引用 (最多10层防止循环)
                for _ in range(10):
                    progress = False
                    for name, expr_info in list(param_expr_map.items()):
                        if expr_info[0] == 'expr':
                            # 使用 _evaluate_raw_param 递归解析 (传入已解析的整数参数)
                            result = self._evaluate_raw_param(name, int_params, scope)
                            if result is not None:
                                param_expr_map[name] = ('literal', result)
                                int_params[name] = result
                                progress = True
                    if not progress:
                        break
                
                # 最终 param_map 只包含已解析的数字
                param_map = int_params
            # 后续可扩展 Class support
        
        if scope is not None:
            # 传入 scope 时总是返回 dict (即使 param_map 为空)
            return self.extract_port_width_with_eval(port, param_map, scope)
        else:
            # 向后兼容: 返回 tuple
            return self._extract_width_tuple(port)
    
    def _resolve_parameter_expr(self, module, param_name: str):
        """从 module AST 中解析参数表达式节点
        
        Args:
            module: ModuleDeclaration AST 节点
            param_name: 参数名称
            
        Returns:
            Expression AST 节点 or None
        """
        if not module or not hasattr(module, 'header'):
            return None
        
        header = module.header
        if not header or not hasattr(header, 'parameters'):
            return None
        
        param_list = header.parameters
        if not param_list or not hasattr(param_list, 'declarations'):
            return None
        
        decls = param_list.declarations
        for decl in decls:
            if not hasattr(decl, 'declarators'):
                continue
            
            for item in decl.declarators:
                if not hasattr(item, 'kind') or 'Declarator' not in str(item.kind):
                    continue
                
                if hasattr(item, 'name') and item.name:
                    name = item.name.value if hasattr(item.name, 'value') else str(item.name)
                    if name == param_name and hasattr(item, 'initializer') and item.initializer:
                        # 返回 EqualsValueClause 的 expr
                        return item.initializer.expr
        
        return None
    
    def _evaluate_raw_param(self, param_name: str, resolved: dict, module=None) -> int | None:
        """递归求值参数引用表达式
        
        Args:
            param_name: 参数名称
            resolved: 已解析的参数 {name: value}
            module: ModuleDeclaration AST 节点 (用于获取参数表达式)
            
        Returns:
            int or None
        """
        if module is None:
            # 从 resolved 中找（如果之前已经解析过）
            if param_name in resolved and isinstance(resolved[param_name], int):
                return resolved[param_name]
            return None
        
        expr_node = self._resolve_parameter_expr(module, param_name)
        if expr_node is None:
            return None
        
        # 使用 _evaluate_expression 递归求值
        result = self._evaluate_expression(expr_node, resolved)
        return result
    
    def _extract_width_tuple(self, port) -> tuple:
        """提取位宽 (向后兼容版本，返回 tuple)"""
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
    
    def extract_port_width_with_eval(self, port, param_map: dict = None, scope=None) -> dict:
        """提取位宽信息 (方案 C 增强版)
        
        [方案 C] 对参数化位宽进行表达式求值
        
        Args:
            port: 端口声明 (ImplicitAnsiPortSyntax or ImplicitNonAnsiPort)
            param_map: 可选，参数名->值的映射，如 {'W': 32, 'B': 8}
            scope: 可选，Module 上下文，用于非ANSI端口查找 PortDeclaration
        
        Returns:
            dict with keys:
                - msb_raw: 原始 MSB 表达式字符串，或 None (字面量)
                - msb_eval: 求值结果 int，或 None (无法求值)
                - msb_is_param: 是否包含参数引用
                - lsb_raw: 原始 LSB 表达式字符串，或 None (字面量)
                - lsb_eval: 求值结果 int，或 None (无法求值)
                - lsb_is_param: 是否包含参数引用
        """
        result = {
            'msb_raw': None,
            'msb_eval': None,
            'msb_is_param': False,
            'lsb_raw': None,
            'lsb_eval': None,
            'lsb_is_param': False
        }
        
        if not port or not hasattr(port, 'kind'):
            return result
        
        # 处理非ANSI端口: 从 body 的 PortDeclaration 提取位宽
        if port.kind == SyntaxKind.ImplicitNonAnsiPort:
            if scope and hasattr(scope, 'members'):
                # 获取端口名
                port_name = None
                if hasattr(port, 'expr') and port.expr and hasattr(port.expr, 'name'):
                    name_node = port.expr.name
                    port_name = name_node.value if hasattr(name_node, 'value') else str(name_node)
                
                if port_name:
                    # 在 scope.members 中查找匹配的 PortDeclaration
                    for node in scope.members:
                        if hasattr(node, 'kind') and node.kind == SyntaxKind.PortDeclaration:
                            # 检查所有 declarators
                            if hasattr(node, 'declarators') and node.declarators:
                                for decl in node.declarators:
                                    if hasattr(decl, 'name'):
                                        decl_name = decl.name.value if hasattr(decl.name, 'value') else str(decl.name)
                                        if decl_name and decl_name.strip() == port_name.strip():
                                            # 找到匹配的 PortDeclaration，递归提取其位宽信息
                                            return self.extract_port_width_with_eval(node, param_map, scope=None)
            
            # 非ANSI但找不到对应的 PortDeclaration，返回空结果
            return result
        
        # ANSI 端口处理
        if not hasattr(port, 'header'):
            return result
        
        header = port.header
        if not hasattr(header, 'dataType') or not header.dataType:
            return result
        
        dt = header.dataType
        if not hasattr(dt, 'dimensions') or not dt.dimensions:
            return result
        
        dims = dt.dimensions
        for dim in dims:
            if hasattr(dim, 'kind') and str(dim.kind) == 'SyntaxKind.VariableDimension':
                spec = getattr(dim, 'specifier', None)
                if spec:
                    sel = getattr(spec, 'selector', None)
                    if sel:
                        left_expr = getattr(sel, 'left', None)
                        right_expr = getattr(sel, 'right', None)
                        
                        # 处理 MSB
                        if left_expr is not None:
                            msb_value = self._extract_value_for_eval(left_expr)
                            if isinstance(msb_value, str):
                                result['msb_raw'] = msb_value
                                result['msb_is_param'] = True
                                if param_map:
                                    result['msb_eval'] = self._evaluate_expression(left_expr, param_map)
                            else:
                                result['msb_eval'] = msb_value
                        
                        # 处理 LSB
                        if right_expr is not None:
                            lsb_value = self._extract_value_for_eval(right_expr)
                            if isinstance(lsb_value, str):
                                result['lsb_raw'] = lsb_value
                                result['lsb_is_param'] = True
                                if param_map:
                                    result['lsb_eval'] = self._evaluate_expression(right_expr, param_map)
                            else:
                                result['lsb_eval'] = lsb_value
                        
                        return result
        
        return result
    
    def _extract_value_for_eval(self, expr) -> int | str:
        """从表达式提取值用于方案 C 求值
        
        与 _extract_int_value 类似，但返回 str 用于标识参数引用
        """
        if expr is None:
            return 0
        
        if isinstance(expr, int):
            return expr
        
        # 字面量
        if hasattr(expr, 'literal') and expr.literal:
            try:
                return int(expr.literal.valueText)
            except:
                pass
        
        # Identifier (参数引用)
        if hasattr(expr, 'identifier') and expr.identifier:
            id_val = expr.identifier.value if hasattr(expr.identifier, 'value') else str(expr.identifier)
            if id_val.strip():
                return id_val.strip()
        
        # BinaryExpression 等复杂表达式
        if hasattr(expr, 'left') and hasattr(expr, 'right'):
            return str(expr).strip()
        
        # 最后的手段
        try:
            return int(str(expr))
        except:
            return 0
    
    def _evaluate_expression(self, expr, param_map: dict) -> int | None:
        """递归求值表达式 [方案 C 核心]
        
        Args:
            expr: pyslang 表达式节点
            param_map: 参数名 -> 值 的映射
        
        Returns:
            int: 求值结果
            None: 无法求值 (缺少参数定义或未知表达式类型)
        """
        if expr is None:
            return 0
        
        if isinstance(expr, int):
            return expr
        
        kind = str(getattr(expr, 'kind', ''))
        
        # 字面量: IntegerLiteral, etc.
        if hasattr(expr, 'literal') and expr.literal:
            try:
                return int(expr.literal.valueText)
            except:
                pass
        
        # 参数引用: IdentifierName
        if hasattr(expr, 'identifier') and expr.identifier:
            name = expr.identifier.value if hasattr(expr.identifier, 'value') else str(expr.identifier)
            if name in param_map:
                val = param_map[name]
                # 如果是字符串，尝试转换为整数
                if isinstance(val, str):
                    try:
                        return int(val)
                    except ValueError:
                        # 如果不是数字，返回 None (参数引用参数无法直接求值)
                        return None
                return val
            return None  # 参数未定义
        
        # 括号表达式: ParenthesizedExpression -> 递归求值 expression
        if kind == 'SyntaxKind.ParenthesizedExpression' and hasattr(expr, 'expression'):
            return self._evaluate_expression(expr.expression, param_map)
        
        # 二元表达式
        if hasattr(expr, 'left') and hasattr(expr, 'right'):
            left_val = self._evaluate_expression(expr.left, param_map)
            right_val = self._evaluate_expression(expr.right, param_map)
            
            if left_val is None or right_val is None:
                return None
            
            # 操作符判断
            if hasattr(expr, 'operatorToken'):
                op = expr.operatorToken
                op_kind = str(getattr(op, 'kind', ''))
                
                # 加法
                if 'Plus' in op_kind:
                    return left_val + right_val
                # 减法
                elif 'Minus' in op_kind:
                    return left_val - right_val
                # 乘法
                elif 'Star' in op_kind:
                    return left_val * right_val
                # 除法
                elif 'Slash' in op_kind:
                    return left_val // right_val if right_val != 0 else 0
                # 取模
                elif 'Percent' in op_kind:
                    return left_val % right_val if right_val != 0 else 0
            
            # 如果没有 operatorToken，尝试字符串匹配
            expr_str = str(expr).strip()
            # 简单处理: 已知模式
            if '+' in expr_str:
                return left_val + right_val
            elif '-' in expr_str:
                return left_val - right_val
            elif '*' in expr_str or '×' in expr_str:
                return left_val * right_val
            elif '/' in expr_str or '÷' in expr_str:
                return left_val // right_val if right_val != 0 else 0
        
        return None  # 无法处理的表达式类型
    
    def _extract_int_value(self, expr) -> int | str:
        """从表达式提取整数值或参数名
        
        [A+ 方案] 返回 int (字面量) 或 str (参数引用)
        这让调用方知道位宽是字面量还是参数引用
        
        未来扩展 [方案 C]:
        - 可通过 module.params 缓存参数定义
        - 实现表达式求值器支持 B-1, C/2+1 等
        - 递归遍历 BinaryExpressionSyntax 等
        """
        if expr is None:
            return 0
        
        # 直接是 int
        if isinstance(expr, int):
            return expr
        
        # 安全检查: 确保 expr 有 literal 属性 (字面量)
        if hasattr(expr, 'literal') and expr.literal:
            try:
                return int(expr.literal.valueText)
            except (ValueError, AttributeError, TypeError):
                pass
        
        # 检查是否是参数引用 (Identifier)
        # 例如 B-1 中的 B，指向模块参数
        if hasattr(expr, 'name') and expr.name:
            name_val = expr.name.value if hasattr(expr.name, 'value') else str(expr.name)
            if name_val.strip():
                return name_val.strip()  # 返回参数名而非 0
        
        # 检查 IdentifierNameSyntax 的 identifier 属性
        if hasattr(expr, 'identifier') and expr.identifier:
            id_val = expr.identifier.value if hasattr(expr.identifier, 'value') else str(expr.identifier)
            if id_val.strip():
                return id_val.strip()  # 返回参数名而非 0
        
        # 检查 BinaryExpressionSyntax (复杂表达式如 W/2-1)
        # 返回字符串表示，标注为参数表达式
        if hasattr(expr, 'left') and hasattr(expr, 'right'):
            # 这是 BinaryExpression 或类似结构
            # 返回完整的表达式字符串
            expr_str = str(expr).strip()
            if expr_str and expr_str != '0':
                return expr_str  # 如 "W/2-1" 或 "B-1"
        
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
                        msb = self._extract_int_value(sel.left)
                        lsb = self._extract_int_value(sel.right)
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
            # 使用 (id, kind) 元组避免 pyslang Token 对象池化导致的 id 冲突
            visited = set()
            max_depth = 100
            
            def find_inst(node, depth=0):
                if node is None or depth > max_depth:
                    return
                
                node_key = (id(node), getattr(node, 'kind', None))
                if node_key in visited:
                    return
                visited.add(node_key)
                
                kind = getattr(node, 'kind', None)
                kind_str = str(kind) if kind else ''
                
                # [FIX] 记录未知节点类型用于调试
                if kind and kind not in (SyntaxKind.ModuleDeclaration, 
                                         SyntaxKind.PortDeclaration,
                                         SyntaxKind.HierarchyInstantiation,
                                         SyntaxKind.InterfaceDeclaration,
                                         SyntaxKind.ClassDeclaration,
                                         SyntaxKind.DataDeclaration,
                                         SyntaxKind.NetDeclaration,
                                         SyntaxKind.ContinuousAssign,
                                         SyntaxKind.AlwaysBlock,
                                         SyntaxKind.GenerateBlock,
                                         SyntaxKind.GenerateRegion,
                                         SyntaxKind.LoopGenerate,
                                         SyntaxKind.IfGenerate,
                                         SyntaxKind.CaseGenerate,
                                         SyntaxKind.NetPortHeader,
                                         SyntaxKind.VariablePortHeader,
                                         SyntaxKind.ImplicitAnsiPort,
                                         SyntaxKind.AnsiPortList,
                                         SyntaxKind.ModuleHeader):
                    # 仅记录一次 (去重)
                    if node_key not in getattr(find_inst, '_logged_kinds', set()):
                        if not hasattr(find_inst, '_logged_kinds'):
                            find_inst._logged_kinds = set()
                        find_inst._logged_kinds.add(node_key)
                        logger.warning(f"[UnknownNode] kind={kind_str} at depth={depth}")
                
                # [FIX] 只接受 HierarchyInstantiation，不接受 HierarchicalInstance
                # HierarchicalInstance 是 HierarchyInstantiation 的子节点，会导致重复
                if kind and 'HierarchyInstantiation' in kind_str and 'HierarchicalInstance' not in kind_str:
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
                                find_inst(c, depth+1)
                        elif hasattr(child, 'kind'):
                            find_inst(child, depth+1)
                    except Exception as e:
                        # [FIX] 不再静默跳过，记录错误便于调试
                        logger.debug(f"[find_inst] attr={attr}: {e}")
            
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
    


    def get_instance_name(self, instance) -> str:
        """获取实例名称
        
        Args:
            instance: HierarchyInstantiation AST 节点
        
        Returns:
            str: 实例名称 (如 'I0', 'inst1')
            
        注意: clacc 使用反格式 (instance_name module_type)，实例名在前
              标准格式使用 (module_type instance_name)
              
        判断逻辑:
        - clacc 反格式: node.type 是实例名 (如 I0, I1)，node.instances[0].decl.name 是模块类型
        - 标准格式: node.type 是模块类型，node.instances[0].decl.name 是实例名
        
        通过 heuristics 判断：如果 node.type 以大写 I 开头加数字，很可能是 clacc 格式
        """
        if not instance:
            return None
        
        # 获取两个可能的名称
        type_val = None
        decl_name = None
        
        if hasattr(instance, 'type') and instance.type:
            type_val = instance.type.value if hasattr(instance.type, 'value') else str(instance.type).strip()
        
        if hasattr(instance, 'instances') and instance.instances:
            inst0 = instance.instances[0]
            if hasattr(inst0, 'decl') and inst0.decl and hasattr(inst0.decl, 'name'):
                decl_name = inst0.decl.name.value if hasattr(inst0.decl.name, 'value') else str(inst0.decl.name).strip()
        
        # Heuristic: 如果 node.type 是 Ix 格式 (x是数字)，它是 clacc 实例名
        if type_val and len(type_val) >= 2 and type_val[0] == 'I' and type_val[1:].isdigit():
            return type_val
        
        # 否则返回 decl.name (标准格式的实例名，或 clacc 格式的模块类型)
        return decl_name
    
    def get_instance_module_type(self, instance) -> str:
        """获取实例化的模块类型
        
        Args:
            instance: HierarchyInstantiation AST 节点
        
        Returns:
            str: 模块类型 (如 'dual_clock_fifo', 'ifmap_spad', 'my_module')
            
        注意: clacc 反格式 (instance_name module_type)，模块类型在 decl.name
              标准格式 (module_type instance_name)，模块类型在 node.type
        """
        if not instance:
            return None
        
        # 获取 node.type (clacc 格式是实例名，标准格式是模块类型)
        type_val = None
        if hasattr(instance, 'type') and instance.type:
            type_val = instance.type.value if hasattr(instance.type, 'value') else str(instance.type).strip()
        
        # 获取 decl.name (clacc 格式是模块类型，标准格式是实例名)
        decl_name = None
        if hasattr(instance, 'instances') and instance.instances:
            inst0 = instance.instances[0]
            if hasattr(inst0, 'decl') and inst0.decl and hasattr(inst0.decl, 'name'):
                decl_name = inst0.decl.name.value if hasattr(inst0.decl.name, 'value') else str(inst0.decl.name).strip()
        
        # Heuristic: 如果 node.type 是 Ix 格式 (x是数字)，它是 clacc 格式
        if type_val and len(type_val) >= 2 and type_val[0] == 'I' and type_val[1:].isdigit():
            # clacc 格式: decl.name 是模块类型
            return decl_name
        
        # 否则 node.type 就是模块类型 (标准格式)
        return type_val

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
                            # expr 是 SimplePropertyExprSyntax，有 identifier 属性
                            if hasattr(expr, 'identifier') and hasattr(expr.identifier, 'value'):
                                signal_name = expr.identifier.value
                            else:
                                signal_name = str(expr).strip()
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
