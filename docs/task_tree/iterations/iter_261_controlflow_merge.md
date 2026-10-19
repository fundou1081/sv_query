# Iteration 261: `controlflow conditions` 并入 `analyze`（T2 再 −1）

**Metadata**:
- **Iteration #**: 261
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-20 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 成功（命令 63→62；core 26→25；全量 3422 passed）

## 🎯 目标

在不动 `exp` 的前提下继续压缩 core 表面积。评审时我把 `controlflow` 三合一**否决**过
（理由："枚举与单信号查询 schema 不同构"）。本次对 `conditions` 重新评估后**改判**。

## 🔬 为什么这次可以合

| 命令 | 输入 | 输出 | 关系 |
|---|---|---|---|
| `controlflow analyze S` | 一个信号 | `conditioned_drivers[].conditions[]` + warnings | 完整视图 |
| `controlflow conditions S` | **同一个信号** | `conditions[]` + count | 上面那个的**扁平子视图** |

两者**输入完全相同**、分析器相同（`ControlFlowAnalyzer`），`conditions` 只是把
`conditioned_drivers` 里的 conditions 拍平。这不是"两个不同问题"，而是**同一答案的两种呈现**。

**判定规则的细化**（写进任务文件）：
> 两个命令输入相同、且一个是另一个的**严格子视图**时，可以合并为 1 个命令 + 视图开关；
> 若两者回答的是**不同问题**（如 `paths` 与 `dataflow analyze`），则不能合并。

这也解释了为什么当初否决 `paths`+`dataflow`：它们对"同一对信号是否可达"给出不同答案，
是**两套实现**的分歧，而不是视图差异。

## 🔧 改动

- `controlflow analyze` 增加 `--conditions-only`
- `conditions` 的实现被删除，其载荷在 `analyze` 里用同一分析器生成
  （`command: "controlflow"` + `subcommand: "conditions"` 保持可识别）
- `_registry` 删 `controlflow conditions`；测试 2 处调用改为
  `analyze ... --conditions-only`
- 速查表同步

## 🕳️ 一次被机械检查救回来的事故

删 registry 条目时用的正则 `[^\n]*\n[^\n]*\n`（"删 1 条目的 2 行"）误伤了**下一条**：
`controlflow conditions` 的 note 是**单行**，于是正则把紧跟的
`controlflow list-conditioned` 首行一并吃掉。

结果：`list-conditioned` 在 CLI 上还在，注册表里没了。

**是 `check_cli_layers` 的 R1 抓到的**：

```
❌ 新增违规 1 条: R1 未分层: `controlflow list-conditioned` 不在 cli/_registry.py 中
```

补回后 `叶子 64 / 已登记 62`、`✅ 无新增违规`。

> 教训：用正则删"多行条目"必须**按条目内容匹配**（如 `_c("key"` 开头 + 到下一条 `_c(` 之前），
> 不能按固定行数。机械检查在这里直接避免了"注册表与 CLI 不同步"的静默漂移。

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 规范命令 | 63 | **62** |
| `core` 层 | 26 | **25** |
| 叶子（含 2 别名） | 65 | **64** |
| 全量测试 | 3422 | **3422 passed / 0 failed** |

## 🔗 相关

- 评审: [2026-10-19_core_smell_review.md §5.2](../../refactoring/2026-10-19_core_smell_review.md)
- 前置: [iter_260 diff compare 合并](iter_260_diff_compare_merge.md)
