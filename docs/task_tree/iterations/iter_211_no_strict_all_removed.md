# Iteration 211: `--no-strict` 违规写法**全部清除** (测试+脚本), 遗留 18 个失败待修

**Metadata**:
- **Iteration #**: 211
- **Task Tree Level**: L1 (纪律强制)
- **Parent Task**: 方豆指示 "先清掉所有, 然后再修。先确认清掉所有违反纪律的写法, 如果失败了, 就先保持失败的状态, 之后一起修"
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ⚠️ 清理 100% 完成 / 遗留 18 failed (2 文件) — **按指示保留失败状态**

## 🎯 本次目标

把 `sim/tests/` 与 `tools/` 里所有 `--no-strict` **用法**清除 (纪律 1), 允许测试失败,
失败清单留待统一修复。

## 🔬 实际结果

### 清理结果

| 位置 | 处理 |
|---|---|
| `sim/tests/**` 用法 | **0 处** (第一批 111 处 + 本批剩余全部清除) |
| `tools/*.py` 脚本用法 | **0 处** (`coverage_gen_demo.py`: 删 `args.append("--no-strict")` + 禁用该分支 + 文档串改写) |
| **专测该 flag 的 3 个测试文件** | **移出归档** (不是删除): `docs/archive/2026-09-09-nostrict-cleanup/tests/` + README 说明原因与恢复路径 |
| `src/cli/**` 选项定义 | **保留** (给用户的逃生舱; 纪律禁止的是**在测试/脚本里用**) |

清理过程中的自伤与处置 (如实): 机械正则对 4 个"flag 出现在断言/文档串"的文件会破坏语法
→ 3 个纯 flag-behavior 文件走归档, `test_json_contract_adversarial.py` 手工改写文档串,
`tools/coverage_gen_demo.py` 先 `git checkout` 还原再做精确小改 (全部 `ast.parse` 校验通过)。

### 遗留失败清单 (按指示保留, 之后一起修)

全量 canonical: **18 failed / 3298 passed** (8 skipped / 164 deselected), 集中在 **2 个文件**:

| 文件 | 失败数 | 初步诊断 |
|---|---|---|
| `sim/tests/cli/test_visualize_teach_nested_mux.py` | **16** | 该 fixture 有**真实 elaboration 错误**, 过去靠 `--no-strict` 优雅降级后断言仍通过 (iter_210 已发现) → **修 fixture 的 SV** |
| `sim/tests/cli/test_coverage_gen_demo.py` | **2** | 待查 (可能与其 fixture 或 `tools/coverage_gen_demo.py` 的改动相关) |

**这正是纪律要防的"假绿"**: 撤掉 flag 后, 18 个测试立刻暴露它们的 fixture/断言原本没有
真正通过严格模式。

## 💡 关键发现 / 关键技术 / 决策

1. **"允许失败"是有价值的中间状态**: 先一次性清干净 (0 违规) 再统一修, 避免"边清边修"
   导致纪律状态反复 (本轮之前就是那种状态: 清了 111 处, 剩 91 处仍在违规)。
2. **归档代替删除**: 3 个"专测 flag 行为"的文件无法合规化 (其存在目的就是该 flag) →
   移到 `docs/archive/2026-09-09-nostrict-cleanup/` 并写 README, 保留恢复路径。
3. **机械清理必须逐文件语法校验**: 4 个复杂文件被正则破坏 → 全部拦住 (未写回), 手工处置。
4. **失败集中在 2 文件是好消息**: 18/3316 且高度集中 → 修 fixture 即可清零, 不需要大改测试。

## 📢 下一步 (一起修这 18 个)

1. `test_visualize_teach_nested_mux.py`: 用严格模式跑它的 fixture, 看真实 SV 错误并修源码
   (16 个测试应随之全绿);
2. `test_coverage_gen_demo.py`: 诊断 2 个失败 (先看是否与 `tools/coverage_gen_demo.py`
   的行为改动有关);
3. 收口后再把全量门禁跑回 0 failed, 并更新 `docs/INDEX.md` 基线。

## 📎 关联

- 纪律: `AGENTS.md` 核心纪律 1
- 归档: `docs/archive/2026-09-09-nostrict-cleanup/` (README 说明原因 + 恢复路径)
- 前序: `iter_210_no_strict_removal_batch1.md`
