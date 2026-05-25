#==============================================================================
# dataflow.py - DataFlow 分析图
#==============================================================================
"""
基于 SignalGraph + MIG 的数据流分析图

职责:
1. 路径搜索 - 使用 SignalGraph 进行 nx.all_simple_paths
2. 段构建 - 从 SignalGraph edges 获取 driver/condition/timing
3. 跨模块解析 - 使用 MIG 的 port_to_internal 映射
4. 结果缓存 - 按需缓存 DataFlowSegment

使用方式:
  dfg = DataFlowGraph(signal_graph, mig)
  result = dfg.analyze('top.u_dut.data_in', 'top.u_dut.data_out')
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import networkx as nx
import logging

from .models import SignalGraph, EdgeKind

logger = logging.getLogger(__name__)


#==============================================================================
# Data Structures
#==============================================================================

@dataclass
class DataFlowSegment:
    """单步驱动关系: from_signal → to_signal
    
    Attributes:
        from_signal: 起点信号 (完整 hierarchy path)
        to_signal: 终点信号 (完整 hierarchy path)
        driver: 驱动表达式 (如 'sreg_d', '4'b1011')
        condition: 驱动条件 (来自 if 语句)
        timing: 时钟域 (如 'clk_i')
        assign_type: 赋值类型 (continuous/always_ff/always_comb/blocking)
        distance: 驱动距离 (1 = 直接驱动)
    """
    from_signal: str
    to_signal: str
    driver: Optional[str] = None
    condition: Optional[str] = None
    timing: Optional[str] = None
    assign_type: str = "continuous"
    distance: int = 1


@dataclass
class DataFlowPath:
    """单条完整数据流路径
    
    Attributes:
        path_id: 路径 ID
        segments: 路径段列表
        distance: 总跳数
        has_conditional: 是否包含条件分支
    """
    path_id: int
    segments: List[DataFlowSegment] = field(default_factory=list)
    distance: int = 0
    has_conditional: bool = False


@dataclass
class DataFlowResult:
    """数据流分析完整结果
    
    Attributes:
        from_signal: 起点信号
        to_signal: 终点信号
        paths: 所有数据流路径
        is_reachable: 是否可达
        paths_count: 路径数量
        intermediate_signals: 中间信号集合
        all_conditions: 所有条件列表
        clock_domain: 主时钟域
        timing_risk: 路径风险级别 (safe/low/medium/high/critical)
    """
    from_signal: str
    to_signal: str
    paths: List[DataFlowPath] = field(default_factory=list)
    is_reachable: bool = False
    paths_count: int = 0
    intermediate_signals: Set[str] = field(default_factory=set)
    all_conditions: List[str] = field(default_factory=list)
    clock_domain: Optional[str] = None
    timing_risk: str = "safe"


#==============================================================================
# DataFlowGraph
#==============================================================================

class DataFlowGraph:
    """数据流图 - 基于 SignalGraph + MIG
    
    用于分析信号间的完整数据流路径，支持跨模块边界追踪。
    
    特性:
    - 按需构建: 不预先解析所有路径，按请求动态计算
    - 段缓存: 缓存已解析的 DataFlowSegment
    - 跨模块: 使用 MIG 映射解析实例端口信号
    """
    
    def __init__(self, signal_graph: SignalGraph, mig: 'ModuleInstanceGraph'):
        """初始化 DataFlowGraph
        
        Args:
            signal_graph: SignalGraph 实例
            mig: ModuleInstanceGraph 实例
        """
        self.signal_graph = signal_graph
        self.mig = mig
        
        # 段缓存: (from, to) → DataFlowSegment
        self._segment_cache: Dict[Tuple[str, str], DataFlowSegment] = {}
        
        # MIG 的 port_to_internal 映射缓存
        self._port_to_internal: Dict[str, str] = {}
        self._internal_to_port: Dict[str, str] = {}
        
        # 构建 MIG 映射缓存
        self._build_mig_cache()
    
    def _build_mig_cache(self):
        """构建 MIG 映射缓存"""
        if not self.mig:
            return
        
        # 从 MIG 获取 port_to_internal 映射
        if hasattr(self.mig, 'port_to_internal'):
            self._port_to_internal = self.mig.port_to_internal.copy()
        
        if hasattr(self.mig, 'internal_to_port'):
            self._internal_to_port = self.mig.internal_to_port.copy()
        
        # 同时从 MIG.instances 构建
        if hasattr(self.mig, 'instances'):
            for inst_id, inst_node in self.mig.instances.items():
                if hasattr(inst_node, 'ports'):
                    for port_name, port_info in inst_node.ports.items():
                        if hasattr(port_info, 'internal_signal'):
                            full_port = f"{inst_id}.{port_name}"
                            self._port_to_internal[full_port] = port_info.internal_signal
                            self._internal_to_port[port_info.internal_signal] = full_port
    
    def get_segment(self, from_signal: str, to_signal: str) -> Optional[DataFlowSegment]:
        """获取单步驱动信息（带缓存）
        
        Args:
            from_signal: 起点信号
            to_signal: 终点信号
            
        Returns:
            DataFlowSegment 或 None (如果不存在驱动关系)
        """
        cache_key = (from_signal, to_signal)
        if cache_key in self._segment_cache:
            return self._segment_cache[cache_key]
        
        segment = self._build_segment(from_signal, to_signal)
        if segment:
            self._segment_cache[cache_key] = segment
        return segment
    
    def _build_segment(self, from_signal: str, to_signal: str) -> Optional[DataFlowSegment]:
        """构建段信息
        
        从 SignalGraph 获取边的驱动信息。
        
        Args:
            from_signal: 起点信号
            to_signal: 终点信号
            
        Returns:
            DataFlowSegment 或 None
        """
        # 1. 解析跨模块信号
        resolved_from = self._resolve_cross_module(from_signal)
        resolved_to = self._resolve_cross_module(to_signal)
        
        # 2. 尝试从 SignalGraph 获取边信息
        edge = self.signal_graph.get_edge(resolved_from, resolved_to)
        
        if not edge:
            # 尝试原始信号（未解析）
            edge = self.signal_graph.get_edge(from_signal, to_signal)
        
        if not edge:
            return None
        
        # 3. 构建 DataFlowSegment
        return DataFlowSegment(
            from_signal=from_signal,  # 保持原始 hierarchy path
            to_signal=to_signal,
            driver=edge.expression if hasattr(edge, 'expression') else None,
            condition=edge.condition if hasattr(edge, 'condition') else None,
            timing=edge.clock_domain if hasattr(edge, 'clock_domain') else None,
            assign_type=edge.assign_type if hasattr(edge, 'assign_type') else 'continuous',
            distance=1
        )
    
    def _resolve_cross_module(self, signal: str) -> str:
        """解析跨模块信号，返回内部信号
        
        例如:
            'top.u_dut.data_in' → 'u_dut.data_in' (如果 MIG 有此映射)
            'top.u_dut.clk' → 'u_dut.clk'
        
        Args:
            signal: 完整 hierarchy path
            
        Returns:
            内部信号名
        """
        # 1. 尝试 MIG 映射
        if signal in self._port_to_internal:
            return self._port_to_internal[signal]
        
        # 2. 尝试反向映射 (internal → port)
        if signal in self._internal_to_port:
            return signal
        
        # 3. 查找最长前缀匹配
        best_match = signal
        for port_path, internal in self._port_to_internal.items():
            if signal.endswith('.' + port_path) or signal == port_path:
                # 找到了匹配的端口路径
                suffix = signal[len(port_path):]
                best_match = internal + suffix
                break
        
        return best_match
    
    def _find_paths(self, from_signal: str, to_signal: str, cutoff: int = 50) -> List[List[str]]:
        """查找所有路径（允许循环）
        
        使用 networkx.all_simple_paths 查找路径。
        注意: all_simple_paths 默认不允许循环，这里使用 cutoff 限制深度。
        
        Args:
            from_signal: 起点信号
            to_signal: 终点信号
            cutoff: 最大深度限制
            
        Returns:
            路径列表，每条路径是信号 ID 列表
        """
        import re
        
        # [FIX] 处理位选择信号，如 byte_data[3:0] → byte_data
        def _expand_bit_select(signal):
            """将位选择信号展开为其父信号"""
            match = re.match(r'^(.+)\[([^\]]+)\]$', signal)
            if match:
                return match.group(1), match.group(2)
            return signal, None
        
        # 获取所有 BIT_SELECT 子节点（如 top.byte_data → top.byte_data[3:0]）
        def _get_bit_select_children(signal):
            """获取信号的所有 BIT_SELECT 子节点 (signal 指向这些节点的反向边)"""
            children = []
            # BIT_SELECT 边的方向是: child → parent (如 byte_data[3:0] → byte_data)
            # 所以我们需要找 signal 的前驱中有 BIT_SELECT 边的
            for pred in nx_graph.predecessors(signal):
                edge = nx_graph.get_edge(pred, signal)
                if edge and edge.kind.name == 'BIT_SELECT':
                    children.append(pred)
            return children
        
        # 获取所有 BIT_SELECT 父节点（如 top.byte_data 是 top.byte_data[3:0] 的父）
        def _get_bit_select_parents(signal):
            """获取信号的所有 BIT_SELECT 父节点 (这些节点指向 signal)"""
            parents = []
            for succ in nx_graph.successors(signal):
                edge = nx_graph.get_edge(signal, succ)
                if edge and edge.kind.name == 'BIT_SELECT':
                    parents.append(succ)
            return parents
        
        # 解析跨模块信号
        resolved_from = self._resolve_cross_module(from_signal)
        resolved_to = self._resolve_cross_module(to_signal)
        
        # 展开位选择
        expanded_from, slice_from = _expand_bit_select(resolved_from)
        expanded_to, slice_to = _expand_bit_select(resolved_to)
        
        # 获取 networkx 图
        try:
            nx_graph = self.signal_graph
        except AttributeError:
            logger.warning("SignalGraph does not support networkx conversion")
            return []
        
        # 构建候选起始点列表（包括 BIT_SELECT 子节点）
        candidates_from = [resolved_from]
        if expanded_from != resolved_from:
            candidates_from.append(expanded_from)
        # 添加 expanded_from 的 BIT_SELECT 子节点
        for child in _get_bit_select_children(expanded_from):
            if child not in candidates_from:
                candidates_from.append(child)
        
        # 构建候选目标点列表（包括 BIT_SELECT 父节点）
        candidates_to = [resolved_to]
        if expanded_to != resolved_to:
            candidates_to.append(expanded_to)
        # 添加 expanded_to 的 BIT_SELECT 父节点
        for parent in _get_bit_select_parents(expanded_to):
            if parent not in candidates_to:
                candidates_to.append(parent)
        
        # 尝试所有候选组合
        for from_candidate in candidates_from:
            for to_candidate in candidates_to:
                if from_candidate not in nx_graph.nodes():
                    continue
                if to_candidate not in nx_graph.nodes():
                    continue
                
                try:
                    paths = list(nx.all_simple_paths(nx_graph, from_candidate, to_candidate, cutoff=cutoff))
                    if paths:
                        return paths
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
        
        return []
    
    def analyze(self, from_signal: str, to_signal: str, max_paths: int = 100) -> DataFlowResult:
        """分析 from → to 的完整数据流路径
        
        主入口方法，返回完整的 DataFlowResult。
        
        Args:
            from_signal: 起点信号 (完整 hierarchy path)
            to_signal: 终点信号 (完整 hierarchy path)
            max_paths: 最大路径数量限制
            
        Returns:
            DataFlowResult: 包含所有路径及分析结果
        """
        # 1. 查找所有路径
        paths = self._find_paths(from_signal, to_signal)
        
        if not paths:
            return DataFlowResult(
                from_signal=from_signal,
                to_signal=to_signal,
                is_reachable=False,
                paths_count=0
            )
        
        # 2. 限制路径数量
        paths = paths[:max_paths]
        
        # 3. 构建 DataFlowPath
        dataflow_paths = []
        all_intermediate: Set[str] = set()
        all_conditions: List[str] = []
        has_conditional = False
        
        for path_id, path in enumerate(paths):
            segments = []
            
            # 4. 构建每条路径的 segments
            for i in range(len(path) - 1):
                seg_from = path[i]
                seg_to = path[i + 1]
                
                # 获取 segment（使用缓存）
                segment = self.get_segment(seg_from, seg_to)
                
                if segment:
                    segments.append(segment)
                    
                    # 收集条件
                    if segment.condition:
                        all_conditions.append(segment.condition)
                        has_conditional = True
                    
                    # 收集中间信号（排除起点和终点）
                    if i > 0:
                        all_intermediate.add(seg_from)
            
            # 5. 创建 DataFlowPath
            df_path = DataFlowPath(
                path_id=path_id,
                segments=segments,
                distance=len(path) - 1,
                has_conditional=has_conditional
            )
            dataflow_paths.append(df_path)
        
        # 6. 收集时钟域
        clock_domain = self._extract_clock_domain(dataflow_paths)
        
        # 7. 评估路径风险
        timing_risk = self._evaluate_timing_risk(dataflow_paths, clock_domain)
        
        return DataFlowResult(
            from_signal=from_signal,
            to_signal=to_signal,
            paths=dataflow_paths,
            is_reachable=True,
            paths_count=len(dataflow_paths),
            intermediate_signals=all_intermediate,
            all_conditions=all_conditions,
            clock_domain=clock_domain,
            timing_risk=timing_risk
        )
    
    def _extract_clock_domain(self, paths: List[DataFlowPath]) -> Optional[str]:
        """提取主时钟域
        
        Args:
            paths: 数据流路径列表
            
        Returns:
            主时钟域字符串或 None
        """
        clock_domains: Dict[str, int] = {}
        
        for path in paths:
            for segment in path.segments:
                if segment.timing:
                    clock_domains[segment.timing] = clock_domains.get(segment.timing, 0) + 1
        
        if not clock_domains:
            return None
        
        # 返回出现最多的时钟域
        return max(clock_domains, key=clock_domains.get)
    
    def _evaluate_timing_risk(self, paths: List[DataFlowPath], clock_domain: Optional[str]) -> str:
        """评估路径时序风险
        
        Args:
            paths: 数据流路径列表
            clock_domain: 主时钟域
            
        Returns:
            风险级别: safe/low/medium/high/critical
        """
        if not paths:
            return "safe"
        
        # 检查是否跨时钟域
        clock_domains = set()
        for path in paths:
            for segment in path.segments:
                if segment.timing:
                    clock_domains.add(segment.timing)
        
        if len(clock_domains) > 1:
            return "high"  # 跨时钟域
        
        # 检查路径长度
        max_distance = max(p.distance for p in paths)
        
        if max_distance > 10:
            return "medium"
        elif max_distance > 5:
            return "low"
        
        return "safe"
    
    def clear_cache(self):
        """清除段缓存"""
        self._segment_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        return {
            "segment_cache_size": len(self._segment_cache),
            "mig_mapping_size": len(self._port_to_internal)
        }