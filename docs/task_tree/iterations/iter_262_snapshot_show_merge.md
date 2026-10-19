# Iteration 262: `snapshot show` 并入 `snapshot list TAG`（命令 62→61）

**Metadata**:
- **Iteration #**: 262
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-20 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 成功（命令 62→61；state 组 5→4；零测试改动；全量 3422 passed）

## 🎯 目标

按 refined 判据（"输入相同 + 严格子视图" 或 "可选参数特例"）继续压缩 core。
`snapshot show TAG` 与 `snapshot list` 的关系与 `instances`/`instance`、
`class`/`classes` 完全同型：**给不给那个可选参数**。

## 🔬 改动

- `snapshot list` 增加**可选位置参数** `tag`：给了 → 输出该快照详情，省略 → 列出全部
- `show` 的命令体改为 `_emit_snapshot_detail(manager, tag, json_output)`
- 删 `show` 命令注册与 registry 条目（`snapshot` 组 5 → 4）
- **零测试改动**：全仓没有任何测试调用 `snapshot show`（只有 `arch show`）

## 🕳️ 又一记正则误伤（同样被 R1 抓住）

第一版用 `_c("snapshot show",...` 起的正则按"1~2 行"匹配删除，结果把下一条
`_c("snapshot compare"...` 的一半吃掉，`_registry.py` 直接语法错
（`closing parenthesis ')' does not match opening parenthesis '['`）。

改用**按精确整行匹配**（`ln.strip() == '_c("snapshot show", ...)'`）后一次过。

> 这是同一类错误在本目标里的第二次（iter_261 吃掉了 `list-conditioned` 的首行）。
> **结论**：改注册表这类"多行条目"的文件，不要用行数正则；用整行内容匹配，
> 或直接 AST/逐行扫描。

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 规范命令 | 62 | **61** |
| `core` 层 | 25 | **24** |
| `state` 组 | 5 | **4** |
| 叶子（含 2 别名） | 64 | **63** |
| 全量测试 | 3422 | **3422 passed / 0 failed** |

## 💡 现状：核心层已接近"不损失能力"的减法边界

当前 core 24 条：

| 组 | 数量 | 说明 |
|---|---|---|
| semantic | 14 | drivers/loads/impact/evidence/controlflow×2/dataflow/instances/connections/hierarchy/params/ports/paths/class |
| locate | 5 | capabilities/stats/search/graph nodes/graph edges |
| state | 4 | snapshot save/list/compare/delete |
| diagnose | 1 | diagnose \<check\> |

再往下压只剩三种手段：
1. **合并 view 叙述类**（`arch show` / `design show` / `trace overview`）—— 输入完全不同，合并会造出参数并集
2. **合并 `trace evidence` + `trace impact`** —— 回答不同问题（源码证据 vs 传递影响）
3. **动 `exp` 24 条** —— 与 `EXP_NAMESPACE.md` 的"降级区不动"政策冲突

**结论**：core 已到"不损失能力"的下限；目标里的 ~52 需要动 exp 或牺牲可用性。

## 🔗 相关

- 判据来源: [iter_261](iter_261_controlflow_merge.md) §为什么这次可以合
- 前序: [iter_260 diff compare 合并](iter_260_diff_compare_merge.md)
