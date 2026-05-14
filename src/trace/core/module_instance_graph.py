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
from .graph.models import EdgeKind
import networkx as nx
import logging

logger = logging.getLogger(__name__)

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
    
    def __init__(self, adapter, signal_graph=None):
        self.adapter = adapter
        self.signal_graph = signal_graph  # 可选，用于从 SignalGraph 获取 port_to_internal
        self.instances: Dict[str, ModuleInstanceNode] = {}  # instance_id → Node
        self.port_to_internal: Dict[str, str] = {}  # "top.u_dut.clk" → "dut.clk" (保留用于兼容，已废弃)
        self.internal_to_port: Dict[str, str] = {}  # "dut.clk" → "top.u_dut.clk" (保留用于兼容，已废弃)
        
    def _get_parent_module_name(self, inst) -> str:
        """Safely get parent module name from instance (handles generate blocks)."""
        node = inst
        for _ in range(5):
            if not hasattr(node, 'parent') or node.parent is None:
                break
            node = node.parent
            if type(node).__name__ == 'ModuleDeclarationSyntax':
                if hasattr(node, 'header') and hasattr(node.header, 'name'):
                    return node.header.name.rawText.strip()
                elif hasattr(node, 'name'):
                    return node.name.rawText.strip()
        return 'unknown'

    def _get_generate_block_name(self, inst) -> Optional[str]:
        """Get the generate block label if instance is inside a generate block."""
        node = inst
        for _ in range(5):
            if not hasattr(node, 'parent') or node.parent is None:
                break
            node = node.parent
            if type(node).__name__ == 'GenerateBlockSyntax':
                if hasattr(node, 'beginName') and node.beginName:
                    bn = node.beginName
                    if hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                        return bn.name.value.strip()
        return None

    def _get_parent_path(self, inst) -> str:
        """Build parent path up to module level."""
        parts = []
        node = inst
        for _ in range(5):
            if not hasattr(node, 'parent') or node.parent is None:
                break
            node = node.parent
            kind_str = type(node).__name__
            if kind_str == 'ModuleDeclarationSyntax':
                if hasattr(node, 'header') and hasattr(node.header, 'name'):
                    parts.append(node.header.name.rawText.strip())
                break
            elif kind_str == 'GenerateBlockSyntax':
                if hasattr(node, 'beginName') and node.beginName:
                    bn = node.beginName
                    if hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                        parts.append(bn.name.value.strip())
        if parts:
            parts.reverse()
            return '.'.join(parts)
        return 'unknown'

    def build(self, trees: Dict[str, any]):
        """构建模块实例图 (三阶段:
        Phase 0: 存储所有模块的端口定义
        Phase 1: 收集所有实例化信息 (全树遍历)
        Phase 2: 对每个实例路径递归处理模块内容)
        """
        # Phase 0: 遍历所有模块，存储端口定义，建立 module AST 缓存
        self._module_ast_cache = {}  # module_name -> AST node
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
                            self._store_module_ports(module_name, member)
                            self._module_ast_cache[module_name] = member
            else:
                module_name = self._get_module_name(root)
                if module_name:
                    self._store_module_ports(module_name, root)
                    self._module_ast_cache[module_name] = root

        # Phase 1: 收集所有实例化信息 (全树遍历)
        # 每个条目: {module_type, inst_name, instance_path}
        all_instance_info = []
        for fname, tree in trees.items():
            if not tree or not hasattr(tree, 'root'):
                continue
            self._find_all_hierarchy_instantiations(tree.root, all_instance_info, parent_path='')

        # Phase 2: 建立 module_name -> [instance_paths] 映射
        # 例如: 'inner' -> ['top.outer']
        module_to_paths = {}
        for info in all_instance_info:
            inst_path = info['instance_path']
            mod_type = info['module_type']
            if mod_type not in module_to_paths:
                module_to_paths[mod_type] = []
            module_to_paths[mod_type].append(inst_path)

        # Phase 3: 对每个顶层模块，在其所有实例路径上处理模块内容
        for fname, tree in trees.items():
            if not tree or not hasattr(tree, 'root'):
                continue
            root = tree.root
            if hasattr(root, 'kind') and 'CompilationUnit' in str(root.kind):
                for member in getattr(root, 'members', []):
                    kind_str = str(getattr(member, 'kind', ''))
                    if 'ModuleDeclaration' not in kind_str:
                        continue
                    module_name = self._get_module_name(member)
                    if not module_name:
                        continue
                    logger.debug(f"Processing ModuleDeclaration: {module_name}")
                    # 如果是被其他模块实例化的模块，不在这里处理
                    # 这些模块只应该通过父模块的递归调用来处理
                    if module_name in module_to_paths:
                        # 这些模块将在父模块处理 HierarchyInstantiation 时被递归处理
                        # 例如: parent 模块实例化 child，父模块 top 处理 inner 的 HierarchyInstantiation 时
                        # 会递归调用 _process_module_at_path(inner_ast, 'top.outer', ...)
                        continue
                    else:
                        # 顶层模块，没有实例化路径（如 tb.top）
                        self._process_module_at_path(member, module_name, module_to_paths)

    def _find_all_hierarchy_instantiations(self, node, result_list, parent_path=''):
        """全树遍历，找到所有 HierarchyInstantiation 并构建完整路径

        Returns:
            List of dicts: {module_type, inst_name, instance_path}
        """
        if node is None:
            return

        kind = getattr(node, 'kind', None)
        kind_str = str(kind) if kind else ''

        # LoopGenerate: 记录 generate block 标签，继续遍历
        if 'LoopGenerate' in kind_str:
            gen_label = None
            if hasattr(node, 'block') and hasattr(node.block, 'beginName'):
                bn = node.block.beginName
                if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                    gen_label = bn.name.value.strip()
            new_path = f"{parent_path}.{gen_label}" if gen_label and parent_path else (gen_label or parent_path)
            if hasattr(node, 'block'):
                for child in getattr(node.block, 'members', []):
                    self._find_all_hierarchy_instantiations(child, result_list, new_path)
            return

        # IfGenerate
        if 'IfGenerate' in kind_str:
            gen_label = None
            if hasattr(node, 'block') and hasattr(node.block, 'beginName'):
                bn = node.block.beginName
                if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                    gen_label = bn.name.value.strip()
            new_path = f"{parent_path}.{gen_label}" if gen_label and parent_path else (gen_label or parent_path)
            if hasattr(node, 'block'):
                for child in getattr(node.block, 'members', []):
                    self._find_all_hierarchy_instantiations(child, result_list, new_path)
            if hasattr(node, 'elseClause') and node.elseClause:
                else_node = getattr(node.elseClause, 'clause', None)
                if else_node and hasattr(else_node, 'members'):
                    for child in getattr(else_node, 'members', []):
                        self._find_all_hierarchy_instantiations(child, result_list, new_path)
            return

        # CaseGenerate
        if 'CaseGenerate' in kind_str:
            if hasattr(node, 'items'):
                for item in node.items:
                    gen_label = None
                    if hasattr(item, 'block') and hasattr(item.block, 'beginName'):
                        bn = item.block.beginName
                        if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                            gen_label = bn.name.value.strip()
                    new_path = f"{parent_path}.{gen_label}" if gen_label and parent_path else (gen_label or parent_path)
                    if hasattr(item, 'block'):
                        for child in getattr(item.block, 'members', []):
                            self._find_all_hierarchy_instantiations(child, result_list, new_path)
            return

        # HierarchyInstantiation: 找到模块实例化
        if 'HierarchyInstantiation' in kind_str:
            module_type = self._get_module_name_from_type(node)
            instances_list = getattr(node, 'instances', None)
            if instances_list and module_type:
                for elem in instances_list:
                    elem_kind = str(getattr(elem, 'kind', ''))
                    if 'HierarchicalInstance' not in elem_kind:
                        continue
                    decl = getattr(elem, 'decl', None)
                    if not decl:
                        continue
                    name_obj = getattr(decl, 'name', None)
                    if not name_obj or not hasattr(name_obj, 'value'):
                        continue
                    inst_name = str(name_obj.value).strip()
                    if inst_name:
                        instance_path = f"{parent_path}.{inst_name}" if parent_path else inst_name
                        result_list.append({
                            'module_type': module_type,
                            'inst_name': inst_name,
                            'instance_path': instance_path,
                        })
            return

        # 只有特定的父节点类型才需要递归遍历包含实例的子节点
        # - CompilationUnit: 顶层容器，包含 ModuleDeclaration 列表
        # - ModuleDeclaration: 模块定义容器，包含 generate region 和实例
        # - GenerateRegion: generate 块容器，包含 LoopGenerate/IfGenerate/CaseGenerate
        # - LoopGenerate/IfGenerate/CaseGenerate: 包含 HierarchyInstantiation 或嵌套 generate
        # - HierarchyInstantiation: 记录后直接返回（无实例子节点）
        should_recurse = ('CompilationUnit' in kind_str) or \
                        ('ModuleDeclaration' in kind_str) or \
                        ('GenerateRegion' in kind_str) or \
                        'LoopGenerate' in kind_str or \
                        'IfGenerate' in kind_str or \
                        'CaseGenerate' in kind_str
        if should_recurse:
            for child in self._iter_children(node):
                self._find_all_hierarchy_instantiations(child, result_list, parent_path)

    def _process_module_at_path(self, module_node, base_path, module_to_paths):
        """在给定的实例路径上处理模块内容

        Args:
            module_node: 模块的 ModuleDeclarationSyntax AST 节点
            base_path: 当前实例路径 (如 'top.outer' 或 'top')
            module_to_paths: module_name -> [instance_paths] 映射
        """
        if module_node is None:
            return

        # 遍历模块的成员
        for child in self._iter_children(module_node):
            if child is None:
                continue
            kind_str = str(getattr(child, 'kind', ''))

            # LoopGenerate
            if 'LoopGenerate' in kind_str:
                gen_label = None
                if hasattr(child, 'block') and hasattr(child.block, 'beginName'):
                    bn = child.block.beginName
                    if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                        gen_label = bn.name.value.strip()
                new_path = f"{base_path}.{gen_label}" if gen_label else base_path
                if hasattr(child, 'block'):
                    for gc in getattr(child.block, 'members', []):
                        self._process_child_at_path(gc, new_path, module_to_paths)
                continue

            # IfGenerate
            if 'IfGenerate' in kind_str:
                gen_label = None
                if hasattr(child, 'block') and hasattr(child.block, 'beginName'):
                    bn = child.block.beginName
                    if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                        gen_label = bn.name.value.strip()
                new_path = f"{base_path}.{gen_label}" if gen_label else base_path
                if hasattr(child, 'block'):
                    for gc in getattr(child.block, 'members', []):
                        self._process_child_at_path(gc, new_path, module_to_paths)
                if hasattr(child, 'elseClause') and child.elseClause:
                    else_node = getattr(child.elseClause, 'clause', None)
                    if else_node and hasattr(else_node, 'members'):
                        for gc in getattr(else_node, 'members', []):
                            self._process_child_at_path(gc, new_path, module_to_paths)
                continue

            # CaseGenerate
            if 'CaseGenerate' in kind_str:
                if hasattr(child, 'items'):
                    for item in child.items:
                        gen_label = None
                        if hasattr(item, 'block') and hasattr(item.block, 'beginName'):
                            bn = item.block.beginName
                            if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                                gen_label = bn.name.value.strip()
                        new_path = f"{base_path}.{gen_label}" if gen_label else base_path
                        if hasattr(item, 'block'):
                            for gc in getattr(item.block, 'members', []):
                                self._process_child_at_path(gc, new_path, module_to_paths)
                continue

            # GenerateRegion: generate ... endgenerate 块容器
            if 'GenerateRegion' in kind_str:
                if hasattr(child, 'members'):
                    for gc in getattr(child, 'members', []):
                        self._process_child_at_path(gc, base_path, module_to_paths)
                continue

            # HierarchyInstantiation: 创建实例
            if 'HierarchyInstantiation' in kind_str:
                module_type = self._get_module_name_from_type(child)
                self._extract_module_instantiation(child, base_path)
                # 如果被实例化的模块自身还有子实例，递归处理
                if module_type and module_type in module_to_paths:
                    instances_list = getattr(child, 'instances', None)
                    if instances_list:
                        for elem in instances_list:
                            elem_kind = str(getattr(elem, 'kind', ''))
                            if 'HierarchicalInstance' not in elem_kind:
                                continue
                            decl = getattr(elem, 'decl', None)
                            if not decl:
                                continue
                            name_obj = getattr(decl, 'name', None)
                            if not name_obj or not hasattr(name_obj, 'value'):
                                continue
                            inst_name = str(name_obj.value).strip()
                            inst_path = f"{base_path}.{inst_name}"
                            # 找到该模块的 AST 定义并递归
                            if module_type in self._module_ast_cache:
                                child_module_ast = self._module_ast_cache[module_type]
                                self._process_module_at_path(child_module_ast, inst_path, module_to_paths)
                continue

    def _process_child_at_path(self, node, base_path, module_to_paths):
        """处理 generate block 内的子节点"""
        if node is None:
            return
        kind_str = str(getattr(node, 'kind', ''))

        if 'HierarchyInstantiation' in kind_str:
            module_type = self._get_module_name_from_type(node)
            self._extract_module_instantiation(node, base_path)
            if module_type and module_type in module_to_paths:
                instances_list = getattr(node, 'instances', None)
                if instances_list:
                    for elem in instances_list:
                        elem_kind = str(getattr(elem, 'kind', ''))
                        if 'HierarchicalInstance' not in elem_kind:
                            continue
                        decl = getattr(elem, 'decl', None)
                        if not decl:
                            continue
                        name_obj = getattr(decl, 'name', None)
                        if not name_obj or not hasattr(name_obj, 'value'):
                            continue
                        inst_name = str(name_obj.value).strip()
                        inst_path = f"{base_path}.{inst_name}"
                        if module_type in self._module_ast_cache:
                            child_module_ast = self._module_ast_cache[module_type]
                            self._process_module_at_path(child_module_ast, inst_path, module_to_paths)
            return

        if 'LoopGenerate' in kind_str:
            gen_label = None
            if hasattr(node, 'block') and hasattr(node.block, 'beginName'):
                bn = node.block.beginName
                if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                    gen_label = bn.name.value.strip()
            new_path = f"{base_path}.{gen_label}" if gen_label else base_path
            if hasattr(node, 'block'):
                for gc in getattr(node.block, 'members', []):
                    self._process_child_at_path(gc, new_path, module_to_paths)
            return

        if 'IfGenerate' in kind_str:
            gen_label = None
            if hasattr(node, 'block') and hasattr(node.block, 'beginName'):
                bn = node.block.beginName
                if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                    gen_label = bn.name.value.strip()
            new_path = f"{base_path}.{gen_label}" if gen_label else base_path
            if hasattr(node, 'block'):
                for gc in getattr(node.block, 'members', []):
                    self._process_child_at_path(gc, new_path, module_to_paths)
            if hasattr(node, 'elseClause') and node.elseClause:
                else_node = getattr(node.elseClause, 'clause', None)
                if else_node and hasattr(else_node, 'members'):
                    for gc in getattr(else_node, 'members', []):
                        self._process_child_at_path(gc, new_path, module_to_paths)
            return

        if 'CaseGenerate' in kind_str:
            if hasattr(node, 'items'):
                for item in node.items:
                    gen_label = None
                    if hasattr(item, 'block') and hasattr(item.block, 'beginName'):
                        bn = item.block.beginName
                        if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                            gen_label = bn.name.value.strip()
                    new_path = f"{base_path}.{gen_label}" if gen_label else base_path
                    if hasattr(item, 'block'):
                        for gc in getattr(item.block, 'members', []):
                            self._process_child_at_path(gc, new_path, module_to_paths)
            return

    def _extract_instances(self, node, parent_path: str):
        """递归提取模块实例（支持 generate block）"""
        from pyslang import SyntaxKind

        if node is None:
            return

        kind = getattr(node, 'kind', None)
        if kind is None:
            return

        kind_str = str(kind)

        # ModuleDeclaration - 递归提取，不更新 parent_path（顶层模块）
        if 'ModuleDeclaration' in kind_str:
            module_name = self._get_module_name(node)
            if module_name:
                self._store_module_ports(module_name, node)
            for child in self._iter_children(node):
                self._extract_instances(child, parent_path)
            return

        # LoopGenerate: for (...) begin : GEN ... end
        if 'LoopGenerate' in kind_str:
            gen_label = None
            if hasattr(node, 'block') and hasattr(node.block, 'beginName'):
                bn = node.block.beginName
                if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                    gen_label = bn.name.value.strip()
            if gen_label:
                new_path = f"{parent_path}.{gen_label}" if parent_path else gen_label
            else:
                new_path = parent_path
            # 递归进入 block.members
            if hasattr(node, 'block'):
                block = node.block
                if hasattr(block, 'members'):
                    for child in block.members:
                        self._extract_instances(child, new_path)
            return

        # IfGenerate: if (...) begin : COND ... end else ...
        if 'IfGenerate' in kind_str:
            gen_label = None
            if hasattr(node, 'block') and hasattr(node.block, 'beginName'):
                bn = node.block.beginName
                if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                    gen_label = bn.name.value.strip()
            new_path = f"{parent_path}.{gen_label}" if gen_label and parent_path else (gen_label or parent_path)
            # then block
            if hasattr(node, 'block'):
                block = node.block
                if hasattr(block, 'members'):
                    for child in block.members:
                        self._extract_instances(child, new_path)
            # else block
            if hasattr(node, 'elseClause') and node.elseClause:
                else_node = getattr(node.elseClause, 'clause', None)
                if else_node and hasattr(else_node, 'members'):
                    for child in else_node.members:
                        self._extract_instances(child, new_path)
            return

        # CaseGenerate: case (...) ... endcase
        if 'CaseGenerate' in kind_str:
            if hasattr(node, 'items'):
                for item in node.items:
                    gen_label = None
                    if hasattr(item, 'block') and hasattr(item.block, 'beginName'):
                        bn = item.block.beginName
                        if bn and hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                            gen_label = bn.name.value.strip()
                    new_path = f"{parent_path}.{gen_label}" if gen_label and parent_path else (gen_label or parent_path)
                    if hasattr(item, 'block') and hasattr(item.block, 'members'):
                        for child in item.block.members:
                            self._extract_instances(child, new_path)
            return

        # HierarchyInstantiation - 提取模块实例（使用当前 parent_path）
        if 'HierarchyInstantiation' in kind_str:
            self._extract_module_instantiation(node, parent_path)
            return

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
        
        # 如果 ANSI 风格没有找到端口，尝试从 members 的 PortDeclaration 获取
        if not ports:
            for member in getattr(node, 'members', []):
                kind_str = str(getattr(member, 'kind', ''))
                if 'PortDeclaration' not in kind_str:
                    continue
                
                # Get direction from header
                direction = 'unknown'
                if hasattr(member, 'header') and member.header:
                    direction = str(getattr(member.header, 'direction', 'unknown')).strip()
                
                # Get port names from declarators
                declarators = getattr(member, 'declarators', None)
                if declarators:
                    # declarators might be a SeparatedList or simple list
                    decl_list = []
                    if hasattr(declarators, 'elements'):
                        decl_list = list(declarators.elements)
                    elif hasattr(declarators, '__iter__') and not isinstance(declarators, str):
                        decl_list = list(declarators)
                    else:
                        decl_list = [declarators]
                    
                    for decl in decl_list:
                        # decl is DeclaratorSyntax with .name
                        name = None
                        if hasattr(decl, 'name') and decl.name:
                            name_val = decl.name
                            if hasattr(name_val, 'value'):
                                name = str(name_val.value)
                            else:
                                name = str(name_val)
                        
                        if not name or name == ',':
                            continue
                        
                        ports[name] = PortInfo(
                            name=name,
                            direction=direction,
                            width=(0, 0),
                            internal_signal=f"{module_name}.{name}",
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
    
    def _get_module_name_from_type(self, node) -> Optional[str]:
        """从 HierarchyInstantiation 的 type 属性获取模块类型名。"""
        inst_type = getattr(node, 'type', None)
        if inst_type is None:
            return None
        # 使用 .value 属性（Token 对象），而非 str() 转换
        if hasattr(inst_type, 'value') and inst_type.value:
            return inst_type.value.strip()
        # 备用：直接取 token text
        if hasattr(inst_type, 'rawText'):
            return inst_type.rawText.strip()
        return None

    def _extract_module_instantiation(self, node, parent_path: str):
        """提取模块实例化 (HierarchyInstantiation)

        HierarchyInstantiation:
          - type: 模块类型名
          - instances: SeparatedList[HierarchicalInstance]

        HierarchicalInstance:
          - decl: InstanceName (有 .name.value)
          - connections: 端口连接列表
        """
        # 获取模块类型 (使用 AST 属性，不做字符串转换)
        module_type = self._get_module_name_from_type(node)
        if not module_type:
            return

        # 获取实例列表 (SeparatedList)
        instances_list = getattr(node, 'instances', None)
        if not instances_list:
            return

        # 遍历每个 HierarchicalInstance
        for elem in instances_list:
            elem_kind = getattr(elem, 'kind', None)
            elem_kind_str = str(elem_kind) if elem_kind else ''
            if 'HierarchicalInstance' not in elem_kind_str:
                continue

            # 获取实例名: elem.decl.name.value
            decl = getattr(elem, 'decl', None)
            if not decl:
                continue

            name_obj = getattr(decl, 'name', None)
            if not name_obj or not hasattr(name_obj, 'value'):
                continue

            instance_name = str(name_obj.value).strip()
            if not instance_name:
                continue

            # 构造完整实例ID: parent_path 已包含 generate block 信息
            if parent_path:
                instance_id = f"{parent_path}.{instance_name}"
            else:
                instance_id = instance_name

            # 创建实例节点（避免重复）
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
        
        MIG 维护自己的 port_to_internal 映射，基于模块端口定义（而非实际连接）。
        CE 的 port_to_internal 来自实际连接，用于 SignalGraph 建边。
        两者语义不同：
          - MIG: 模块 Z 有端口 X，内部信号是 Z.X（结构定义）
          - CE: 实例的端口 X 实际连接到信号 Y（实际连接）
        
        Args:
            port_path: "top.u_dut.clk"
            
        Returns:
            "dut.clk" 或 None
        """
        # MIG 自己的映射（基于模块定义）
        if self.port_to_internal:
            return self.port_to_internal.get(port_path)
        # 备用：从 SignalGraph 获取（CE 构建的连接映射）
        if self.signal_graph is not None:
            return self.signal_graph.get_internal_signal(port_path)
        return None
    
    def get_port_path(self, internal_signal: str) -> Optional[str]:
        """内部信号 → 端口路径
        
        Args:
            internal_signal: "dut.clk"
            
        Returns:
            "top.u_dut.clk" 或 None
        """
        # MIG 自己的映射（基于模块定义）
        if self.internal_to_port:
            return self.internal_to_port.get(internal_signal)
        # 备用：从 SignalGraph 获取（CE 构建的连接映射）
        if self.signal_graph is not None:
            port_to_internal = self.signal_graph.get_port_to_internal()
            # 反向查找
            for inst_port, internal in port_to_internal.items():
                if internal == internal_signal:
                    return inst_port
        return None
    
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
        """递归查找所有路径的实现 (使用 successors)"""
        if current in visited:
            return
        visited.add(current)
        
        if current == dst:
            paths.append(path.copy())
            visited.discard(current)
            return
        
        try:
            successors = list(self.signal_graph.successors(current))
        except (KeyError, nx.NetworkXError):
            successors = []
        
        for driven_id in successors:
            path.append(driven_id)
            self._find_all_paths_impl(driven_id, dst, path, visited, paths)
            path.pop()
        
        visited.discard(current)
