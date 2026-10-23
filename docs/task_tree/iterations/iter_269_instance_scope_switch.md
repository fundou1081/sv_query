# Iteration 269: 实例级图开关（迁移第 1 步：全实例遍历 + 基准）

**Metadata**:
- **Iteration #**: 269
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-23 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "按 1 来做；2 只认实例吧，干净一些"）
- **Outcome**: ✅ 开关可用 + 真实工程基准到手；默认未切换

## 🎯 目标

按评估结论第 1 步：**先加开关**（不切默认），用真实工程跑出基线，再决定是否切换。
按方豆决策 2：目标态是**只认实例路径**，模块类型命名空间最终消失。

## 🔬 改了什么

### ① `GraphBuilder(instance_scope=True)`

- `_configure_instance_paths()` 原本只在 `target_module` 时执行；
  现在 `instance_scope` 也触发，且**遍历所有 top**（新增 `_all_top_instances()`）
- 不做 `_filter_by_target()`（全设计视图，不是单子树调试）

### ② 孤儿节点清理 `_drop_orphan_type_nodes()`

`DriverExtractor` 已按实例路径出边，但 `connection` / `load` / `clock` 三个 extractor
仍会为**模块定义**建节点。实测这些节点在 instance_scope 下**全部零度**：

| fixture | 影子节点 | 其中有边的 |
|---|---|---|
| minimal_3module | 14 | 1（常量 `0`） |
| scheduler_minimal | 26 | 1（常量 `0`） |

清理规则：**非实例命名空间 + 零度 + 非常量 `0`** 才删；有边的保留并 `logger.warning`（不静默丢信息）。

### ③ 开关（两处）

```bash
svq paths ... --instance-scope          # 单命令开关
svq dataflow analyze ... --instance-scope
SVQ_INSTANCE_SCOPE=1 svq <任意命令>      # 全局开关（build_graph 里读 env，默认关）
```

## 📊 基准（真实工程 verilog-axi，21 top / 186 实例）

| 模式 | 节点 | 边 | 构建耗时 |
|---|---|---|---|
| 模块级（默认） | 11,622 | 16,909 | **16.3s** |
| 实例级（新） | 13,188 | 26,230 | **25.8s** |

- 节点 +13%，边 +55%，耗时 **+58%**
- 代价换来：**影子节点彻底消失**、路径语义单一

小 fixture：

| fixture | 模块级 | 实例级 | 前缀（实例级） |
|---|---|---|---|
| minimal_3module | 44 节点 | 31 节点 | `top_minimal` / `synchronizer` / `0` |
| scheduler_minimal | 98 节点 | 73 节点 | `Scheduler_minimal` / `0` |

## ✅ 验收

新增 `sim/tests/unit/test_instance_scope.py`（5 用例）：

| 用例 | 锁定内容 |
|---|---|
| `test_no_type_namespace_nodes` | 实例级下前缀只能是顶层实例名或 `0` |
| `test_all_nodes_under_instance` | 每个节点都落在实例路径下 |
| `test_default_still_has_type_nodes` | **默认模式未变**（开关不影响老行为） |
| `test_directed_path_agrees_with_dataflow` | 实例级下两命令结论一致 |
| `test_type_id_is_unknown` | 模块定义 id 查不到（符合"只认实例"决策） |

全量门禁：**2311 passed / 0 failed**（新增 5 个用例后重跑仍绿）。

## 💡 决策与遗留

1. **默认未切换**：方豆要求先开关 + 基准。当前 `SVQ_INSTANCE_SCOPE` 默认关闭。
2. **模块类型查询的去留已定**：只认实例。切换默认时要处理 **31 处测试引用**模块定义 id，
   以及 `capabilities`/文档里"按模块类型查询"的说明。
3. **性能代价已量化**：真实工程 +58% 构建时间、+55% 边。切换默认前需要评估这是否可接受
   （agent 场景下 16s → 26s 是显著差异）。
4. **generate 块**：`_configure_instance_paths` 会下钻 generate，与决策 D2
   （"generate 内部不进图"）存在潜在冲突，切换前需实测确认。

## 🔗 相关

- POC: [2026-10-23_native_connectivity.md](../../poc/2026-10-23_native_connectivity.md)
- 前序: [iter_268 路径语义修复](iter_268_path_semantics_fix.md)
