#==============================================================================
# graph_builder.py - Builder Layer
# 统一图构建器 - 一次性构建全图
#==============================================================================

from typing import Dict, List, Optional
from dataclasses import dataclass, field

from graph_models import (
    SignalGraph, TraceNode, TraceEdge, NodeKind, EdgeKind
)

@dataclass
class ExtractorResult:
    """提取器结果"""
    nodes: List[TraceNode] = field(default_factory=list)
    edges: List[TraceEdge] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

class DriverExtractor:
    """Driver 提取器"""
    
    def __init__(self, parser):
        self.parser = parser
    
    def extract(self) -> ExtractorResult:
        """提取所有驱动关系"""
        result = ExtractorResult()
        
        # 遍历模块
        for module in self.parser.modules:
            for assignment in module.assignments:
                # 提取 lhs -> rhs 驱动关系
                lhs_node = self._create_node(assignment.lhs, module.name)
                rhs_node = self._create_node(assignment.rhs, module.name)
                
                result.nodes.extend([lhs_node, rhs_node])
                
                edge = TraceEdge(
                    src=rhs_node.id,
                    dst=lhs_node.id,
                    kind=EdgeKind.DRIVER,
                    assign_type="continuous"
                )
                result.edges.append(edge)
            
            # 遍历 always 块
            for always in module.always_blocks:
                # 提取阻塞/非阻塞赋值
                for stmt in always.statements:
                    lhs = stmt.lhs
                    rhs = stmt.rhs
                    assign_type = stmt.blocking and "blocking" or "nonblocking"
                    
                    src_node = self._create_node(rhs, module.name)
                    dst_node = self._create_node(lhs, module.name)
                    
                    result.nodes.extend([src_node, dst_node])
                    
                    edge = TraceEdge(
                        src=src_node.id,
                        dst=dst_node.id,
                        kind=EdgeKind.DRIVER,
                        assign_type=assign_type
                    )
                    result.edges.append(edge)
        
        return result
    
    def _create_node(self, signal, module):
        """创建节点"""
        return TraceNode(
            id=f"{module}.{signal.name}",
            name=signal.name,
            module=module,
            kind=NodeKind.WIRE,
            width=signal.width
        )

class LoadExtractor:
    """Load 提取器"""
    
    def __init__(self, parser):
        self.parser = parser
    
    def extract(self) -> ExtractorResult:
        """提取负载关系"""
        result = ExtractorResult()
        
        for module in self.parser.modules:
            for assignment in module.assignments:
                # rhs 的负载是 lhs
                src = self._create_node(assignment.rhs, module.name)
                dst = self._create_node(assignment.lhs, module.name)
                
                edge = TraceEdge(
                    src=src.id,
                    dst=dst.id,
                    kind=EdgeKind.DATA
                )
                result.edges.append(edge)
        
        return result
    
    def _create_node(self, signal, module):
        return TraceNode(
            id=f"{module}.{signal.name}",
            name=signal.name,
            module=module,
            kind=NodeKind.WIRE,
            width=signal.width
        )

class ConnectionExtractor:
    """连接提取器 - 模块端口"""
    
    def __init__(self, parser):
        self.parser = parser
    
    def extract(self) -> ExtractorResult:
        """提取模块端口连接"""
        result = ExtractorResult()
        
        for inst in self.parser.module_instances:
            # 端口映射
            for port_name, signal in inst.port_map.items():
                # 模块端口 -> 外部信号
                port_node = TraceNode(
                    id=f"{inst.module}.{port_name}",
                    name=port_name,
                    module=inst.module,
                    kind=NodeKind.PORT_IN if inst.is_input(port_name) else NodeKind.PORT_OUT
                )
                
                signal_node = TraceNode(
                    id=f"{inst.parent}.{signal.name}",
                    name=signal.name,
                    module=inst.parent,
                    kind=NodeKind.WIRE
                )
                
                result.nodes.extend([port_node, signal_node])
                
                edge = TraceEdge(
                    src=signal_node.id,
                    dst=port_node.id,
                    kind=EdgeKind.CONNECTION
                )
                result.edges.append(edge)
        
        return result

class ClockDomainExtractor:
    """时钟域提取器"""
    
    def __init__(self, parser):
        self.parser = parser
    
    def extract(self) -> ExtractorResult:
        """提取时钟域"""
        result = ExtractorResult()
        
        for module in self.parser.modules:
            for port in module.ports:
                if port.is_clock:
                    node = TraceNode(
                        id=f"{module}.{port.name}",
                        name=port.name,
                        module=module,
                        kind=NodeKind.PORT_IN,
                        is_clock=True
                    )
                    result.nodes.append(node)
                    
                elif port.is_reset:
                    node = TraceNode(
                        id=f"{module}.{port.name}",
                        name=port.name,
                        module=module,
                        kind=NodeKind.PORT_IN,
                        is_reset=True
                    )
                    result.nodes.append(node)
        
        return result

class GraphBuilder:
    """统一图构建器 - 一次性构建全图"""
    
    def __init__(self, parser):
        self.parser = parser
        self.graph = SignalGraph()
        self._extractors = {
            'driver': DriverExtractor(parser),
            'load': LoadExtractor(parser),
            'connection': ConnectionExtractor(parser),
            'clock_domain': ClockDomainExtractor(parser),
        }
    
    def build(self) -> SignalGraph:
        """构建完整信号图"""
        # 1. 提取所有节点
        self._extract_all_nodes()
        
        # 2. 提取所有边
        self._extract_all_edges()
        
        # 3. 分类标记 (clock/reset/enable)
        self._mark_special_signals()
        
        return self.graph
    
    def get_extractor(self, name: str):
        """获取提取器"""
        return self._extractors.get(name)
    
    def _extract_all_nodes(self):
        """提取所有节点"""
        for name, extractor in self._extractors.items():
            result = extractor.extract()
            
            for node in result.nodes:
                self.graph.add_trace_node(node)
    
    def _extract_all_edges(self):
        """提取所有边"""
        for name, extractor in self._extractors.items():
            result = extractor.extract()
            
            for edge in result.edges:
                self.graph.add_trace_edge(edge)
    
    def _mark_special_signals(self):
        """标记特殊信号 (clock/reset/enable)"""
        for node_id, node in self.graph._node_data.items():
            name_lower = node.name.lower()
            
            # 时钟
            if "clk" in name_lower or "clock" in name_lower:
                node.is_clock = True
                # 添加 CLOCK 边
                for succ in self.graph.successors(node_id):
                    edge = self.graph.get_edge(node_id, succ)
                    if edge:
                        edge.kind = EdgeKind.CLOCK
            
            # 复位
            if "rst" in name_lower or "reset" in name_lower or "nRst" in name_lower:
                node.is_reset = True
                for succ in self.graph.successors(node_id):
                    edge = self.graph.get_edge(node_id, succ)
                    if edge:
                        edge.kind = EdgeKind.RESET
            
            # 使能
            if "en" in name_lower or "enable" in name_lower:
                node.is_enable = True
                for succ in self.graph.successors(node_id):
                    edge = self.graph.get_edge(node_id, succ)
                    if edge:
                        edge.kind = EdgeKind.ENABLE
    
    def stats(self) -> Dict:
        """统计信息"""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            **self.graph.stats()
        }
