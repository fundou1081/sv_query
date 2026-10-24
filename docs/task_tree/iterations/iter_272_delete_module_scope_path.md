# Iteration 272: 删除模块定义级图路径（单一命名空间）

**Metadata**:
- **Iteration #**: 272
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-24 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "先 1 后 2" —— 1=删模块定义级逃生路径）
- **Outcome**: ✅ 完成（图只有实例级一种模式；全量 2306 passed / 0 failed）

## 🎯 目标

iter_271 切默认后仍留了逃生口（`SVQ_INSTANCE_SCOPE=0` / `--no-instance-scope`）。
本次把它**彻底删除**：代码里不再有"模块定义命名空间"的图模式。

## 🔧 删除清单

| # | 删除内容 |
|---|---|
| 1 | `UnifiedTracer.build_graph(instance_scope=...)` 参数 + `SVQ_INSTANCE_SCOPE` 环境变量 |
| 2 | `GraphBuilder(instance_scope=...)` 参数；`_configure_instance_paths` / `_drop_orphan_type_nodes` 改为**无条件执行** |
| 3 | CLI `--instance-scope/--no-instance-scope`（paths / dataflow）+ `build_tracer` 透传参数 |
| 4 | `DriverExtractor.extract()` 的**模块级 else 分支**（遍历 `adapter.get_modules()`）→ 改为显式告警 + 空结果（不再静默退回） |
| 5 | `PathResolver._neighbors` 的 MIG 虚拟跳（进/出模块）—— 目标 id 是模块定义名，已不在图里 |
| 6 | `SignalTracer` 的四处 `_mig_neighbors` 注入 + 三个 MIG 辅助方法（`_mig_neighbors` / `_find_loads_via_mig` / `_find_drivers_via_mig`） |
| 7 | `SignalTracer` / `LoadTracer` 的 `use_mig` 参数（MIG fallback 已无对象） |
| 8 | `sim/tests/unit/test_pr3_mig_fallback.py` 归档（专测已删行为） |

## 🧪 测试调整

| 文件 | 调整 |
|---|---|
| `test_instance_scope.py` | 从"开关测试"变为"单一命名空间不变式"；删掉"默认仍有类型节点"的旧守卫 |
| `test_graph_cache_scope.py` | 去掉 scope 维度；改为 target 隔离 + filelist key |
| `test_generate_real_world.py` | 不再用 `instance_scope=False`；改为断言实例级 generate/数组节点 |
| 跨模块遍历 / 适配层 / pulp mock | 去掉 `use_mig=False` 用例与相关断言 |

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 全量门禁 | 2317 passed | **2306 passed / 0 failed**（−11：归档 pr3 专用测试 9 个 + 删 2 个 use_mig 用例） |
| 图模式 | 2 种（实例级 / 模块级） | **1 种** |
| `instance_scope` 引用（src+sim） | 47 处 | **0** |
| `use_mig` 引用 | 34 处 | **0**（`visualize_module --mig` 是另一个语义，保留） |

## 💡 说明

- **MIG 本身保留**：`instances` / `hierarchy` / `arch show` 仍需要实例树与端口方向信息；
  删的是"用 MIG 虚拟跳做跨模块遍历"这套旧机制。
- **`_drop_orphan_type_nodes` 保留**：`connection` / `load` / `clock` 三个 extractor 仍会为
  模块定义建节点；该 pass 是"单一命名空间"的保证。彻底移除需要这三个 extractor 也改实例级，
  属后续独立改动。
- **逃生口没了**：若发现回归，只能 revert 本次提交，不能再靠环境变量回退。

## 🔗 相关

- 前序: [iter_271 实例级切默认](iter_271_instance_scope_default.md)
- 下一步: generate 语义与决策 D2 的收敛（iter_273）
