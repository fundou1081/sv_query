# Iteration 252: 删除 `dev` 层残留 —— `expression` 3 命令归档 (叶子 93→90)

**Metadata**:
- **Iteration #**: 252
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 成功（规范命令 67→64、叶子 93→90、`dev` 层清零；全量 3422 passed）

## 🎯 目标

评审里 `dev` 层被定义为"开发者内部调试，不进用户文档"，但实际有 3 个命令
（`expression build|func|cond`）挂在 CLI 上，还被速查表当用户功能写着。

## 🔬 判定：删掉，而不是合并

先考虑过合并成 `expression --kind build|func|cond`，但检查实现后放弃：

| 事实 | 影响 |
|---|---|
| `build` 的 `--file` 路径**从未实现**（代码里自己打 warning 说 "当前未使用"） | 命令本身半成品 |
| 三个命令必需参数完全不同（`--operands/--expression` vs `--name/--args` vs `--cond/--true/--false`） | 合并后是 9 个互斥选项的并集，比 3 个明确命令更难用 |
| 全仓 **0 个测试**引用 | 删掉无回归风险 |
| 底层能力仍在（`trace.core.builder.expression_builder.ExpressionBuilder`） | 需要时可从 Python 调用 |

**结论**：删除 CLI 层入口，模块整体归档（满足"归档不删除"）。

### 改动

- `main.py`：移除 `expression_app` 注册与 import
- `_registry.py`：删除 3 条 `dev` 条目；`dev` LayerSpec note 改为"当前无命令"
- `src/cli/dev/expression.py`（255 行）→ `docs/archive/2026-10-19-src-archived/cli_dev/`
- 顺带清掉残留空目录 `src/cli/dev/`、`src/cli/commands/`（只剩一个 `.bak` 文件）
- 速查表：删掉 3 条 `expression` 用法，并在文件头标注"本文已部分过期，权威清单是 CLI_SURFACE.md"

### 验证

- `svq --help` 中 `expression` 出现次数 = **0**
- `capabilities`：total 64（core 27 / view 13 / exp 24，dev 0）
- 叶子 90（64 规范 + 26 别名）
- 全量门禁 **3422 passed / 0 failed**

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 规范命令 | 67 | **64** |
| `dev` 层命令 | 3 | **0** |
| 叶子（含别名） | 93 | **90** |
| `src/cli/` 目录 | 9 个子包 | **8**（dev 与 commands 清空） |

## 💡 决策

1. **删层比并命令更诚实。** `dev` 层的前提是"有内部调试命令"；当这些命令是半成品时，
   合并只是把半成品包装成一个更复杂的命令。删掉 + 保留 Python API 是更小的承诺。
2. **发现速查表已经不可信**：它把 `fix`（iter_248 已删）和 `expression` 都当用户功能写着，
   头部还停在 2026-08-26 的"23 top-level commands"。已加显式警告并指向生成物
   `CLI_SURFACE.md` —— **手写清单必须让位给生成物**，否则每次减法都要手工追。
3. **空目录也是债**：`src/cli/commands/` 只剩一个 `.bak` 文件却还在源码树里，
   会误导 grep 与目录度量。

## 🔗 相关

- 归档: [docs/archive/2026-10-19-src-archived/README.md](../../archive/2026-10-19-src-archived/README.md)
- 前置: [iter_251 隐藏老路径](iter_251_hide_legacy_paths.md)
