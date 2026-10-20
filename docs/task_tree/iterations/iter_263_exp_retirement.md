# Iteration 263: exp 区整体退役（命令 61 → 37；源码 −8,118 行）

**Metadata**:
- **Iteration #**: 263
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-20 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "可以动 exp。这些 exp 都是当时想到的创意想法，但没有实际落地，以后未来逐个再做，现在做好文档，只记录想法、解决问题场景……在现阶段减法可以简洁掉。"）
- **Outcome**: ✅ 成功（命令 61→37；源码 59,725→51,607 行；全量 2633 passed / 0 failed）

## 🎯 目标

把 `exp` 降级区**整体退役**：CLI 上不再有 `svq exp ...`；
想法只留一份"想法 + 问题场景"清单；实现代码与测试归档。

## 🔬 做法

### 1. 想法留档（`docs/EXP_IDEAS.md`）

按方豆要求只记两列：**想法** / **解决什么问题**。10 条：
协议识别、握手语义、反压与死锁、SVA 抽取与断言覆盖、覆盖率缺口与 covergroup 生成、
验证缺口报告、改动风险分级、约束与随机化可达性、CDC、时序关键路径。

> 刻意不写：CLI 语法、schema、实现方案、测试细节 —— 这些是"重做时再决定"的东西。

### 2. 代码与测试归档（不删除）

| 内容 | 规模 | 去向 |
|---|---|---|
| `src/cli/exp/` 24 个命令 | 4,347 行 | `docs/archive/2026-10-20-exp-attic/cli_exp/` |
| `src/applications/` 支撑库 | 3,724 行 | `.../applications/` |
| 相关测试 | 30 个文件 | `.../tests/` |

### 3. CLI 清理

- `main.py`：删 10 个 exp import + 17 行 `exp_app` 注册块
- `_registry.py`：删 24 条 exp 条目（`exp` 层保留 LayerSpec，命令数 0）
- `capabilities`：只剩 `core 24 + view 13`

### 4. 测试适配（这是本次最费时的部分）

| 情况 | 处理 |
|---|---|
| 纯 exp / applications 测试（30 文件） | 整体归档 |
| 混合文件里依赖 exp 的**用例** | 逐条删除（`test_pyslang_v11_cli_smoke` 3 条、`test_human_output` 2 条、`test_tree_output` 1 条、`test_golden_chain_anomalies` 3 条、`test_cross_viz_consistency` 4 条 + 1 个类、`test_cli_filelist_parity` 4 条） |
| `test_cli_layering` 的 exp 断言 | 改为**反向锁定**："exp 已退役，`svq exp` 必须不存在" |
| `test_json_contract_adversarial` | F1 的 exp 用例换成 core 命令；F4 两条依赖 `timing --max-paths` → 删除 |
| `test_strict_default_filelist` | 命令清单里的 7 条 exp 删掉，测试改名 |

## 🕳️ 顺带抓到的测试隔离 bug

全量跑时 `test_filelist_resolution::test_missing_entry_warns_and_skips` **只在组合运行下失败**
（单独跑通过）。根因：

- 该测试靠 `caplog` 抓 `trace.core.filelist` 的 WARNING
- 某测试文件在**模块 import 期**就构造了 `UnifiedTracer(log_level='ERROR')`
  → `trace` logger 级别被设成 ERROR 且从不复位
- caplog 只能提高 **root** 级别，管不了 `trace` 自己的级别

修法：在 `sim/tests/conftest.py` 加 autouse fixture，每个测试**前后**把
`trace` / `trace.core` 归位到基线（WARNING）。

> 关键点：不能用"快照→恢复"，因为泄漏发生在 **collection 阶段**，快照到的已经是脏值。

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 规范命令 | 61 | **37**（core 24 + view 13） |
| `exp` 命令 | 24 | **0** |
| 叶子（含 2 别名） | 63 | **39** |
| 默认可见 | 37 | **37**（exp 本就不在默认面） |
| `src/` 文件 / 行数 | 164 / 59,725 | **145 / 51,607**（−8,118） |
| 测试文件 | 355 | **325** |
| 全量门禁 | 3422 passed | **2633 passed / 0 failed**（−789，随退役功能一起归档） |

## 💡 决策

1. **退役 ≠ 删除**：代码与测试都归档在 `docs/archive/2026-10-20-exp-attic/`，
   git 历史与目录结构都保留，将来想回看有据可查。
2. **想法文档只写"为什么值得做"**：不写方案、不写 CLI 形态 —— 那些会在重做时重新设计，
   写下来反而会限制思路。
3. **测试数量下降是预期结果**，不是"测试变少所以更绿"：被删的 789 个用例全部依附于退役功能，
   剩下的 2633 个仍然全绿。

## 🔗 相关

- 想法清单: [docs/EXP_IDEAS.md](../../EXP_IDEAS.md)
- 退役说明: [docs/EXP_NAMESPACE.md](../../EXP_NAMESPACE.md)
- 归档: [docs/archive/2026-10-20-exp-attic/README.md](../../archive/2026-10-20-exp-attic/README.md)
- 前序: [iter_262 snapshot show 合并](iter_262_snapshot_show_merge.md)
