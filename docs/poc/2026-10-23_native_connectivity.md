# POC: slang-native 连通性 vs 现有两套路径实现（2026-10-23）

> **性质**: POC（概念验证）。产出数据用于决策，**不改任何产品代码**。
> **工具**: [`tools/poc_native_connectivity.py`](../../tools/poc_native_connectivity.py)
> **复现**: `python3 tools/poc_native_connectivity.py --filelist <filelist.f> [--json out.json]`

## 1. 要回答的问题

现在有两条"路径"实现，结论互相矛盾：

| 命令 | 实现 | 方向 | 跨模块 |
|---|---|---|---|
| `paths` | `PathResolver` (`module_instance_graph.py:281`) | **无向** | 有（运行时 MIG 跳） |
| `dataflow analyze` | `DataFlowGraph._find_paths` (`dataflow.py:332`) | **有向** | 无 |

POC 要回答：**如果把跨模块连接改成 slang 原生 `portConnections` 建边，会改变什么？**
以及：现在这两套实现的具体缺陷能不能被量化。

## 2. 方法

1. **原生侧**：`Compilation` + `root.topInstances` + `InstanceSymbol.portConnections`
   - 父侧：`conn.expression.symbol.hierarchicalPath`（输入口） / `conn.expression.left.symbol.hierarchicalPath`（输出口）
   - 子侧：`conn.port.internalSymbol.hierarchicalPath`
   - 方向：`conn.port.direction`
2. **旧实现侧**：`UnifiedTracer.build_graph()` 的 SignalGraph + `PathResolver`
3. **对比**：
   - 命名空间量化（实例作用域 vs 模块定义影子节点）
   - 从顶层输入出发的有向可达性（按命名空间分组）
   - 采样信号对的四列可达性（原生/增强图/旧有向/旧无向）
   - `PathResolver` 返回路径的**终点正确率**

## 3. 实测结果

### 3.1 两个 fixture 的规模

| 指标 | minimal_3module | scheduler_minimal |
|---|---|---|
| 文件 / 顶层实例 / 子实例 | 3 / 2 / 3 | 1 / 1 / 7 |
| 原生端口边 | 11 | 25 |
| 旧图节点 / 边 | 44 / 56 | 98 / 173 |
| 建图耗时（原生 / 旧） | 0.001s / 0.077s | 0.002s / 0.137s |

### 3.2 双命名空间（核心发现）

| 指标 | minimal_3module | scheduler_minimal |
|---|---|---|
| 实例作用域节点 | 27 | 68 |
| **模块定义影子节点** | **17（38.6%）** | **30（30.6%）** |
| 两个命名空间之间的边 | 3 | 21 |
| 弱连通分量 | 6 | 10 |

**影子节点从顶层输入出发的有向可达：`0/17` 和 `0/30`。**

也就是说：`sub_aggregator.valid_i`、`leaf_pipeline.data_i`、`Listbuffer.clk` 这类
"模块定义命名空间"节点，**在数据流意义上完全不可达**。它们不是信号，是我们为了
"按模块类型分析"另建的一张平行图。

### 3.3 `PathResolver` 的两个具体缺陷（被量化）

| 缺陷 | minimal_3module | scheduler_minimal |
|---|---|---|
| **终点被改写**：返回路径的最后一项 ≠ 用户请求的 dst | **78 / 120** | **65 / 120** |
| **逆流路径**：无向可达、但有向不可达（数据流上走不通） | **104 / 120** | **88 / 120** |

终点改写的机制（`find_path`）：

```python
dst_internal = self.module_graph.get_internal_signal(dst)
dst_target = dst_internal if dst_internal else dst     # ← 把目标换成影子节点
```

实测后果：

```
$ paths top_minimal.valid_i top_minimal.sa1.lp1.data_i
  path = [top_minimal.valid_i, top_minimal.sa1.valid_i,
          top_minimal.sa1.lp1.data_i, leaf_pipeline.data_i]
                                    ↑ 越过了用户要的终点，多走一步到影子节点
```

### 3.4 原生侧能不能解决

能提供**准确的两端路径 + 方向**（实测，`minimal_3module` 的 `top_minimal.sa1`）：

```
port=valid_i  dir=In   internal=valid_i  expr=NamedValue  → top_minimal.valid_i
port=sum_o    dir=Out  internal=sum_o    expr=Assignment → top_minimal.data_o (left.symbol)
```

即：父网 ↔ 实例端口，**slang 原生给出，无需合成**。当前 MIG 却是
`internal = f"{inst_type}.{port_name}"` 手工拼出来的模块定义名 —— 这正是一切
"影子节点"的来源。

## 4. 结论

1. **影子命名空间确实存在且不可达**：占图节点 30~38%，从顶层输入 0 可达。
   任何以影子节点结尾的 `paths` 结果都不是真实数据流路径。
2. **`PathResolver` 不能直接给 `dataflow` 复用**：它是无向的，且 60%+ 的采样对
   返回的路径终点不等于请求的 dst。直接复用会把 `dataflow` 变成"无向 + 终点漂移"。
3. **slang 原生能给出端口两侧的准确路径与方向**，用它建"单一命名空间连通层"是可行的。
4. **但**：本次 POC 只验证了"端口连接"这层；模块内部的 dataflow 边仍来自旧 SignalGraph，
   所以**不能**据此宣称"原生重写整体更快/更准"。

## 5. 适用场景 / 优点 / 缺陷

### 适用
- ✅ 评估"要不要换连通层"，以及换之前先量化旧实现的缺陷
- ✅ 复盘"影子节点"占比（不同 fixture 的稳定性）
- ✅ 给后续迁移提供**可复现的基线数字**

### 优点
- 不碰 `src/`，零产品风险
- 只用 pyslang public API（`portConnections` / `internalSymbol` / `hierarchicalPath`）
- 结论可复现（确定性种子）
- 输出既有汇总也有明细（不一致信号对逐条列出）

### 缺陷（必须随结论一起读）
1. **只比可达性，不比路径质量**：两边都可达时，哪条路径更"对"没有判断
2. **原生侧只建了端口边**：模块内部边仍借用旧图，所以"原生 vs 旧"不是完整对照
3. **旧有向可达用图 BFS 近似 `dataflow`**：`dataflow` 本身有 `cutoff=50`，极深路径可能不一致
4. **不展开 generate-block**（沿用项目 D2 决策）
5. **只有 2 个小 fixture**：scheduler_minimal（98 节点）与 minimal_3module（44 节点），
   大工程（OpenTitan / CVA6）未跑，不能外推
6. **不测性能**：建图耗时那两列只作参考，样本量不足以支持性能结论

## 6. 建议的下一步

1. **先修 `PathResolver` 的终点改写**（缺陷 3.3 第一条）——这是**独立于迁移**的正确性 bug，
   改动小、收益立刻可见：`find_path` 不应把 dst 换成影子节点；若需要"穿透到模块内部"，
   应显式提供 `--through-module` 语义而不是偷偷改目标。
2. **再决定连通层**：若要统一，按本 POC 的三条硬指标验收：
   - 影子节点数降到 0（或明确标注为"仅用于模块类型查询"）
   - 从顶层输入对齐可达集合（当前 11/27、52/68，需与原生图一致）
   - `dataflow` 与 `paths --directed` 对同一对信号结论一致
3. **在更大 fixture 上重跑本 POC**（先跑 `sim/tests/fixtures/golden_mini` 与一个真实开源工程），
   再评估迁移成本。

## 7. 复现命令

```bash
python3 tools/poc_native_connectivity.py --filelist sim/tests/fixtures/minimal_3module/filelist.f
python3 tools/poc_native_connectivity.py --filelist sim/tests/fixtures/scheduler_minimal/filelist.f --json /tmp/poc.json
```
