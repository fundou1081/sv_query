# Graph Diff 查询模式设计方案

> 基于静态有向图结构化对比的变更影响分析，2026-05-14

## 背景与目标

**核心问题**：对比两个版本 RTL 代码的 SignalGraph，输出变更点及其影响传播范围。

**应用场景**：
- Code Review：展示"这一改，会顺着这些边冲击哪些信号"
- 回归测试选取：只测试受影响可达节点对应的代码
- 架构预警：检测小改动导致的大范围可达性扩散

---

## 核心建模

| 概念 | sv_query 实现 |
|---|---|
| 节点 | `TraceNode`（PORT_IN/PORT_OUT/REG/SIGNAL） |
| 边 | `EdgeKind.DRIVER`（驱动数据流）、`EdgeKind.CONNECTION`（实例连接）、`EdgeKind.CLOCK`（时钟关系） |
| 影响传播方向 | 沿 DRIVER/CONNECTION 边 **正向** BFS/DFS |
| 环路处理 | `seen_ids` set 防止递归爆炸 |

---

## 图对比分层实现路径

### Phase 1（必做）：Element-wise Diff

**目标**：定位图的结构变化——哪些节点/边被增删改。

```python
@dataclass
class GraphDiff:
    """两个图的差异结构"""
    added_nodes:       List[str]                    # 新增节点
    removed_nodes:     List[str]                    # 删除节点
    added_edges:       List[Tuple[str, str]]        # 新增边 (src, dst)
    removed_edges:     List[Tuple[str, str]]        # 删除边

    modified_nodes:    Dict[str, Dict]               # node_id -> {old: {...}, new: {...}}

    identical:        bool                         # 两图是否完全相同

def diff_graph(G1: SignalGraph, G2: SignalGraph) -> GraphDiff:
    """O(N+M) 集合差集操作"""
    ...
```

**算法**：
1. `added_nodes   = G2.nodes - G1.nodes`
2. `removed_nodes = G1.nodes - G2.nodes`
3. 同理对 edges 做差集
4. 对同名节点对比属性（kind、width 等）

---

### Phase 2（做）：双向 Reachability 分析

**目标**：计算变更点的可达性差异——新增影响范围 / 消失影响范围。

**核心公式**：
```
ImpactSet = ⋃_{v ∈ ChangedNodes}
    ( Reach_new(v) ⊕ Reach_old(v) )
```
其中 `⊕` 为对称差（XOR），即"新增可达"和"消失可达"的并集。

**实现**：

```python
def forward_reachability(start_nodes: List[str], graph: SignalGraph,
                         max_depth: int | None = None) -> Set[str]:
    """BFS 正向可达性分析
    
    沿 DRIVER/CONNECTION 边正向传播，
    收集所有可达节点（不含起点本身）。
    """
    impacted = set()
    queue = list(start_nodes)
    depth = 0

    while queue:
        current_level_size = len(queue)
        if max_depth is not None and depth >= max_depth:
            break

        for _ in range(current_level_size):
            node = queue.pop(0)
            for succ in graph.successors(node):
                edge = graph.get_edge(node, succ)
                # 只沿数据流边传播，CLOCK 边不参与
                if edge and edge.kind not in (EdgeKind.DRIVER, EdgeKind.CONNECTION):
                    continue
                if succ not in impacted:
                    impacted.add(succ)
                    queue.append(succ)
        depth += 1

    return impacted


def diff_reachability(changed_nodes: List[str],
                      G_old: SignalGraph, G_new: SignalGraph) -> Dict:
    """对比两个图上同一组变更点的可达性差异"""
    # 在旧图上的可达集
    reach_old = forward_reachability(changed_nodes, G_old)
    # 在新图上的可达集
    reach_new = forward_reachability(changed_nodes, G_new)

    return {
        "newly_impacted": list(reach_new - reach_old),      # 新增影响目标
        "no_longer_impacted": list(reach_old - reach_new),  # 解除影响目标
        "still_impacted": list(reach_old & reach_new),      # 持续影响目标
        "max_impact_depth_new": max_depth_of(reach_new, G_new),
        "max_impact_depth_old": max_depth_of(reach_old, G_old),
    }
```

**边类型过滤规则**：
- `DRIVER`：数据驱动传播，**参与**可达性分析
- `CONNECTION`：实例端口连接，**参与**（穿过实例时相当于数据流延续）
- `CLOCK`：时钟关系，**不参与**（时钟不等同于数据依赖）

**环路处理**：BFS 的 `visited` set 已在每层递归前检查，防止在环中死循环。

---

### Phase 3（已实现：方案一替代）稳定核心识别

**目标**：找出两个图中保留的稳定依赖核心（标识符严格匹配），MCS 以外的部分就是潜在的影响传播区域。

> 与用户讨论后决定使用方案一（标识符严格匹配）+ 方案四（变更种子传播），而非 NP 完全的 Ullmann 算法。

```python
def compute_stable_core(G1: SignalGraph, G2: SignalGraph) -> List[str]:
    """标识符严格匹配法 - O(|V|+|E|)
    
    稳定核心 = {node_id | node_id 同名 in G1 & G2, 且出边和入边完全一致}
    """
    ...

def compute_health_score(G: SignalGraph, stable_core: List[str]) -> float:
    """架构健康度 = 稳定核心比例"""
    return len(stable_core) / len(list(G.nodes()))

def compute_coupling_warning(changed_nodes, total_nodes, unstable_ratio) -> Dict:
    """耦合预警：小改动(<5%) + 高不稳定(>30%) -> 高耦合警告"""
    ...

def diff_with_health(G1, G2) -> Dict:
    """整合 Phase 1 + Phase 3 + Phase 4 (coupling warning)"""
    ...
```

**应用**：
- 架构健康度：稳定核心比例越高 -> 核心结构越稳定
- 异常预警：小改动导致大量不稳定区域 -> 耦合度预警

---

## Phase 1 + Phase 2 完整 Diff 输出格式

```json
{
  "graph_diff": {
    "added_nodes":   ["top.new_signal"],
    "removed_nodes": ["top.old_signal"],
    "added_edges":   [["top.a", "top.c"]],
    "removed_edges": [["top.a", "top.b"]],
    "modified_nodes": {},
    "identical": false
  },

  "reachability_diff": {
    "changed_nodes": ["top.a"],
    "newly_impacted":    ["top.c"],
    "no_longer_impacted": ["top.b"],
    "still_impacted":    [],
    "impact_depth_delta": 0
  },

  "summary": {
    "nodes_added": 1,
    "nodes_removed": 1,
    "edges_added": 1,
    "edges_removed": 1,
    "new_impact_count": 1,
    "removed_impact_count": 1,
    "structural_stability": "low"   // 或 "medium", "high"
  }
}
```

---

## 存储方案（已实现）

**SnapshotManager** (src/trace/core/snapshot_manager.py)：

```
.svq/snapshots/
  v1.2.3.json    # tag=版本号
  abc1234.json   # tag=git commit hash
  2026-05-14.json
```

**CLI 命令**：
```bash
svq snapshot save <file> -t <tag>   # 保存快照
svq snapshot list                    # 列出所有快照
svq snapshot show <tag>             # 查看详情
svq snapshot delete <tag>           # 删除
svq snapshot compare <tag1> <tag2> # 对比两个快照
```

**触发时机**：
1. 手动触发：`svq snapshot save <file> -t <tag>`
2. 自动：`svq snapshot save <file> -t <tag> --git` (自动捕获 git commit hash)

---

## 待确认问题

1. **Reachability 方向**：只做正向（影响往下游传），还是也需要反向（回溯依赖源）？
2. **深度限制**：是否需要对 Reachability 加 `max_depth` 参数防止爆炸？

## 已完成问题

1. ~~Phase 3 优先级~~：**已跳过 True MCS**，使用方案一（标识符严格匹配）替代
2. ~~Snapshot 粒度~~：**已实现 SnapshotManager**，支持 tag 标记任意版本
3. ~~MCS 算法复杂度~~：**已选择方案一**，O(|V|+|E|) 替代 NP 完全 Ullmann