"""
stage_inferrer.py — BFS topo depth → stage_id (V6.9 datapath)

原则:
- 对非 pipeline 模块（无 REG），用 BFS topological depth 自动分层
- 从 PORT_IN (depth=0) 出发，每过一个 driver_edge depth+1
- PORT_OUT 取所有输入 depth 的最大值+1
- 控制/clock/reset 边不参与 depth 传播

用法:
    from .stage_inferrer import infer_stages_bfs
    stage_map = infer_stages_bfs(viz)  # {node_id: stage_id}
    viz 中 node.stage_id 被就地设置
"""

from __future__ import annotations

from collections import deque
from typing import Any

from ..viz.viz_data_models import VizData


def infer_stages_bfs(viz: VizData) -> dict[str, int]:
    """BFS topological depth → stage_id.

    算法:
    1. 起点: 所有 PORT_IN 节点 → depth=0
    2. 传播: edge.src→edge.dst, dst_depth = max(dst_depth, src_depth+1)
       只传播 DATA driver 边 (跳过 CLOCK/RESET/CONNECTION/control)
    3. 终点: PORT_OUT → 取 max incoming depth+1
    4. 孤立节点 → depth=0

    Returns:
        {node_id → stage_id} dict，同时就地设置 viz Node.stage_id
    """
    # Index nodes
    {n.id: n for n in viz.nodes}

    # Init depths: -1 = unvisited
    depth: dict[str, int] = {n.id: -1 for n in viz.nodes}

    # Seed: PORT_IN nodes
    queue: deque[str] = deque()
    for n in viz.nodes:
        if n.kind == "PORT_IN":
            depth[n.id] = 0
            queue.append(n.id)

    # Fallback: if no PORT_IN, seed from all nodes with no incoming data edges
    if not queue:
        has_incoming: set[str] = set()
        for e in viz.edges:
            if _is_data_driver(e):
                has_incoming.add(e.dst)
        for n in viz.nodes:
            if n.id not in has_incoming:
                depth[n.id] = 0
                queue.append(n.id)

    # BFS
    while queue:
        src_id = queue.popleft()
        src_depth = depth[src_id]
        next_depth = src_depth + 1

        for e in viz.edges:
            if e.src != src_id:
                continue
            if not _is_data_driver(e):
                continue
            if depth[e.dst] < next_depth:
                depth[e.dst] = next_depth
                queue.append(e.dst)

    # Unvisited nodes → depth 0
    for nid, d in depth.items():
        if d < 0:
            depth[nid] = 0

    # PORT_OUT: bump to max incoming + 1
    for n in viz.nodes:
        if n.kind == "PORT_OUT":
            max_in = 0
            for e in viz.edges:
                if e.dst == n.id and _is_data_driver(e):
                    max_in = max(max_in, depth.get(e.src, 0) + 1)
            if max_in > depth.get(n.id, 0):
                depth[n.id] = max_in

    # Write back to VizNode
    for n in viz.nodes:
        n.stage_id = depth.get(n.id, 0)

    return depth


def _is_data_driver(edge: Any) -> bool:
    """是否为数据流驱动边（参与 BFS depth 传播）"""
    if edge.kind in ("CLOCK", "RESET", "CONNECTION"):
        return False
    if edge.is_control_edge:
        return False
    # DRIVER edge or BIT_SELECT with driver semantics
    return True
