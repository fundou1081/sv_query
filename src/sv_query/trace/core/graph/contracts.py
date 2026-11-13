# ==============================================================================
# contracts.py - Edge 分类契约 (P158.1)
# ==============================================================================
"""
Edge 分类的**唯一**实现。

契约来源: [SEMANTIC_CONTRACTS.md §2](../../../docs/dev/SEMANTIC_CONTRACTS.md)。

所有消费者 (`PathResolver` / `DataFlowGraph` / `verify claim type=path` /
`trace fanin/fanout` / `verify consistency reciprocity`) 必须引用本模块的
常量, **不允许**在命令里写 `edge.kind in (...)` —— 那等于第二份实现
(铁律 I3 / 单一实现原则)。

三分类 (与契约表逐字对应):

| 类别 | 集合 | 语义 |
|---|---|---|
| data | `DRIVER`, `CONNECTION` | 数据驱动 / 端口连接; 构成数据路径 |
| control | `CLOCK`, `RESET`, `BRANCH_*`, `CASE_*` | 时序 / 条件元数据; **不能**单独构成数据路径 |
| structural | `BIT_SELECT`, `MEMBER_SELECT` | 位 / 成员聚合; 层级定位; 不能冒充数据驱动 |

class / constraint 边 (`CONSTRAINS`, `HAS_*`, `CONTAINS_MEMBER`,
`IS_INSTANCE_OF`, `SUPER_CALL`) 不参与信号路径, 单列一组。

契约要点 (P158.1 / P158.2):

- `paths --directed` / `verify claim type=path` / `dataflow analyze`
  只走 data 边 → CLOCK/RESET/BIT_SELECT 不得出现在数据路径里。
- 无向 `paths` 是**结构连通性**, 与数据路径语义不同 → 必须标注 mode。
- 任何路径枚举都必须有 work budget + 可选 deadline; 耗尽时显式 truncated。
"""

from __future__ import annotations

from .models import EdgeKind

# ----------------------------------------------------------------------------
# 唯一策略常量 (SEMANTIC_CONTRACTS §2.1)
# ----------------------------------------------------------------------------

#: 数据边 —— 数据驱动 + 模块端口连接。构成数据路径。
DATA_EDGE_KINDS: frozenset[EdgeKind] = frozenset({
    EdgeKind.DRIVER,
    EdgeKind.CONNECTION,
})

#: 控制边 —— 时序 / 条件元数据。不能单独构成数据路径。
CONTROL_EDGE_KINDS: frozenset[EdgeKind] = frozenset({
    EdgeKind.CLOCK,
    EdgeKind.RESET,
    EdgeKind.BRANCH_CONDITION,
    EdgeKind.BRANCH_TRUE,
    EdgeKind.BRANCH_FALSE,
    EdgeKind.BRANCH_RESULT,
    EdgeKind.CASE_SELECT,
    EdgeKind.CASE_ITEM,
    EdgeKind.CASE_RESULT,
})

#: 结构边 —— 位 / 成员聚合与层级定位。不能冒充数据驱动。
STRUCTURAL_EDGE_KINDS: frozenset[EdgeKind] = frozenset({
    EdgeKind.BIT_SELECT,
    EdgeKind.MEMBER_SELECT,
})

#: class / constraint 边 —— 不参与信号路径。
CLASS_EDGE_KINDS: frozenset[EdgeKind] = frozenset({
    EdgeKind.CONSTRAINS,
    EdgeKind.HAS_CONDITION,
    EdgeKind.HAS_CONSEQUENT,
    EdgeKind.HAS_ALTERNATE,
    EdgeKind.HAS_LHS,
    EdgeKind.HAS_RHS,
    EdgeKind.HAS_MEMBER,
    EdgeKind.HAS_LOOP_VAR,
    EdgeKind.HAS_BEFORE,
    EdgeKind.HAS_AFTER,
    EdgeKind.CONTAINS_MEMBER,
    EdgeKind.IS_INSTANCE_OF,
    EdgeKind.SUPER_CALL,
})

#: 全部"硬件信号边" = data + control + structural (不含 class/constraint)。
SIGNAL_EDGE_KINDS: frozenset[EdgeKind] = (
    DATA_EDGE_KINDS | CONTROL_EDGE_KINDS | STRUCTURAL_EDGE_KINDS
)


# ----------------------------------------------------------------------------
# 判定 helper —— 消费者统一走这些函数, 不自己解释 kind
# ----------------------------------------------------------------------------

def is_data_edge(edge) -> bool:
    """该边是否是数据边 (DRIVER / CONNECTION)。

    Args:
        edge: `TraceEdge` 或任何带 `.kind` 属性的对象。

    Returns:
        True 当且仅当 `edge.kind` 属于 `DATA_EDGE_KINDS`。
    """
    kind = getattr(edge, "kind", None)
    if kind is None:
        return False
    return kind in DATA_EDGE_KINDS


def is_control_edge(edge) -> bool:
    """该边是否是控制边 (CLOCK / RESET / BRANCH_* / CASE_*)。"""
    kind = getattr(edge, "kind", None)
    if kind is None:
        return False
    return kind in CONTROL_EDGE_KINDS


def is_structural_edge(edge) -> bool:
    """该边是否是结构边 (BIT_SELECT / MEMBER_SELECT)。"""
    kind = getattr(edge, "kind", None)
    if kind is None:
        return False
    return kind in STRUCTURAL_EDGE_KINDS


def has_data_edge(edges) -> bool:
    """一组边里是否至少有一条数据边。

    用于"是否存在数据关系"的判定 (verify / reciprocity 语义)。
    """
    return any(is_data_edge(e) for e in edges)


def filter_edges(edges, kinds: frozenset[EdgeKind]):
    """按 kind 集合过滤边 (返回 list)。"""
    return [e for e in edges if getattr(e, "kind", None) in kinds]


def data_edge_view(signal_graph):
    """构造只含**数据边** (DRIVER / CONNECTION) 的有向视图。

    [P158.1] dataflow 的路径搜索必须只走数据边; CLOCK / RESET /
    BIT_SELECT / MEMBER_SELECT 不得成为数据路径的**段**。
    BIT_SELECT 仍然可以用作**位展开** (端点归一化), 但那发生在
    端点解析阶段, 不是路径上的一段。

    实现: 新建一个 `nx.DiGraph`, 只复制 data 边的 (src, dst) 与边属性。
    节点集合与原图一致 (含无出边的孤立节点), 便于 `has_path` 判定。

    Args:
        signal_graph: `SignalGraph` (nx.DiGraph 子类)

    Returns:
        `nx.DiGraph` —— 只含数据边的视图。
    """
    import networkx as nx

    view = nx.DiGraph()
    view.add_nodes_from(signal_graph.nodes())
    for src, dst, data in signal_graph.edges(data=True):
        edges = signal_graph.get_edges(src, dst)
        if not any(e.kind in DATA_EDGE_KINDS for e in edges):
            continue
        view.add_edge(src, dst, **data)
    return view


__all__ = [
    "DATA_EDGE_KINDS",
    "CONTROL_EDGE_KINDS",
    "STRUCTURAL_EDGE_KINDS",
    "CLASS_EDGE_KINDS",
    "SIGNAL_EDGE_KINDS",
    "is_data_edge",
    "is_control_edge",
    "is_structural_edge",
    "has_data_edge",
    "filter_edges",
    "data_edge_view",
]
