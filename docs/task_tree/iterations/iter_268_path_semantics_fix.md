# Iteration 268: 修路径语义 —— 端点漂移 + 跨模块改写 + 有向模式

**Metadata**:
- **Iteration #**: 268
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-23 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "现在的足够说明问题了。按 1 2 来做吧"）
- **Outcome**: ✅ 成功（端点不再漂移；dataflow 跨模块可达；`paths --directed` 与 dataflow 结论一致）

## 🎯 目标

按 [POC iter_267](../../poc/2026-10-23_native_connectivity.md) 的结论做两步：
1. 修 `PathResolver` 的**端点改写**
2. 统一**有向/无向**语义，让 `paths` 与 `dataflow` 能给出同一答案

## 🔬 改了什么（四处，逐条对应 POC 证据）

### ① `PathResolver.find_path` / `find_all_paths`：不再改写 dst

```python
# 旧: dst 是实例端口时会被换成"模块定义命名空间"的影子节点
dst_internal = self.module_graph.get_internal_signal(dst)
dst_target = dst_internal if dst_internal else dst
```

POC 实测：120 个采样对里 65~78 个返回路径的**最后一项 ≠ 用户请求的 dst**，
甚至越过 dst 继续走到影子节点：

```
修复前: paths top_minimal.valid_i top_minimal.sa1.lp1.data_i
        → [... , top_minimal.sa1.lp1.data_i, leaf_pipeline.data_i]   ← 多走一步
修复后: → [top_minimal.valid_i, top_minimal.sa1.valid_i, top_minimal.sa1.lp1.data_i]
```

顺带把 BFS 的 `list.pop(0)` 换成 `deque.popleft()`。

### ② `DataFlowGraph._resolve_cross_module`：图里已有的 id 不再重写

```python
# 旧: 无条件改写 → top_minimal.sa1.valid_i 变成 sub_aggregator.valid_i (孤立影子节点)
# 新: 图里存在的 id 原样返回; 只有不在图里的名字才走旧映射
```

这是 `dataflow analyze` 对一切跨模块查询报 unreachable 的**唯一原因**：
实测 `nx.has_path(top_minimal.valid_i, top_minimal.sa1.valid_i) == True`，
但 `analyze()` 走完改写后目标变成孤立节点 → 不可达。

修后实测 3/3 跨模块对可达（顶层端口→实例端口 / →孙实例内部 / 叶内部→顶层输出）。

### ③ `PathResolver` 增加 `directed` 模式

| 模式 | 邻接 | 语义 |
|---|---|---|
| `directed=False`（默认） | successors + predecessors + MIG 虚拟跳 | **结构连通性**（逆流也能找到） |
| `directed=True` | 只 successors，无虚拟跳 | **数据流方向**（与 dataflow 同一张图） |

### ④ CLI：`paths --directed`

```bash
svq paths in_a add_out --directed --filelist project.f --json
# → {"directed": true, "found": ...}
```

## ✅ 验收（新测试锁定三条不变式）

`sim/tests/unit/test_path_directed_parity.py`（20 个用例，全绿）：

| 不变式 | 内容 |
|---|---|
| A | `paths --directed` 与 `dataflow analyze` 对同一对信号结论一致（6 对） |
| B | 逆流查询：有向必须不可达、无向必须可达 |
| C | 任何返回路径最后一项必须 == 请求的 dst（`find_path` 与 `find_all_paths` 各测一遍） |

## 📊 量化

| 指标 | 值 |
|---|---|
| 全量门禁 | **2311 passed / 0 failed**（2291 + 20 新用例） |
| 跨模块 dataflow 可达性 | 修前 0/3 → 修后 **3/3**（minimal_3module 实测） |
| `paths --directed` vs `dataflow` 一致率 | **8/8 采样对** |
| 端点漂移 | 修前 65~78/120 → 修后 **0**（测试锁定） |

## 💡 决策

1. **没有重写连通层**：POC 证明图本身已经是连通的（`nx.has_path=True`），
   问题出在"名字改写"这一层。只改这一层，改动面小、风险低。
2. **影子节点保留**：它仍服务于"按模块定义名查询"，只是不参与有向数据流。
   彻底删除需要另一次决策（影响 `graph nodes` 输出与部分 golden）。
3. **无向默认不变**：`paths` 的老调用方不受影响；有向是**显式**选项，
   语义差异写在 `--help` 与 registry note 里。

## 🔗 相关

- POC: [2026-10-23_native_connectivity.md](../../poc/2026-10-23_native_connectivity.md)
- 限制登记: [KNOWN_LIMITATIONS §3.3-3](../../KNOWN_LIMITATIONS.md)
- 前序: [iter_267 POC](iter_267_poc_native_connectivity.md)
