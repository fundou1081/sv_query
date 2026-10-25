# Iteration 277: 删除 `port_to_internal` 自映射（单一命名空间收尾）

**Metadata**:
- **Iteration #**: 277
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "可以，做吧" —— 删除 `port_to_internal` 自映射）
- **Outcome**: ✅ 成功（图级 + dataflow 级映射全删；全量 2302 passed）

## 🎯 目标

iter_276 之后，图里只剩实例级 id。`port_to_internal` 变成**实例端口 → 自己**的
自映射（`top.u_dut.clk → top.u_dut.clk`），除了序列化体积没有任何作用。本次删除。

## 🔧 删除清单

| # | 位置 | 内容 |
|---|---|---|
| 1 | `graph/models.py` | `SignalGraph._port_to_internal` 字段、`get_port_to_internal()`、`get_internal_signal()`、`to_dict/from_dict` 里的序列化 |
| 2 | `extractor_models.py` | `ExtractorResult.port_to_internal` 字段 |
| 3 | `connection_extractor.py` | 3 处 `result.port_to_internal[...] = child_signal_id` 写入 |
| 4 | `graph_builder.py` | `self.graph._port_to_internal.update(...)` 收集 |
| 5 | `graph/dataflow.py` | `_port_to_internal` / `_internal_to_port` / `_build_mig_cache()` / `_resolve_cross_module()` 及 5 处调用；`mig_mapping_size` 统计字段 |
| 6 | `snapshot_manager.py` | 快照格式注释里的 `port_to_internal` |
| 7 | 测试 | `test_connection_extractor` 的映射断言改为节点/边断言；删除 self-map 语义用例 + pulp mock 的映射用例 |

> `_resolve_cross_module` 在 iter_268 已被修正为"图内 id 原样返回"，本次把整个函数
> 连同 MIG 映射缓存删除 —— 它剩下的作用只是给不在图里的名字做一次无效映射。

## 📊 量化

| 指标 | 值 |
|---|---|
| 全量门禁 | **2302 passed / 0 failed**（iter_276 2305 → 少 3 个被删的映射用例） |
| `port_to_internal` 引用（src） | 20+ → **0**（图级 + dataflow 级） |
| 快照体积 | 每个快照少一份 N 条 `inst_port → 自身` 的字典 |
| 代码行 | 净删除约 120 行（含注释） |

## 🔎 仍然保留的一处

`ModuleInstanceGraph.port_to_internal` / `internal_to_port`（**MIG 自己的**映射）仍在：

- 它映射 `instance_port → module_type.port`（如 `top.u_dut.clk → dut.clk`）
- 唯一消费者：`module_extractor.extract_module_edges_from_mig()`（`visualize module --mig` 的
  instance-to-instance 边推导）与 `get_internal_signal()` API
- 它不属于图的连通层（图已单命名空间），属于视图层的启发式；要删需先给
  `visualize module` 换一套实例级边推导 —— 独立任务

## 💡 经验

1. **自映射是"删除后遗留"的典型信号**：`k → k` 说明原语义（进模块）已消失，只剩兼容壳。
2. **删除映射要连快照格式一起改**：`to_dict/from_dict` 是隐式 API，改字段前先全局搜。
3. **测试要跟着语义走**：`port_to_internal` 的断言应改为"实例端口节点存在 + 父网连到它"，
   而不是换个字段名继续断言内部实现。

## 🔗 相关

- 前序: [iter_276 单一命名空间收口](iter_276_clean_single_namespace.md)
