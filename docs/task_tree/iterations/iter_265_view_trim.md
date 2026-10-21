# Iteration 265: 删 3 个 view 命令（`compute` / `timed` / `gap`），默认可见 34

**Metadata**:
- **Iteration #**: 265
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-21 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "可以清，我们做减法"）
- **Outcome**: ✅ 成功（命令 37→34；view 13→10；默认可见 37→34；全量 2291 passed）

## 🎯 目标

把默认可见面从 37 压到目标区间（~33）。评审文档 §5.2 早就标了三个候选，
其中两个写着"保留价值待确认"，本次按使用度结案。

## 🔬 三个命令的判断

| 命令 | 测试引用 | 判断 |
|---|---|---|
| `visualize compute` | 1 个测试文件 | 运算架构图；与 `timed` 是同一件事的两种画法 |
| `visualize timed` | 1 个测试文件 | 时间轴运算图；**只是 compute 的另一种布局** |
| `visualize gap` | **0 个测试** | 验证缺口可视化 —— 它依赖的"风险分级/覆盖率"正是 iter_263 退役的那批想法 |

- `compute` / `timed`：两者输出同一类信息（哪个信号经过什么运算符），差别只在布局。
  留两个等于让使用者在"我该看哪个"上做无意义选择。
- `gap`：它的语义是"高亮有风险但没 SVA/没覆盖的信号"，而风险分级与覆盖率评估
  已经在 iter_263 整体退役 —— 这个视图失去了数据来源的定义，属于**孤儿视图**。

## 🔧 改动

- `src/cli/view/visualize_plots.py`：删 `compute` / `timed` / `gap` 三个函数
- `src/cli/view/visualize.py`：删 3 处注册与 import
- `_registry.py`：删 3 条 `_v(...)`
- 归档 2 个测试文件（`test_visualize_compute.py` / `test_visualize_timed_compute.py`）
- 文档同步：`USER_GUIDE` / `VIZ_COMMANDS` / `CLI_COMMAND_CHEATSHEET` / `docs/README` 删对应小节

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 规范命令 | 37 | **34**（core 24 + view 10） |
| 叶子（含 2 别名） | 39 | **36** |
| **默认可见** | 37 | **34**（目标 ~33 ✅） |
| `src/` 行数 | 46,480 | **46,332** |
| 全量门禁 | 2310 passed | **2291 passed / 0 failed**（−19） |

## 💡 决策

1. **删而不是合并 `compute`/`timed`**：合并要造一个 `--timed` 开关，等于把"选布局"
   变成"记参数"。两个都不常用 → 直接删更干净；将来真需要再按新需求设计。
2. **`gap` 属于"想法退役后的孤儿"**：一个视图如果依赖已退役概念的判定标准，
   留着它只会输出没人能定义对错的图。
3. **没动 `teach` / `datapath`**：它们有 7~11 处测试引用、语义独立，
   属于"能用但没被验证过"的中间地带，留给方豆后续判断。

## 🔗 相关

- 评审候选: [2026-10-19_core_smell_review.md §5.2](../../refactoring/2026-10-19_core_smell_review.md)
- 前序: [iter_264 失联库清理](iter_264_dead_libs_cleanup.md)
- 视图清单: [docs/VIZ_COMMANDS.md](../../VIZ_COMMANDS.md)
