#==============================================================================
# graph_builder.py - Builder Layer
#==============================================================================

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from .graph_models import SignalGraph, TraceNode, TraceEdge, NodeKind, EdgeKind
from .base import PyslangAdapter

@dataclass
class ExtractorResult:
    nodes: List[TraceNode] = field(default_factory=list)
    edges: List[TraceEdge] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

class DriverExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
    
    def extract(self) -> ExtractorResult:
        result = ExtractorResult()

        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)
            
            # [铁律4] 为端口创建 TraceNode (输入端口作为驱动源)
            ports = self.adapter.get_port_names(module)
            for port in ports:
                port_id = f"{module_name}.{port}"
                if port_id not in [n.id for n in result.nodes]:
                    result.nodes.append(TraceNode(
                        id=port_id,
                        name=port,
                        module=module_name,
                        kind=NodeKind.PORT_IN,
                        width=(1, 0)
                    ))
            
            # [铁律4] 为每个信号创建 TraceNode
            # assign 语句
            for assign in self.adapter.get_assignments(module):
                lhs, rhs = self._parse_assign(assign)
                if lhs and rhs:
                    # 创建 dst 节点
                    dst_node_id = f"{module_name}.{lhs}"
                    if dst_node_id not in [n.id for n in result.nodes]:
                        result.nodes.append(TraceNode(
                            id=dst_node_id, name=lhs, module=module_name,
                            kind=NodeKind.SIGNAL, width=(1, 0)
                        ))
                    # 创建 src 节点
                    src_node_id = f"{module_name}.{rhs}"
                    if src_node_id not in [n.id for n in result.nodes]:
                        result.nodes.append(TraceNode(
                            id=src_node_id, name=rhs, module=module_name,
                            kind=NodeKind.SIGNAL, width=(1, 0)
                        ))
                    result.edges.append(TraceEdge(
                        src=src_node_id, dst=dst_node_id,
                        kind=EdgeKind.DRIVER, assign_type="continuous"
                    ))
            
            # always 块 - [铁律7金标准]
            # 金标准: always_ff @(posedge clk) dout <= data;
            for always in self.adapter.get_always_blocks(module):
                stmts = []
                self._collect_assignments_from_stmt(always, stmts)
                for stmt in stmts:
                    lhs, rhs = self._parse_assign(stmt)
                    if lhs and rhs:
                        dst_node_id = f"{module_name}.{lhs}"
                        if dst_node_id not in [n.id for n in result.nodes]:
                            result.nodes.append(TraceNode(
                                id=dst_node_id, name=lhs, module=module_name,
                                kind=NodeKind.REG, width=(1, 0)
                            ))
                        src_node_id = f"{module_name}.{rhs}"
                        if src_node_id not in [n.id for n in result.nodes]:
                            result.nodes.append(TraceNode(
                                id=src_node_id, name=rhs, module=module_name,
                                kind=NodeKind.SIGNAL, width=(1, 0)
                            ))
                        result.edges.append(TraceEdge(
                            src=src_node_id, dst=dst_node_id,
                            kind=EdgeKind.DRIVER, assign_type="nonblocking"
                        ))
        
        return result

    
    def _collect_assignments_from_stmt(self, node, statements: list, depth=0):
        if node is None or depth > 30:
            return
        
        kind = getattr(node, 'kind', None)
        # [铁律2] 支持所有赋值类型
        kind_str = str(kind) if kind else ''
        if kind and ('Assignment' in kind_str):
            statements.append(node)
            return
        if kind and 'Nonblocking' in kind_str:
            pass  # 继续遍历
        # [P0] 支持 always_comb 阻塞赋值
        #pyslang 10.0: always_comb 用 AssignmentExpression
        if kind and ('Blocking' in kind_str or 'AssignmentExpression' == kind_str):
            statements.append(node)
            return
        # [P0] 支持 always_ff 内部 ExpressionStatement
        if kind and 'ExpressionStatement' in kind_str:
            statements.append(node)
            return
        
        for attr in dir(node):
            if attr.startswith('_'):
                continue
            if attr in ['parent', 'kind', 'sourceRange', 'attributes']:
                continue
            
            try:
                child = getattr(node, attr)
                if callable(child):
                    continue
                if hasattr(child, '__iter__') and not isinstance(child, str):
                    for c in child:
                        self._collect_assignments_from_stmt(c, statements, depth+1)
                elif hasattr(child, 'kind'):
                    self._collect_assignments_from_stmt(child, statements, depth+1)
            except:
                pass
    
    def _parse_assign(self, assign) -> tuple:
        # [P0] 处理 ExpressionStatement (always_ff/always_comb 内部)
        if hasattr(assign, 'expr'):
            assign = assign.expr
        
        try:
            if hasattr(assign, 'assignments') and assign.assignments:
                a = assign.assignments[0]
                lhs = a.left if hasattr(a, 'left') else None
                rhs = a.right if hasattr(a, 'right') else None
            else:
                lhs = getattr(assign, 'left', None) or getattr(assign, 'lhs', None)
                rhs = getattr(assign, 'right', None) or getattr(assign, 'rhs', None)
            
            lhs_name = self._get_signal(lhs)
            rhs_name = self._get_signal(rhs)
            
            return lhs_name, rhs_name
        except:
            return None, None
    
    def _get_signal(self, signal) -> Optional[str]:
        if signal is None:
            return None
        
        name = None
        if hasattr(signal, 'name'):
            name = signal.name.value if hasattr(signal.name, 'value') else str(signal.name)
        elif hasattr(signal, 'value'):
            name = signal.value
        else:
            name = str(signal)
        
        name = self.adapter.clean_name(name) if name else None
        
        # [P2增强] 递归提取复合表达式的操作数
        # 处理三元、拼接、一元、移位等复杂运算符
        special_attrs = ['left', 'right', 'operand', 'ifTrue', 'ifFalse', 
                       'target', 'increment', 'left', 'right']
        for attr in special_attrs:
            if hasattr(signal, attr):
                try:
                    child = getattr(signal, attr)
                    if child and not callable(child):
                        result = self._get_signal(child)
                        if result:
                            return result
                except:
                    pass
        
        # [P0 Fix] 复合表达式处理
        if name:
            # 处理 & | + - 等运算符
            has_binary_op = any(op in name for op in ['&', '|', '+', '-', '^', '<<', '>>'])
            if has_binary_op and hasattr(signal, 'left') and hasattr(signal, 'right'):
                left_name = self._get_signal(signal.left)
                if left_name:
                    return left_name
                right_name = self._get_signal(signal.right)
                if right_name:
                    return right_name
                return None
        
        # [P1增强] 处理拼接: {a,b} -> 提取 values
        if hasattr(signal, 'kind'):
            kind_str = str(signal.kind)
            if 'Replication' in kind_str or 'Concat' in kind_str:
                if hasattr(signal, 'values'):
                    vals = signal.values
                    if vals and len(vals) > 0:
                        first_val = self._get_signal(vals[0])
                        if first_val:
                            return first_val
        
        return name

class LoadExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
    
    def extract(self) -> ExtractorResult:
        result = ExtractorResult()

        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)
            
            # [铁律4] 为端口创建 TraceNode (输入端口作为驱动源)
            ports = self.adapter.get_port_names(module)
            for port in ports:
                port_id = f"{module_name}.{port}"
                if port_id not in [n.id for n in result.nodes]:
                    result.nodes.append(TraceNode(
                        id=port_id,
                        name=port,
                        module=module_name,
                        kind=NodeKind.PORT_IN,
                        width=(1, 0)
                    ))
            
            for assign in self.adapter.get_assignments(module):
                lhs, rhs = self._parse_assign(assign)
                if lhs and rhs:
                    result.edges.append(TraceEdge(
                        src=f"{module_name}.{rhs}",
                        dst=f"{module_name}.{lhs}",
                        kind=EdgeKind.DRIVER
                    ))
        
        return result
    
    def _parse_assign(self, assign) -> tuple:
        # [铁律2] 支持所有赋值语法结构
        try:
            if hasattr(assign, 'assignments') and assign.assignments:
                # ContinuousAssign
                a = assign.assignments[0]
                lhs = a.left if hasattr(a, 'left') else None
                rhs = a.right if hasattr(a, 'right') else None
            elif hasattr(assign, 'left') and hasattr(assign, 'right'):
                # NonblockingAssignmentExpression / BlockingAssignmentExpression
                lhs = getattr(assign, 'left', None)
                rhs = getattr(assign, 'right', None)
            
            lhs_name = self._get_signal(lhs)
            rhs_name = self._get_signal(rhs)
            
            return lhs_name, rhs_name
        except:
            return None, None
    
    def _get_signal(self, signal) -> Optional[str]:
        if signal is None:
            return None
        
        name = None
        if hasattr(signal, 'name'):
            name = signal.name.value if hasattr(signal.name, 'value') else str(signal.name)
        else:
            name = str(signal)
        
        return self.adapter.clean_name(name) if name else None

class ConnectionExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
    
    def extract(self) -> ExtractorResult:
        result = ExtractorResult()
        
        trees = getattr(self.adapter.parser, 'trees', {})
        instances = self.adapter.get_module_instances(trees)
        
        for inst in instances:
            inst_name = inst.decl.value if hasattr(inst.decl, 'value') else str(inst.decl)
            
            conns = self.adapter.get_instance_connection(inst)
            
            for port_name, signal_name in conns:
                port_name = self.adapter.clean_name(port_name)
                signal_name = self.adapter.clean_name(signal_name)
                
                # driver edge: external -> port
                result.edges.append(TraceEdge(
                    src=f"top.{signal_name}",
                    dst=f"{inst_name}.{port_name}",
                    kind=EdgeKind.DRIVER,
                    assign_type="connection"
                ))
        
        return result

class ClockDomainExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
    
    def extract(self) -> ExtractorResult:
        result = ExtractorResult()

        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)
            
            # [铁律4] 为端口创建 TraceNode (输入端口作为驱动源)
            ports = self.adapter.get_port_names(module)
            for port in ports:
                port_id = f"{module_name}.{port}"
                if port_id not in [n.id for n in result.nodes]:
                    result.nodes.append(TraceNode(
                        id=port_id,
                        name=port,
                        module=module_name,
                        kind=NodeKind.PORT_IN,
                        width=(1, 0)
                    ))
            
            for port in self.adapter.get_port_names(module):
                port_name, direction = self.adapter.get_port_name_and_direction(port)
                if not port_name:
                    continue
                
                port_name = self.adapter.clean_name(port_name)
                
                is_clock = 'clk' in port_name.lower()
                is_reset = 'rst' in port_name.lower()
                
                if is_clock or is_reset:
                    result.nodes.append(TraceNode(
                        id=f"{module_name}.{port_name}",
                        name=port_name,
                        module=module_name,
                        kind=NodeKind.PORT_IN,
                        width=(1, 0),
                        is_clock=is_clock,
                        is_reset=is_reset
                    ))
        
        return result

class GraphBuilder:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
        self.graph = SignalGraph()
        self._extractors = {
            'driver': DriverExtractor(adapter),
            'load': LoadExtractor(adapter),
            'connection': ConnectionExtractor(adapter),
            'clock': ClockDomainExtractor(adapter),
        }
    
    def build(self) -> SignalGraph:
        self._extract_all_nodes()
        self._extract_all_edges()
        self._mark_special_signals()
        return self.graph
    
    def get_extractor(self, name):
        return self._extractors.get(name)
    
    def _extract_all_nodes(self):
        for name, extractor in self._extractors.items():
            result = extractor.extract()
            for node in result.nodes:
                self.graph.add_trace_node(node)
    
    def _extract_all_edges(self):
        for name, extractor in self._extractors.items():
            result = extractor.extract()
            for edge in result.edges:
                self.graph.add_trace_edge(edge)
    
    def _mark_special_signals(self):
        for node_id, node in self.graph._node_data.items():
            name_lower = node.name.lower()
            
            if 'clk' in name_lower or 'clock' in name_lower:
                node.is_clock = True
            
            if 'rst' in name_lower or 'reset' in name_lower:
                node.is_reset = True
    
    def stats(self) -> Dict:
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            **self.graph.stats()
        }
