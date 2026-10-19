# Iteration 254: T3-3 — 拆 `view/visualize.py` (2,376 → 70 行入口 + 5 模块)

**Metadata**:
- **Iteration #**: 254
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-20 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 成功（2,376 → 70 行入口 + 5 个实现模块；全量 3422 passed）

## 🎯 目标

`src/cli/view/visualize.py` 是 CLI 里最大的文件（2,376 行），一个文件装 10 个命令
（graph / dataflow / pipeline / compute / timed / gap / datapath / chain / module / teach）
加 8 个 helper。评审列为 T3-3。

## 🔬 实际结果

| 文件 | 行数 | 内容 |
|---|---|---|
| `visualize.py` | **70** | `vis_app` + 导入 + 10 条命令注册 |
| `visualize_plots.py` | 539 | graph / dataflow / pipeline / compute / timed / gap / datapath |
| `visualize_chain.py` | 793 | `chain`（383）+ `_generate_chain_dot`（366） |
| `visualize_teach.py` | 427 | `teach` + DOT/HTML 渲染 |
| `visualize_common.py` | 419 | `_emit_split_by_module` / `_auto_detect_io_ports` / `_run_graph_visualization` / `_run_gap_visualization` / `_resolve_signal_id` |
| `visualize_module.py` | 295 | `module` + `_module_def_cluster` / `_write_module_dot` |

### 手法

沿用 iter_253 拆 `trace.py` 的模式：

1. 用 AST 取每个函数的精确行区间，按**职责**分组搬到新文件
2. **去掉 `@vis_app.command(...)` 装饰器**，统一由 `visualize.py` 末尾注册
   （避免子模块反向 import `vis_app` 形成环）
3. 共享 helper 下沉到 `visualize_common.py`，需要的模块显式 import

### 拆分时踩到的坑（一次就抓到）

第一次跑 `sim/tests/cli` **66 个失败**：`teach` / `chain` / `plots` 三个模块调用了
被我搬到 `visualize_common` 里的 helper，但没加 import。补三行 import 后全绿：
- `visualize_chain` → `_auto_detect_io_ports`
- `visualize_teach` → `_resolve_signal_id`
- `visualize_plots` → `_emit_split_by_module`, `_run_gap_visualization`

> 这正是"拆分要用测试兜底"的理由：跨模块名字引用肉眼查不全，而全量门禁一次就给答案。

### 验证

- 10 个 `visualize <子命令> --help` 全部 rc=0
- `sim/tests/cli` **424 passed**；全量 **3422 passed / 0 failed**
- `main.py` 仍只 `from cli.view.visualize import vis_app`（外部导入零改动）

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| `view/visualize.py` | 2,376 行 | **70 行** |
| `view/` 模块数 | 3（arch / design / visualize） | **8** |
| 单文件最大 | 2,376 | **793**（visualize_chain） |

## 💡 决策

1. **按"命令族"切，不按行数切**：chain 自带 366 行 DOT 生成，和 `chain` 命令强耦合 → 同文件；
   `teach` 自带 DOT+HTML 渲染 → 同文件；其余 7 个"纯出图"命令共享同一批选项 → 合在 `plots`。
2. **入口文件只做注册**：70 行里没有业务逻辑，改命令行为时不需要在 2,376 行里找。
3. **不顺手改逻辑**：本次是纯搬运，所有函数体一字未动 —— 这样"全量门禁绿"才是
   "搬运正确"的证据，而不是"顺手修好了某处"的混合结果。

## 🔗 相关

- 评审: [2026-10-19_core_smell_review.md T3-3](../../refactoring/2026-10-19_core_smell_review.md)
- 同模式: [iter_253 拆 semantic/trace.py](iter_253_trace_split.md)
- 剩余 T3: `elk_bridge` 908 行函数 / `UnifiedTracer` 36 方法
