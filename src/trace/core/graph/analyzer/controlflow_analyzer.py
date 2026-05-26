# ControlFlow Analyzer - 控制流分析器
# 基于 SignalGraph 的边 condition 信息进行控制流分析

from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict

from ...graph_builder import GraphBuilder
from ..models import TraceEdge, EdgeKind
from ..dataflow import DataFlowResult


@dataclass
class ConditionInfo:
    """条件信息"""
    expr: str                    # 条件表达式 "rst_n && en"
    edge: TraceEdge             # 对应的边
    
    @property
    def signals(self) -> List[str]:
        """提取条件中的信号"""
        # 简化: 用字符串提取变量名
        # 后续可以用 SignalExpressionVisitor
        signals = []
        current = ""
        for c in self.expr:
            if c.isalnum() or c == '_':
                current += c
            else:
                if current and current not in ('0', '1'):
                    signals.append(current)
                current = ""
        if current and current not in ('0', '1'):
            signals.append(current)
        return signals


@dataclass  
class ConditionedDriver:
    """同一目标的多个条件驱动边"""
    to_node: str                # 目标节点 "top.q"
    edges: List[TraceEdge]      # 所有到达该节点的边
    
    @property
    def conditions(self) -> List[ConditionInfo]:
        """获取所有条件"""
        return [
            ConditionInfo(expr=e.condition, edge=e) 
            for e in self.edges if e.condition
        ]
    
    @property
    def has_branches(self) -> bool:
        """是否有多个分支"""
        return len([e for e in self.edges if e.condition]) > 1
    
    def get_coverage_info(self) -> Dict[str, Any]:
        """获取覆盖信息"""
        conds = self.conditions
        return {
            "total_branches": len(conds),
            "conditions": [c.expr for c in conds],
        }


@dataclass
class ControlFlowAnalysis:
    """控制流分析结果"""
    signal: str
    
    # 条件驱动信息
    conditioned_drivers: List[ConditionedDriver] = field(default_factory=list)
    
    # 分析警告
    warnings: List[str] = field(default_factory=list)


class ControlFlowAnalyzer:
    """控制流分析器 - 直接从 SignalGraph 读取"""
    
    def __init__(self, graph_builder: Optional[GraphBuilder] = None):
        self.graph_builder = graph_builder
    
    def analyze(self, signal: str) -> ControlFlowAnalysis:
        """
        分析信号的控制流
        
        Args:
            signal: 信号名，如 "top.q"
        
        Returns:
            ControlFlowAnalysis: 控制流分析结果
        """
        result = ControlFlowAnalysis(signal=signal)
        
        if self.graph_builder is None or self.graph_builder.graph is None:
            return result
        
        graph = self.graph_builder.graph
        
        # 1. 找到所有指向该信号的边
        incoming_edges = self._get_incoming_edges(graph, signal)
        
        if not incoming_edges:
            return result
        
        # 2. 按源节点分组，找条件驱动
        by_source: Dict[str, List[TraceEdge]] = defaultdict(list)
        for edge in incoming_edges:
            by_source[edge.src].append(edge)
        
        # 3. 构建 ConditionedDriver
        for to_node, edges in by_source.items():
            # 检查是否有条件
            conditional_edges = [e for e in edges if e.condition]
            if conditional_edges:
                result.conditioned_drivers.append(
                    ConditionedDriver(to_node=signal, edges=conditional_edges)
                )
        
        # 4. 检查警告
        self._check_warnings(result)
        
        return result
    
    def analyze_dataflow_conditions(self, df_result: DataFlowResult) -> ControlFlowAnalysis:
        """
        从 DataFlow 结果中提取控制流信息
        
        Args:
            df_result: DataFlow 分析结果
        
        Returns:
            ControlFlowAnalysis: 控制流分析结果
        """
        result = ControlFlowAnalysis(signal=df_result.from_signal)
        
        # 从 DataFlowResult 中提取条件
        # df_result.all_conditions 是 List[str]
        if hasattr(df_result, 'all_conditions'):
            for cond in df_result.all_conditions:
                if cond:
                    result.warnings.append(f"路径条件: {cond}")
        
        # 从 segments 中提取条件
        if hasattr(df_result, 'segments'):
            for seg in df_result.segments:
                if hasattr(seg, 'condition') and seg.condition:
                    result.warnings.append(f"段条件: {seg.condition}")
        
        return result
    
    def find_conditioned_signals(self, module: Optional[str] = None) -> List[str]:
        """
        找出模块中所有有条件驱动的信号
        
        Args:
            module: 模块名
        
        Returns:
            List[str]: 有条件驱动的信号列表
        """
        if self.graph_builder is None or self.graph_builder.graph is None:
            return []
        
        graph = self.graph_builder.graph
        conditioned_signals = set()
        
        # 遍历所有边，找有 condition 的边
        # 注意: graph.get_edge() 返回 TraceEdge 对象，edges(data=True) 返回 dict
        for u, v in graph.edges():
            edge = graph.get_edge(u, v)
            if edge and hasattr(edge, 'condition') and edge.condition:
                conditioned_signals.add(v)
        
        return sorted(conditioned_signals)
    
    def get_conditions_for_signal(self, signal: str) -> List[str]:
        """
        获取信号的所有条件
        
        Args:
            signal: 信号名
        
        Returns:
            List[str]: 条件列表
        """
        if self.graph_builder is None or self.graph_builder.graph is None:
            return []
        
        graph = self.graph_builder.graph
        conditions = []
        
        # 找所有指向该信号的边
        for u, v in graph.edges():
            if v == signal:
                edge = graph.get_edge(u, v)
                if edge and hasattr(edge, 'condition') and edge.condition:
                    conditions.append(edge.condition)
        
        return conditions
    
    def _get_incoming_edges(self, graph, signal: str) -> List[TraceEdge]:
        """获取所有指向信号的边"""
        edges = []
        for u, v in graph.edges():
            if v == signal:
                edge = graph.get_edge(u, v)
                if edge:
                    edges.append(edge)
        return edges
    
    def _check_warnings(self, result: ControlFlowAnalysis):
        """检查警告"""
        for cd in result.conditioned_drivers:
            conds = cd.conditions
            
            # 检查是否有矛盾条件
            for i, c1 in enumerate(conds):
                for c2 in conds[i+1:]:
                    if self._is_negation(c1.expr, c2.expr):
                        result.warnings.append(
                            f"矛盾条件检测: {c1.expr} vs {c2.expr}"
                        )
    
    def _is_negation(self, expr1: str, expr2: str) -> bool:
        """检查两个表达式是否互为否定"""
        # 简化检测: a vs !a
        def normalize(expr):
            return expr.replace("!", "").replace(" ", "")
        
        n1 = normalize(expr1)
        n2 = normalize(expr2)
        
        # 检查 !a vs a 或 a vs !a
        if expr1.startswith("!") and n1 == n2:
            return True
        if expr2.startswith("!") and n2 == n1:
            return True
        
        return False