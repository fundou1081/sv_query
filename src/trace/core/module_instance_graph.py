"""
module_instance_graph.py - 模块实例层级图

[铁律11] 单一职责 - 模块实例结构独立管理

职责：
1. 管理模块实例层级 (top.u_tb, top.u_dut)
2. 维护端口到内部信号的映射
3. 支持跨模块路径查找

使用方式：
  mig = ModuleInstanceGraph(adapter)
  mig.build(trees)
  internal = mig.get_internal_signal('top.u_dut.clk')  # → 'dut.clk'
"""

from typing import Dict, List, Optional, Tuple
from .graph_models import EdgeKind
from dataclasses import dataclass, field


@dataclass
class PortInfo:
    """端口信息"""
    name: str                    # 端口名 (clk, data, etc.)
    direction: str               # input/output/inout
    width: Tuple[int, int]      # (msb, lsb)
    internal_signal: str        # 内部信号名 (dut.clk)
    module_type: str            # 模块类型 (dut)


@dataclass
class ModuleInstanceNode:
    """模块实例节点"""
    id: str                      # 实例ID: "top.u_dut"
    module_type: str            # 模块类型: "dut"
    parent: Optional[str]       # 父实例: "top" 或 None
    ports: Dict[str, PortInfo] = field(default_factory=dict)
    
    def get_port(self, port_name: str) -> Optional[PortInfo]:
        return self.ports.get(port_name)
    
    def get_internal_signal(self, port_name: str) -> Optional[str]:
        port = self.get_port(port_name)
        return port.internal_signal if port else None


class ModuleInstanceGraph:
    """模块实例层级图
    
    管理模块实例及其端口映射关系
    支持跨模块边界追踪
    """
    
    def __init__(self, adapter):
        self.adapter = adapter
        self.instances: Dict[str, ModuleInstanceNode] = {}  # instance_id → Node
        self.port_to_internal: Dict[str, str] = {}  # "top.u_dut.clk" → "dut.clk"
        self.internal_to_port: Dict[str, str] = {}  # "dut.clk" → "top.u_dut.clk"
        
    def build(self, trees: Dict[str, any]):
        """构建模块实例图 (两遍: 1)存储模块端口 2)解析实例)"""
        from pyslang import SyntaxKind
        
        # 第一遍: 遍历所有模块，存储端口定义
        for fname, tree in trees.items():
            if not tree or not hasattr(tree, 'root'):
                continue
            
            root = tree.root
            
            # 处理 CompilationUnit vs ModuleDeclaration
            if hasattr(root, 'kind') and 'CompilationUnit' in str(root.kind):
                for member in getattr(root, 'members', []):
                    kind_str = str(getattr(member, 'kind', ''))
                    if 'ModuleDeclaration' in kind_str:
                        module_name = self._get_module_name(member)
                        if module_name:
                            self._store_module_ports(module_name, member)
            else:
                # 直接是 ModuleDeclaration
                module_name = self._get_module_name(root)
                if module_name:
                    self._store_module_ports(module_name, root)
        
        # 第二遍: 遍历所有模块，提取实例化并建立端口映射
        for fname, tree in trees.items():
            if not tree or not hasattr(tree, 'root'):
                continue
            
            root = tree.root
            
            if hasattr(root, 'kind') and 'CompilationUnit' in str(root.kind):
                for member in getattr(root, 'members', []):
                    kind_str = str(getattr(member, 'kind', ''))
                    if 'ModuleDeclaration' in kind_str:
                        module_name = self._get_module_name(member)
                        if module_name:
                            print(f"[DEBUG] Processing ModuleDeclaration: {module_name}")
                            self._extract_instances(member, module_name)
            else:
                module_name = self._get_module_name(root)
                if module_name:
                    print(f"[DEBUG] Processing single module: {module_name}")
                    self._extract_instances(root, module_name)
    
    def _extract_instances(self, node, parent_path: str):
        """递归提取模块实例"""
        from pyslang import SyntaxKind
        
        if node is None:
            return
        
        kind = getattr(node, 'kind', None)
        if kind is None:
            return
        
        kind_str = str(kind)
        
        # ModuleDeclaration - 提取端口定义
        if 'ModuleDeclaration' in kind_str:
            module_name = self._get_module_name(node)
            if module_name:
                # 存储模块端口定义 (用于后续实例化)
                self._store_module_ports(module_name, node)
            # 继续递归，但保持 parent_path 不变 (因为我们是同层级的模块定义)
            for child in self._iter_children(node):
                self._extract_instances(child, parent_path)
            return
        
        # HierarchyInstantiation - 提取模块实例 (使用当前 parent_path)
        if 'HierarchyInstantiation' in kind_str:
            self._extract_module_instantiation(node, parent_path)
            return
        
        # 递归子节点
        for child in self._iter_children(node):
            self._extract_instances(child, parent_path)
        
        # GateInstantiation 或 ModuleInstantiation
        if 'HierarchyInstantiation' in kind_str:
            self._extract_module_instantiation(node, parent_path)
        
        # ContinuousAssign - 端口连接
        if 'ContinuousAssign' in kind_str:
            self._extract_port_connections(node, parent_path)
        
        # 递归子节点
        for child in self._iter_children(node):
            self._extract_instances(child, parent_path)
    
    def _get_module_name(self, node) -> Optional[str]:
        """获取模块名"""
        if hasattr(node, 'header') and node.header:
            header = node.header
            if hasattr(header, 'name'):
                name = header.name
                if hasattr(name, 'value'):
                    return name.value
                if hasattr(name, 'text'):
                    return name.text
        return None
    
    def _store_module_ports(self, module_name: str, node):
        """存储模块的端口定义"""
        if not hasattr(self, '_module_ports'):
            self._module_ports = {}
        
        ports = {}
        header = getattr(node, 'header', None)
        
        # 从 header.ports 获取端口信息
        if header and hasattr(header, 'ports') and header.ports:
            ansi_ports = header.ports
            
            # ports = ( OpenParen, SeparatedList, CloseParen )
            # SeparatedList contains ImplicitAnsiPort nodes
            if len(ansi_ports) > 1:
                separated_list = ansi_ports[1]
                if hasattr(separated_list, '__iter__'):
                    for elem in separated_list:
                        if not hasattr(elem, 'kind') or 'ImplicitAnsiPort' not in str(elem.kind):
                            continue
                        
                        # Get port name from declarator
                        port_name = None
                        declarator = getattr(elem, 'declarator', None)
                        if declarator and hasattr(declarator, 'name') and declarator.name:
                            port_name = declarator.name.value if hasattr(declarator.name, 'value') else str(declarator.name)
                        
                        if not port_name:
                            continue
                        
                        # Get direction from header
                        direction = 'unknown'
                        elem_header = getattr(elem, 'header', None)
                        if elem_header and hasattr(elem_header, 'direction'):
                            direction = str(elem_header.direction).strip()
                        
                        # Get width from header.dataType.dimensions
                        width = (0, 0)
                        if elem_header and hasattr(elem_header, 'dataType') and elem_header.dataType:
                            dt = elem_header.dataType
                            if hasattr(dt, 'dimensions') and dt.dimensions:
                                for dim in dt.dimensions:
                                    dim_kind = str(getattr(dim, 'kind', ''))
                                    if 'VariableDimension' in dim_kind:
                                        spec = getattr(dim, 'specifier', None)
                                        if spec and hasattr(spec, 'selector'):
                                            sel = spec.selector
                                            left = getattr(sel, 'left', None)
                                            right = getattr(sel, 'right', None)
                                            msb = self._extract_int_value(left)
                                            lsb = self._extract_int_value(right)
                                            width = (msb, lsb)
                                            break
                        
                        ports[port_name] = PortInfo(
                            name=port_name,
                            direction=direction,
                            width=width,
                            internal_signal=f"{module_name}.{port_name}",
                            module_type=module_name
                        )
        
        self._module_ports[module_name] = ports
    
    def _extract_port_info(self, port_decl, module_name: str) -> Optional[PortInfo]:
        """提取端口信息 (PortDeclarationSyntax)"""
        # 获取端口名称
        name = None
        if hasattr(port_decl, 'declarator') and port_decl.declarator:
            decl = port_decl.declarator
            name = getattr(decl, 'name', None)
            if name:
                name = name.value if hasattr(name, 'value') else str(name)
        
        if not name:
            return None
        
        # 获取方向
        direction = 'unknown'
        if hasattr(port_decl, 'header') and port_decl.header:
            header = port_decl.header
            if hasattr(header, 'direction'):
                direction = str(header.direction)
        
        # 获取位宽 (从 dataType.dimensions)
        width = (0, 0)
        if hasattr(port_decl, 'header') and port_decl.header:
            header = port_decl.header
            if hasattr(header, 'dataType') and header.dataType:
                dt = header.dataType
                if hasattr(dt, 'dimensions') and dt.dimensions:
                    for dim in dt.dimensions:
                        if hasattr(dim, 'kind') and 'VariableDimension' in str(dim.kind):
                            spec = getattr(dim, 'specifier', None)
                            if spec and hasattr(spec, 'selector'):
                                sel = spec.selector
                                left = getattr(sel, 'left', None)
                                right = getattr(sel, 'right', None)
                                msb = self._extract_int_value(left)
                                lsb = self._extract_int_value(right)
                                width = (msb, lsb)
                                break
        
        return PortInfo(
            name=name,
            direction=direction,
            width=width,
            internal_signal=f"{module_name}.{name}",
            module_type=module_name
        )
    
    def _extract_int_value(self, expr) -> int:
        """从表达式提取整数值"""
        if expr is None:
            return 0
        if hasattr(expr, 'literal') and expr.literal:
            lit = expr.literal
            if hasattr(lit, 'valueText'):
                try:
                    return int(lit.valueText)
                except (ValueError, TypeError):
                    pass
        if hasattr(expr, 'value'):
            v = expr.value
            if isinstance(v, (int, float)):
                return int(v)
        return 0
    
    def _extract_module_instantiation(self, node, parent_path: str):
        """提取模块实例化 (HierarchyInstantiation)"""
        import re
        
        # 获取模块类型 (来自 instantiation 的 type)
        module_type = None
        inst_type = getattr(node, 'type', None)
        if inst_type:
            module_type = str(inst_type).strip()
        
        # 获取实例名列表 (来自 instances)
        instances_str = getattr(node, 'instances', None)
        if instances_str:
            inst_str = str(instances_str).strip()
            # Parse: u_tb(), u_dut() -> ['u_tb', 'u_dut']
            matches = re.findall(r'(\w+)\s*(?:\([^)]*\))?\s*,?\s*', inst_str)
            
            for instance_name in matches:
                if not instance_name:
                    continue
        
                # 构造完整实例ID
                if parent_path:
                    instance_id = f"{parent_path}.{instance_name}"
                else:
                    instance_id = instance_name
        
                # 创建实例节点
                if instance_id not in self.instances:
                    instance_node = ModuleInstanceNode(
                        id=instance_id,
                        module_type=module_type,
                        parent=parent_path or None
                    )
                    self.instances[instance_id] = instance_node
                    
                    # 添加端口映射
                    self._add_instance_ports(instance_id, module_type)
    
    def _add_instance_ports(self, instance_id: str, module_type: str):
        """为实例添加端口映射"""
        if not hasattr(self, '_module_ports'):
            return
        
        module_ports = self._module_ports.get(module_type, {})
        for port_name, port_info in module_ports.items():
            # 端口路径: top.u_dut.clk
            port_path = f"{instance_id}.{port_name}"
            # 内部信号: dut.clk
            internal = f"{module_type}.{port_name}"
            
            self.port_to_internal[port_path] = internal
            self.internal_to_port[internal] = port_path
            
            # 更新实例节点的端口
            if instance_id in self.instances:
                self.instances[instance_id].ports[port_name] = PortInfo(
                    name=port_name,
                    direction=port_info.direction,
                    width=port_info.width,
                    internal_signal=internal,
                    module_type=module_type
                )
    
    def _extract_port_connections(self, node, parent_path: str):
        """提取端口连接 (assign 语句)"""
        # assign u_dut.clk = u_tb.clk;
        # 提取左边的端口路径和右边的信号
        pass  # ConnectionExtractor 已处理
    
    def _iter_children(self, node):
        """迭代子节点"""
        if node is None:
            return
        
        # 常见的子节点属性
        for attr in ['members', 'items', 'body', 'statements', 'declarations']:
            children = getattr(node, attr, None)
            if children and hasattr(children, '__iter__') and not isinstance(children, str):
                for child in children:
                    yield child
    
    def get_internal_signal(self, port_path: str) -> Optional[str]:
        """端口路径 → 内部信号
        
        Args:
            port_path: "top.u_dut.clk"
            
        Returns:
            "dut.clk" 或 None
        """
        return self.port_to_internal.get(port_path)
    
    def get_port_path(self, internal_signal: str) -> Optional[str]:
        """内部信号 → 端口路径
        
        Args:
            internal_signal: "dut.clk"
            
        Returns:
            "top.u_dut.clk" 或 None
        """
        return self.internal_to_port.get(internal_signal)
    
    def get_instance(self, instance_id: str) -> Optional[ModuleInstanceNode]:
        """获取实例节点"""
        return self.instances.get(instance_id)
    
    def get_child_instances(self, parent_id: str) -> List[ModuleInstanceNode]:
        """获取子实例"""
        return [inst for inst in self.instances.values() 
                if inst.parent == parent_id]
    
    def get_all_instances(self) -> List[str]:
        """获取所有实例ID"""
        return list(self.instances.keys())


class PathResolver:
    """跨模块路径解析器
    
    协调 SignalGraph 和 ModuleInstanceGraph
    实现跨模块边界路径查找
    """
    
    def __init__(self, signal_graph, module_graph: ModuleInstanceGraph):
        self.signal_graph = signal_graph
        self.module_graph = module_graph
    
    def find_path(self, src: str, dst: str) -> Optional[List[str]]:
        """查找从 src 到 dst 的路径
        
        跨模块时自动映射端口→内部信号
        """
        path = [src]
        
        # 1. 如果 src 是端口，映射到内部信号
        internal = self.module_graph.get_internal_signal(src)
        if internal:
            path.append(internal)
            current = internal
        else:
            current = src
        
        # 2. 递归追踪驱动源 (使用图的后继节点)
        visited = set()
        result = self._trace_drivers(current, dst, path, visited)
        
        return result if result else None
    
    def _trace_drivers(self, current: str, dst: str, path: List[str], visited: set) -> Optional[List[str]]:
        """递归追踪驱动目标 (使用 successors，因为边是 driver --> driven)"""
        if current in visited:
            return None
        visited.add(current)
        
        if current == dst:
            return path
        
        # 使用 successors 找驱动目标
        try:
            successors = list(self.signal_graph.successors(current))
        except (KeyError, nx.NetworkXError):
            successors = []
        
        for driven_id in successors:
            path_copy = path.copy()
            path_copy.append(driven_id)
            
            # 如果驱动目标是端口，映射到内部信号
            internal = self.module_graph.get_internal_signal(driven_id)
            if internal:
                path_copy.append(internal)
                next_signal = internal
            else:
                next_signal = driven_id
            
            # 递归追踪
            result = self._trace_drivers(next_signal, dst, path_copy, visited)
            if result:
                return result
        
        return None
    
    def find_all_paths(self, src: str, dst: str) -> List[List[str]]:
        """查找所有路径"""
        paths = []
        path = [src]
        visited = set()
        
        self._find_all_paths_impl(src, dst, path, visited, paths)
        return paths
    
    def _find_all_paths_impl(self, current: str, dst: str, path: List[str], visited: set, paths: List[List[str]]):
        """递归查找所有路径的实现"""
        if current in visited:
            return
        visited.add(current)
        
        if current == dst:
            paths.append(path.copy())
            visited.discard(current)
            return
        
        try:
            drivers = list(self.signal_graph.predecessors(current))
        except (KeyError, nx.NetworkXError):
            drivers = []
        
        for driver_id in drivers:
            path.append(driver_id)
            self._find_all_paths_impl(driver_id, dst, path, visited, paths)
            path.pop()
        
        visited.discard(current)
import networkx as nx
