#==============================================================================
# graph_diff.py - Graph Diff 查询
# Phase 1: Element-wise Diff（节点/边集合差集）
# Phase 2: Reachability 分析（正向 BFS 可达性 + 可达性差异对比）
#==============================================================================

from typing import List, Tuple, Set, Dict, Optional
from dataclasses import dataclass, field

from .models import SignalGraph, EdgeKind


#==============================================================================
# Phase 1: Element-wise Diff
#==============================================================================

@dataclass
class GraphDiff:
    """两个图的差异结构"""
    added_nodes: List[str] = field(default_factory=list)
    removed_nodes: List[str] = field(default_factory=list)
    added_edges: List[Tuple[str, str]] = field(default_factory=list)
    removed_edges: List[Tuple[str, str]] = field(default_factory=list)
    modified_nodes: Dict[str, Dict] = field(default_factory=dict)
    identical: bool = True


def diff_graph(G1: SignalGraph, G2: SignalGraph) -> GraphDiff:
    """对比两个 SignalGraph，返回结构化差异（Element-wise Diff）

    Args:
        G1: 旧版本 Graph
        G2: 新版本 Graph

    Returns:
        GraphDiff: 包含节点/边增删改的结构化差异
    """
    # 节点集合
    nodes1 = set(G1.nodes())
    nodes2 = set(G2.nodes())

    added_nodes = sorted(nodes2 - nodes1)
    removed_nodes = sorted(nodes1 - nodes2)

    # 边集合（NetworkX DiGraph.edges() 返回 tuple，直接用集合运算）
    edges1 = set(G1.edges())
    edges2 = set(G2.edges())

    added_edges = sorted(edges2 - edges1)
    removed_edges = sorted(edges1 - edges2)

    # 属性变化检测（同名节点但属性不同）
    common_nodes = nodes1 & nodes2
    modified = {}
    for node_id in common_nodes:
        n1 = G1.get_node(node_id)
        n2 = G2.get_node(node_id)
        if n1 and n2 and not _nodes_equal(n1, n2):
            modified[node_id] = {
                'old': {'kind': n1.kind.name, 'width': n1.width},
                'new': {'kind': n2.kind.name, 'width': n2.width},
            }
    modified_nodes = modified

    identical = (
        len(added_nodes) == 0
        and len(removed_nodes) == 0
        and len(added_edges) == 0
        and len(removed_edges) == 0
        and len(modified_nodes) == 0
    )

    return GraphDiff(
        added_nodes=added_nodes,
        removed_nodes=removed_nodes,
        added_edges=added_edges,
        removed_edges=removed_edges,
        modified_nodes=modified_nodes,
        identical=identical,
    )


def _nodes_equal(n1, n2) -> bool:
    """比较两个 TraceNode 是否完全相等"""
    return (
        n1.kind == n2.kind
        and n1.width == n2.width
        and n1.module == n2.module
    )


#==============================================================================
# Phase 2: Reachability 分析
#==============================================================================

def forward_reachability(
    start_nodes: List[str],
    graph: SignalGraph,
    max_depth: Optional[int] = None,
) -> Set[str]:
    """BFS 正向可达性分析

    沿 DRIVER/CONNECTION 边正向传播，收集所有可达节点。

    Args:
        start_nodes: 起始节点 ID 列表（变更点）
        graph: SignalGraph
        max_depth: None=无限递归, N=最多递归 N 层

    Returns:
        Set[str]: 所有可达节点 ID（不含起点本身）
    """
    impacted: Set[str] = set()
    # 过滤掉不在图中的起始节点
    queue = [n for n in start_nodes if n in graph.nodes()]
    depth = 0

    while queue:
        if max_depth is not None and depth >= max_depth:
            break

        current_level_size = len(queue)
        for _ in range(current_level_size):
            node = queue.pop(0)
            for succ in graph.successors(node):
                edge = graph.get_edge(node, succ)
                # 只沿数据流边传播，CLOCK 边不参与数据依赖
                if edge and edge.kind not in (EdgeKind.DRIVER, EdgeKind.CONNECTION):
                    continue
                if succ not in impacted:
                    impacted.add(succ)
                    queue.append(succ)
        depth += 1

    return impacted


def diff_reachability(
    changed_nodes: List[str],
    G_old: SignalGraph,
    G_new: SignalGraph,
) -> Dict:
    """对比两个图上同一组变更点的可达性差异

    Args:
        changed_nodes: 变更节点列表（从 diff_graph 获取的 added_nodes/removed_nodes/modified_nodes）
        G_old: 旧版本 Graph
        G_new: 新版本 Graph

    Returns:
        Dict: {
            'newly_impacted': 新版本新增的可达节点,
            'no_longer_impacted': 旧版本有但新版本没有的可达节点,
            'still_impacted': 两版本都可达的节点,
            'max_impact_depth_new': 新版本最大影响深度,
            'max_impact_depth_old': 旧版本最大影响深度,
        }
    """
    if not changed_nodes:
        return {
            'newly_impacted': [],
            'no_longer_impacted': [],
            'still_impacted': [],
            'max_impact_depth_new': 0,
            'max_impact_depth_old': 0,
        }

    # 在旧图上的可达集（无限深度）
    reach_old = forward_reachability(changed_nodes, G_old)
    # 在新图上的可达集（无限深度）
    reach_new = forward_reachability(changed_nodes, G_new)

    # 对称差：新增可达 ⊕ 消失可达
    newly_impacted = sorted(reach_new - reach_old)
    no_longer_impacted = sorted(reach_old - reach_new)
    still_impacted = sorted(reach_old & reach_new)

    # 最大影响深度（逐层计算）
    max_depth_new = _max_impact_depth(changed_nodes, G_new)
    max_depth_old = _max_impact_depth(changed_nodes, G_old)

    return {
        'newly_impacted': newly_impacted,
        'no_longer_impacted': no_longer_impacted,
        'still_impacted': still_impacted,
        'max_impact_depth_new': max_depth_new,
        'max_impact_depth_old': max_depth_old,
    }


def _max_impact_depth(start_nodes: List[str], graph: SignalGraph) -> int:
    """计算从 start_nodes 出发的最大影响传播深度

    通过逐层 BFS 测量，每扩散一层 depth+1。
    """
    if not start_nodes:
        return 0

    # 过滤掉不在图中的起始节点
    valid_starts = [n for n in start_nodes if n in graph.nodes()]
    if not valid_starts:
        return 0

    impacted: Set[str] = set()
    queue = list(valid_starts)
    max_depth = 0

    while queue:
        current_level_size = len(queue)
        if current_level_size == 0:
            break

        for _ in range(current_level_size):
            node = queue.pop(0)
            for succ in graph.successors(node):
                edge = graph.get_edge(node, succ)
                if edge and edge.kind not in (EdgeKind.DRIVER, EdgeKind.CONNECTION):
                    continue
                if succ not in impacted:
                    impacted.add(succ)
                    queue.append(succ)

        max_depth += 1

    return max_depth

#==============================================================================
# 方案一: 标识符严格匹配法 - 稳定核心 + 架构健康度
# 参考: GRAPH_DIFF_DESIGN.md + MCS方案汇总文档
#==============================================================================

def compute_stable_core(G1: SignalGraph, G2: SignalGraph) -> List[str]:
    """计算两个图的稳定核心（同名模块 + 所有出边和入边完全一致）
    
    金标准推导:
    稳定核心 = {module_id | module_id in G1 and module_id in G2 
                      and out_edges(G1, module_id) == out_edges(G2, module_id)
                      and in_edges(G1, module_id) == in_edges(G2, module_id)}
    
    Args:
        G1: 旧版本 Graph
        G2: 新版本 Graph
    
    Returns:
        List[str]: 稳定核心模块 ID 列表
    
    时间复杂度: O(|V| + |E|)
    """
    nodes1 = set(G1.nodes())
    nodes2 = set(G2.nodes())
    
    # 同名节点集合
    common_nodes = nodes1 & nodes2
    
    stable_core = []
    
    for node_id in common_nodes:
        # 检查出边是否一致
        out1 = set(G1.out_edges(node_id))
        out2 = set(G2.out_edges(node_id))
        if out1 != out2:
            continue
        
        # 检查入边是否一致
        in1 = set(G1.in_edges(node_id))
        in2 = set(G2.in_edges(node_id))
        if in1 != in2:
            continue
        
        stable_core.append(node_id)
    
    return sorted(stable_core)


def compute_health_score(G: SignalGraph, stable_core: List[str]) -> float:
    """计算架构健康度
    
    金标准推导:
    健康度 = 稳定核心模块数 / 图中最大模块数
    
    Args:
        G: SignalGraph
        stable_core: compute_stable_core() 返回的稳定核心列表
    
    Returns:
        float: 健康度 (0.0 ~ 1.0)
    """
    total_nodes = len(list(G.nodes()))
    if total_nodes == 0:
        return 0.0
    return len(stable_core) / total_nodes


def compute_coupling_warning(
    changed_nodes: List[str],
    total_nodes: int,
    unstable_ratio: float,
    changed_ratio: float = 0.05,
    unstable_threshold: float = 0.30
) -> Dict:
    """计算耦合预警
    
    金标准推导:
    耦合预警条件:
    - |C| / 总模块数 < 5% (改动很小)
    - 不稳定模块比例 > 30% (轻微改动导致大范围不稳定)
    
    Args:
        changed_nodes: 变更节点列表
        total_nodes: 总节点数
        unstable_ratio: 不稳定模块比例 (不稳定模块 = 总模块 - 稳定核心)
        changed_ratio: 变更比例阈值 (默认 5%)
        unstable_threshold: 不稳定比例阈值 (默认 30%)
    
    Returns:
        Dict: {
            'is_warning': bool,
            'changed_count': int,
            'changed_ratio': float,
            'unstable_ratio': float,
            'level': str,  # 'high' | 'medium' | 'low'
        }
    """
    changed_count = len(changed_nodes)
    changed_pct = changed_count / total_nodes if total_nodes > 0 else 0.0
    
    is_warning = (changed_pct < changed_ratio) and (unstable_ratio > unstable_threshold)
    
    # 计算预警级别
    if is_warning:
        if unstable_ratio > 0.5:
            level = 'critical'
        elif unstable_ratio > 0.3:
            level = 'high'
        else:
            level = 'medium'
    else:
        level = 'low'
    
    return {
        'is_warning': is_warning,
        'changed_count': changed_count,
        'changed_ratio': round(changed_pct, 4),
        'unstable_ratio': round(unstable_ratio, 4),
        'level': level,
    }


def diff_with_health(
    G1: SignalGraph,
    G2: SignalGraph
) -> Dict:
    """完整 Graph Diff，包含稳定核心和健康度（方案一）
    
    金标准输出格式:
    {
        "graph_diff": GraphDiff,
        "stable_core": List[str],           # 稳定核心节点
        "health_score_old": float,          # 旧图健康度
        "health_score_new": float,          # 新图健康度
        "health_delta": float,              # 健康度变化
        "coupling_warning": Dict,            # 耦合预警
    }
    
    Args:
        G1: 旧版本 Graph
        G2: 新版本 Graph
    
    Returns:
        Dict: 包含所有 diff 信息及健康度指标
    """
    # Phase 1: Element-wise diff
    diff_result = diff_graph(G1, G2)
    
    # Phase 2: 稳定核心计算
    stable_core = compute_stable_core(G1, G2)
    
    # Phase 3: 健康度计算
    health_old = compute_health_score(G1, stable_core)
    health_new = compute_health_score(G2, stable_core)
    health_delta = health_new - health_old
    
    # Phase 4: 耦合预警
    total_nodes = max(len(list(G1.nodes())), len(list(G2.nodes())))
    unstable_ratio = 1.0 - (len(stable_core) / total_nodes) if total_nodes > 0 else 0.0
    
    # 变更节点 = added_nodes + removed_nodes + modified_nodes
    changed_nodes = (
        diff_result.added_nodes + 
        diff_result.removed_nodes + 
        list(diff_result.modified_nodes.keys())
    )
    
    coupling = compute_coupling_warning(
        changed_nodes=changed_nodes,
        total_nodes=total_nodes,
        unstable_ratio=unstable_ratio
    )
    
    return {
        'graph_diff': diff_result,
        'stable_core': stable_core,
        'health_score_old': round(health_old, 4),
        'health_score_new': round(health_new, 4),
        'health_delta': round(health_delta, 4),
        'coupling_warning': coupling,
    }
