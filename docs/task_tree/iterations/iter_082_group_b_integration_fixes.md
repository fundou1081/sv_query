# Iteration 082: B 组完成 — integration 14 个失败全部解决 (2 修 + 12 环境)

**Metadata**:
- **Iteration #**: 082
- **Task Tree Level**: L1
- **Parent Task**: Test_Assets_ABC → B 修 integration pre-existing 失败
- **Created**: 2026-09-01 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (14 个失败 = 2 个过时断言已修 + 12 个 sandbox 环境 artifact 已定性)

## 🎯 本次目标

B 组: 修 integration 14 个 pre-existing 失败 (iter_080 实测清单)。

## 📊 当前状态 / 预期结果

- 14 failed: benchmark_picorv32 (1) / benchmark_regression (1) / human_output (5) /
  tree_output (5) / real_project_viz (2)
- 预期: 逐个诊断根因, 修到 integration 全绿

## 🔬 实际结果

### 分类: 2 个真实过时断言 + 12 个环境 artifact

**✅ 修了 2 个 (基准过时)**:

1. **test_benchmark_picorv32::test_baseline_l2_values_reasonable**
   - 断言 nodes 400-700, baseline 实际 708 (iter_059 native 迁移 GAP-3 让图 +34%,
     527→708, 图更完整是改善) — 断言没跟上
   - 修: 范围 600-800

2. **test_benchmark_regression::test_10_pct_node_drop_passes + test_node_drop_50_pct_fails**
   - variant 值基于旧 baseline 527: 475 相对新 708 是 -33% (超 30% 阈值) → 误 FAIL
   - 修: variant 改 637 (10% drop) / 354 (50% drop)

**🟡 12 个是 sandbox 环境 artifact (测试正确, 无需改)**:

根因: `ast_cache.py:30 CACHE_DIR = Path.home() / ".svq" / "cache"` — 沙箱环境
`~/.svq/cache` 不可写 (Operation not permitted) → CLI subprocess 全失败 (rc=1)。
这 12 个测试全部是 `run_cli.py` subprocess 型 (human_output 5 / tree_output 5 /
real_project_viz 2), 与 test_trace_include_flags 4 个 unit 失败同源。

**验证**: `HOME=/tmp/svq_home` (可写) 下:
- test_human_output: 10 passed
- test_tree_output + real_project_viz: 11 passed + 5 skipped (显式 skip 设计)
- **integration 全量: 417 passed + 5 skipped, 0 failed** (60s)

## 💡 关键发现 / 决策

1. **"pre-existing failed" 不全是真失败**: iter_058 记的 integration 13-15 failed
   大部分是沙箱 cache 环境假象, 不是代码问题。真问题只有 2 个过时 baseline 断言。
2. **baseline 迁移后测试必须同步**: iter_059 更新 picorv32 baseline (527→708) 时
   没同步 benchmark 测试的断言/variant — 这是文档-测试不同步的典型。
3. **环境验证方法**: HOME 重定向 (HOME=/tmp/svq_home) 绕过 cache 限制,
   是沙箱里验证 subprocess CLI 测试的标准手段 — 应记入 TESTING.md。

## 📌 状态

- ✅ B 组完成: 2 个断言修复 + 12 个环境定性; integration 可写 HOME 下 0 failed
- 下一步: C 组 (扩 truth 层 1:1 金标准)
- 提交: 2 测试文件 + TEST_MAP + L2 任务记录 + 本记录

---

## ⚠️ 事后更正 (2026-09-02, iter_086)

**"12 个环境定性" 中有 2 个是误分类** — test_real_project_viz 的 darkriscv/picorv32
实际是**真实失败**, 不是 cache 环境问题:

- 根因: 本记录的验证用 `HOME=/tmp/svq_home` 重定向, `~/my_dv_proj/picorv32/...`
  展开到不存在路径 → 这 2 个测试被动态 `pytest.skip('not found')` 跳过,
  "0 failed" 未包含它们 (假绿)。
- darkriscv: 断言过时 (`--dot` 写 SVG, 断言查 'digraph') — iter_086 已修
- picorv32: ELK dangling port (elk_bridge SignalRef 解析 edge 侧/emit 侧不一致) —
  iter_086 定位根因, 方豆拍板暂缓
- 教训: **环境定性结论必须核对 skip 清单**; HOME 重定向会坑 `~` 依赖的测试。

