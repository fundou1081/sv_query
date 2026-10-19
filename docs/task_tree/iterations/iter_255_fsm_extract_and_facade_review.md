# Iteration 255: T3-4 — 拆 `unified_tracer.py` 的 FSM 三件套 + 复核"上帝门面"结论

**Metadata**:
- **Iteration #**: 255
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-20 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 提取成功（1,403 → 1,214 行）；⚠️ **修正了评审对 `UnifiedTracer` 的判断**

## 🎯 目标

评审把 `UnifiedTracer` 的"36 个公开方法跨 10 领域"列为 🟠 P1，建议拆成领域门面。
本次先做**可量化的部分**：把与门面职责无关的 FSM 三个类搬出去；再复核"是否真该拆门面"。

## 🔬 结果一：FSM 三件套提取（1,403 → 1,214 行）

| 类 | 行数 | 去向 |
|---|---|---|
| `StateTransition` / `StateMachineInfo` / `StateMachineAnalyzer` | 191 | `trace/core/fsm_analyzer.py`（206 行，含头） |

`unified_tracer.py` 用 re-export 保住路径：

```python
from trace.core.fsm_analyzer import (
    StateMachineAnalyzer, StateMachineInfo, StateTransition,
)
```

既有 `from trace.unified_tracer import StateMachineInfo` 全部继续有效（验证：import 冒烟 + 全量门禁）。

## 🔬 结果二：复核"36 个公开方法是不是问题"

用 AST 量了一遍方法体长度：

| 指标 | 值 |
|---|---|
| 方法总数 | 46（公开 36 / 私有 10） |
| **中位数** | **10 行** |
| 公开方法中 **< 10 行** | **19 / 36** |
| 最长的公开方法 | `build_graph` 151 行 |
| 最长的私有方法 | `_emit_conditional_op_nodes` 173 / `_resolve_class_member_access` 134 |

**结论修正**：`UnifiedTracer` **已经是一个门面**（薄委托：`trace_signal` 3 行、
`trace_loads` 3 行、`trace_fanout` 23 行），它的 36 个方法里 19 个是 2~9 行的转发。
真正的复杂度集中在 **3 个私有方法**（合计 480 行），而不是"方法太多"。

因此**不做**领域门面拆分：

| 方案 | 收益 | 代价 | 判定 |
|---|---|---|---|
| 拆成 `SignalQuery` / `StructureQuery` / … 再让 `UnifiedTracer` 转发 | 文件名/类名更"纯" | 多一层转发；所有 CLI 命令与测试的调用点仍需改；**逻辑一行没少** | ❌ 否决 |
| 保持门面，把 3 个巨型私有方法拆小 | 直接降低单方法复杂度（真正的痛点） | 需读懂图构建细节，风险高 | ⏳ 下一阶段（列为 backlog） |
| 提取与门面无关的类（本次） | −191 行、职责更清晰 | 无 | ✅ 已完成 |

这符合评审自己定的判据：**"输入可由参数表达 + 输出同构"才合并**；反过来说，
**拆分也要有可测量的收益**，而不是为了让类"看起来小"。

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| `unified_tracer.py` | 1,403 行 | **1,214 行** |
| 其中类定义 | 4 个 | 2 个（`InstanceInfo` + `UnifiedTracer`） |
| 新增模块 | — | `trace/core/fsm_analyzer.py`（206 行） |
| 全量测试 | 3422 | **3422 passed / 0 failed** |

## 💡 决策与教训

1. **"坏味道"要用数据复核，不能只凭印象。** 评审时我把"36 个公开方法"直接判为 P1；
   实测中位数 10 行、19 个方法是薄转发 —— 它是个合格的门面。**没有量化就下结论，
   会把重构力气花在错误的地方。**
2. **拆分的目标是"降低单个阅读单元"，不是"减少类的方法数"。** 3 个 130~170 行的私有
   方法才是真正的阅读负担；但它们与图构建强耦合，需单独排期。
3. **re-export 让提取零风险**：搬类时保留导入路径，调用方（含测试）零改动。

## 🔗 相关

- 评审: [2026-10-19_core_smell_review.md §3 A3](../../refactoring/2026-10-19_core_smell_review.md)（**本次修正了该项结论**）
- 前置: [iter_254 拆 visualize.py](iter_254_visualize_split.md)
- backlog: 拆 `_emit_conditional_op_nodes`(173) / `_resolve_class_member_access`(134) /
  `build_graph`(151)；`elk_bridge.expr_trees_to_elk`(908)
