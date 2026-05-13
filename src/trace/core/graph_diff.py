#==============================================================================
# graph_diff.py - Graph Diff 查询
# Phase 1: Element-wise Diff（节点/边集合差集）
# Phase 2: Reachability 分析（正向 BFS 可达性 + 可达性差异对比）
#==============================================================================

from typing import List, Tuple, Set, Dict, Optional
from dataclasses import dataclass, field

from .graph_models import SignalGraph, EdgeKind


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