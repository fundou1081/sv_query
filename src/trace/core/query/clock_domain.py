from enum import Enum
#==============================================================================
# query_clock_domain.py - 场景C: Clock Domain Trace
# 时钟域追踪
#==============================================================================

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
import networkx as nx

from ..graph.models import (
    SignalGraph, TraceNode, TraceEdge, EdgeKind, NodeKind
)

class CrossingRisk(Enum):
    """跨时钟域风险级别"""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ClockDomainTrace:
    """时钟域追踪结果"""
    clock: str
    registers: List[TraceNode] = field(default_factory=list)
    combinational_logic: List[TraceNode] = field(default_factory=list)  # 该域内组合逻辑
    cross_domain_paths: List[TraceEdge] = field(default_factory=list)  # 跨时钟域路径
    reset_tree: List[TraceEdge] = field(default_factory=list)  # 复位树
    confidence: str = "high"
    caveats: List[str] = field(default_factory=list)

class ClockDomainTracer:
    """场景C: 时钟域追踪"""
    
    def __init__(self, graph: SignalGraph):
        self.graph = graph
        self._clock_signals: Dict[str, str] = {}  # signal_id -> clock_domain
    
    def _find_registers_by_clock(self, clock_id: str) -> List[TraceNode]:
        """找到所有被此时钟驱动的寄存器"""
        registers = []
        
        for node_id, node in self.graph._node_data.items():
            if node.kind != NodeKind.REG:
                continue
            
            # 检查是否由此时钟驱动
            for pred in self.graph.predecessors(node_id):
                edge = self.graph.get_edge(pred, node_id)
                if edge and edge.kind == EdgeKind.CLOCK and pred == clock_id:
                    registers.append(node)
                    break
        
        return registers
    
    def _find_combinational_logic(self, registers: List[TraceNode]) -> List[TraceNode]:
        """找寄存器输出驱动的组合逻辑"""
        combinational = []
        
        for reg in registers:
            # 查找后继节点
            for succ in self.graph.successors(reg.id):
                succ_node = self.graph.get_node(succ)
                if succ_node and succ_node.kind == NodeKind.WIRE:
                    combinational.append(succ_node)
        
        return combinational
    
    def _build_timing_chain(self, registers: List[TraceNode]) -> List[List[str]]:
        """构建时序链 (寄存器->寄存器路径)"""
        chains = []
        
        for src_reg in registers:
            for dst_reg in registers:
                if src_reg.id == dst_reg.id:
                    continue
                
                # 检查数据路径
                paths = self.graph.find_all_paths(src_reg.id, dst_reg.id, max_depth=20)
                for path in paths:
                    # 验证都是寄存器
                    if all(self.graph.get_node(n).kind == NodeKind.REG for n in path):
                        chains.append(path)
        
        return chains
    
    def _detect_cross_domain(self, clock_id: str) -> List[TraceEdge]:
        """识别跨时钟域路径"""
        cross_paths = []
        
        # 获取此时钟域的寄存器
        regs = self._find_registers_by_clock(clock_id)
        
        # 遍历所有节点，检测跨域
        for reg in regs:
            for succ in self.graph.successors(reg.id):
                succ_node = self.graph.get_node(succ)
                if not succ_node:
                    continue
                
                # 检查目标节点的时钟域
                if succ_node.id in self._clock_signals:
                    target_clock = self._clock_signals[succ_node.id]
                    if target_clock != clock_id:
                        edge = self.graph.get_edge(reg.id, succ_node.id)
                        if edge:
                            cross_paths.append(edge)
                else:
                    # 如果目标不在已知时钟域，检查是否有其他时钟驱动
                    has_other_clock = False
                    for pred in self.graph.predecessors(succ_node.id):
                        pred_node = self.graph.get_node(pred)
                        if pred_node and pred_node.is_clock:
                            edge = self.graph.get_edge(pred, succ_node.id)
                            if edge and edge.kind == EdgeKind.CLOCK:
                                has_other_clock = True
                                break
                    
                    if has_other_clock:
                        edge = self.graph.get_edge(reg.id, succ_node.id)
                        if edge:
                            cross_paths.append(edge)
        
        return cross_paths
    
    def _build_reset_tree(self, registers: List[TraceNode]) -> List[TraceEdge]:
        """构建复位树"""
        reset_edges = []
        
        for reg in registers:
            for pred in self.graph.predecessors(reg.id):
                pred_node = self.graph.get_node(pred)
                if pred_node and pred_node.is_reset:
                    edge = self.graph.get_edge(pred, reg.id)
                    if edge:
                        reset_edges.append(edge)
        
        return reset_edges
    
    def _assess_risk(self, cross_domain_paths: List[TraceEdge]) -> str:
        """评估风险"""
        if not cross_domain_paths:
            return "high"  # 安全的单域
        
        # 检查是否有同步器
        has_synchronizer = any("sync" in e.dst.lower() for e in cross_domain_paths)
        
        if has_synchronizer:
            return "medium"
        
        count = len(cross_domain_paths)
        if count > 5:
            return "low"
        return "medium"
    
    def _collect_caveats(self, result: ClockDomainTrace) -> List[str]:
        """收集注意事项"""
        caveats = []
        
        # 无寄存器
        if not result.registers:
            caveats.append("No registers found for this clock")
        
        # 无复位树
        if result.registers and not result.reset_tree:
            caveats.append("No reset tree found")
        
        # 跨域风险
        if result.cross_domain_paths:
            if result.confidence == "low":
                caveats.append(f"Found {len(result.cross_domain_paths)} cross-domain paths without synchronizers")
        
        return caveats
    
    def trace(self, clock: str) -> ClockDomainTrace:
        """追踪时钟域"""
        clock_id = clock if "." in clock else f"top.{clock}"
        
        result = ClockDomainTrace(clock=clock)
        
        # 验证时钟存在
        clock_node = self.graph.get_node(clock_id)
        if not clock_node:
            result.caveats.append(f"Clock signal {clock} not found")
            return result
        
        # 1. 找到所有被此时钟驱动的寄存器
        result.registers = self._find_registers_by_clock(clock_id)
        
        # 2. 找组合逻辑
        result.combinational_logic = self._find_combinational_logic(result.registers)
        
        # 3. 识别跨时钟域路径
        result.cross_domain_paths = self._detect_cross_domain(clock_id)
        
        # 4. 构建复位树
        result.reset_tree = self._build_reset_tree(result.registers)
        
        # 5. 评估风险
        result.confidence = self._assess_risk(result.cross_domain_paths)
        
        # 6. 收集注意事项
        result.caveats = self._collect_caveats(result)
        
        return result
    
    def trace_all_domains(self) -> List[ClockDomainTrace]:
        """追踪所有时钟域"""
        domains = []
        
        # 查找所有时钟信号
        for node_id, node in self.graph._node_data.items():
            if node.is_clock:
                result = self.trace(node_id)
                domains.append(result)
        
        return domains
    
    def find_synchronizers(self, clock: str) -> List[str]:
        """查找同步器链"""
        synchronizers = []
        clock_node_id = clock if "." in clock else f"top.{clock}"
        
        # 查找 sync 相关节点
        for node_id, node in self.graph._node_data.items():
            if "sync" in node_id.lower():
                synchronizers.append(node_id)
        
        return synchronizers
    
    def check_cdc_violations(self) -> List[str]:
        """检查 CDC 违规"""
        violations = []
        
        for domain in self.trace_all_domains():
            if domain.cross_domain_paths and domain.confidence == "low":
                for edge in domain.cross_domain_paths:
                    violations.append(
                        f"CDC violation: {edge.src} -> {edge.dst} ({domain.clock})")
        
        return violations
