# Iteration 260: `diff compare` 并入 `snapshot compare`（T1 遗留项收口）

**Metadata**:
- **Iteration #**: 260
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-20 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 成功（命令 64→63；state 组 6→5；全量 3422 passed）

## 🎯 目标

T1 里把 `diff compare` **推迟**到了 T2（当时判断"入参与 schema 都不同，不属零风险"）。
本次收口：按注册表里早就写着的计划（"`diff compare` 并入 `snapshot compare`"）真正合并。

## 🔬 设计：一个命令，两种输入

`snapshot compare A B` 现在按参数形态分派：

| 输入 | 行为 |
|---|---|
| 两个都是**已存在文件**（或 `.sv/.v/.svh` 结尾） | 编译成图 → 健康度/耦合/可达性 diff（原 `diff compare`） |
| 否则 | 按**快照 tag** 比较（原行为） |

- `diff.compare` 改造成纯函数 `compare_files(old, new, signal, json_output, pretty)`
- `snapshot.compare` 增加 `--signal`（只在文件模式有意义）
- 删 `diff` Typer 子应用注册与 `_registry` 里的 `diff compare` 条目
- 测试 4 处 `["diff","compare",...]` → `["snapshot","compare",...]`

### 兼容性

`svq diff compare A B` 不再存在（破坏性）。新用法 `svq snapshot compare A B`。
两个命令的 JSON 信封字段本来就不一样（`graph_diff` vs `node_count_diff`），
合并后**按输入形态各自保持原样**，不做 schema 统一。

## 🕳️ 一个自己造的坑

第一次插入 `_looks_like_file()` 辅助函数时，把新函数插到了
`@snapshot_app.command()` 与 `def compare(` **之间** —— 装饰器套到了辅助函数上，
`compare` 从 CLI 消失，冒烟直接报 `No such command 'compare'`。

修法：把辅助函数移到装饰器**之前**。这类错误只有"立刻跑一次命令"才能发现，
单看 diff 很难注意。

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 规范命令 | 64 | **63** |
| `core` 层 | 27 | **26** |
| `state` 组 | 6 | **5** |
| 叶子（含 2 个别名） | 66 | **65** |
| 全量测试 | 3422 | **3422 passed / 0 failed** |

## 💡 决策

1. **按输入形态分派，而不是加 `--mode`**：用户不需要先理解"我有两个文件还是两个快照"，
   路径存在与否本身就是判据。`--mode` 反而多一个要记的东西。
2. **不做 schema 统一**：两种模式的输出本来就不同（一个讲健康度，一个讲节点数），
   硬统一会丢信息。命令合并的收益是"少一个入口"，不是"字段一致"。
3. **当初推迟是对的**：T1 的目标是"零行为变化"，而这个合并改的是命令语义。
   放到 T2、有测试保护时做，代价小得多。

## 🔗 相关

- T1 的推迟决定: [iter_245](iter_245_t1_dead_code_cleanup.md)
- 评审: [2026-10-19_core_smell_review.md §4 B6](../../refactoring/2026-10-19_core_smell_review.md)
- 分层任务: [L1_cli_layering.md P4](../tasks/L1_cli_layering.md)
