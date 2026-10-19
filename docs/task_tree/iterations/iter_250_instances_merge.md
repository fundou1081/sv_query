# Iteration 250: T2-d — `instance` 合并进 `instances` (2 → 1) + 发现两套路径实现

**Metadata**:
- **Iteration #**: 250
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 合并成功（命令 68→67，core 28→27，叶子 93）；⚠️ 顺带发现一个新的实现分叉（已登记）

## 🎯 目标

`instance` 与 `instances` 只差"有没有给实例路径" —— 与 iter_247 的 `class`/`classes`
同一形态，合并为 1。

## 🔬 实际结果

### 改动

- `instances` 增加**可选位置参数** `path`：给了 → 输出该实例详情（类型/父/子/端口），
  没给 → 列出实例
- `instance_cmd` 改造为 `_emit_instance_detail(tracer, all_inst, path, ...)`（去掉 Typer 参数）
- 删除 `instance` 命令注册与 registry 条目；`instances` note 改写
- 测试 3 处调用改为 `instances <path>`；`test_cli_instance_query` / `test_cli_readonly_guarantee` **17 passed**

### 冒烟

```
instances --filelist scheduler_minimal/filelist.f --json      → count=7
instances Scheduler_minimal.SourceA_dut --filelist ... --json → ports=4, children=0
```

### ⚠️ 顺带发现：`paths` 与 `dataflow analyze` 是两套路径实现，且一真一假

对比同一对信号（`inst_demo.sv`，顶层输入 → 顶层输出）：

| 命令 | 结果 |
|---|---|
| `paths inst_demo.in_a inst_demo.add_out` | **found**，4 跳：`in_a → u_adder.a → u_adder → u_adder.sum → add_out` |
| `dataflow analyze inst_demo.in_a inst_demo.add_out` | **is_reachable=false**，0 条路径 |

原因：`paths` 用 iter_237 修的 `PathResolver`（跨模块端口跳转），
`dataflow analyze` 用的是**旧 dataflow 引擎**（无 MIG）。这与 iter_240/241 的
`loads` 双实现是同一类问题（违反单一实现原则 I3）。

**处置**：本次只登记（`KNOWN_LIMITATIONS §3.3` 第 3 条），不顺手改 ——
dataflow 引擎还被 golden / 时序分析用着，换实现要单独评估影响面。
**这条改变了 T2 的结论**：`paths` / `dataflow analyze` **不能合并**（一个真一个假），
应先修实现再谈合并。

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 规范命令 | 68 | **67** |
| `core` 层 | 28 | **27** |
| 叶子（含别名） | 94 | **93** |
| 全量测试 | 3422 | **3422**（无回归） |

## 💡 决策

1. **`instances <path>` 而不是 `instance --list`**：列表是默认行为（无参数），
   给路径才是特例 —— 与 shell 工具惯例一致，也避免"默认值要额外 flag"。
2. **发现分叉不顺手修**：`dataflow` 换引擎会影响 golden 与 timing 相关断言，
   属于独立决策；先登记可观察后果（同一查询两种答案），再排期。
3. **重新审视 T2 剩余项**：`snapshot 5→4`、`view 3→1` 经复核都不满足
   "输入可枚举 + 输出同构"，硬合并会变成 flags 并集。剩余可做的只有
   `dev 3→1`（内部调试层，不影响默认可见面）与别名收敛。

## 🔗 相关

- 评审: [2026-10-19_core_smell_review.md §5.2](../../refactoring/2026-10-19_core_smell_review.md)
- 新登记: [KNOWN_LIMITATIONS §3.3 第 3 条](../../KNOWN_LIMITATIONS.md)
- 前置: [iter_249 graph 合并](iter_249_graph_merge.md)
