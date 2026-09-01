# Iteration 083: C 组完成 — truth 层扩 1:1 金标准 (10 测试) + spec 幽灵文件修复

**Metadata**:
- **Iteration #**: 083
- **Task Tree Level**: L1
- **Parent Task**: Test_Assets_ABC → C 扩 truth 层
- **Created**: 2026-09-01 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (C 组 2 个 truth 文件 10 测试 + 1 个 spec 修复; A/B/C 全部完成)

## 🎯 本次目标

C 组: 扩 truth 层 1:1 金标准 (case27 之外) — 用图结构精确断言锁定关键语义不变量。

## 📊 当前状态 / 预期结果

- truth 层原 3 文件 22 测试 (case27 SVG / d1 generate flatten / spec unsupported)
- 预期: 补 generate-for 链 + 跨模块连接 2 个 1:1 truth

## 🔬 实际结果

### 新增 2 文件 10 测试 (全绿, ruff clean)

**1. test_generate_for_chain_truth.py (6)** — golden_dataflow_29 (3 级 generate-for 链):
- 节点: buf1[0..3] (4) / buf2[0..2] / buf3[0..2] 精确存在 + base 节点
- 链边: data→buf1[0] (头), buf3→chain_out (尾), buf1[i+1]→buf1 (stage1 回边),
  buf1→buf2[i] + buf2→buf3[i] (级间), prod→各 stage 索引节点
- genvar i 非信号节点

**2. test_cross_module_truth.py (4)** — minimal_3module (top→sub→leaf 链):
- 实例节点: sa1 / sa1.lp1 / sa1.la1
- 端口连接: sa1.clk→lp1.clk, sa1.data_i→la1.a, sa1.valid_i→lp1.data_i
- 叶子回流: lp1.data_o→leaf_ready, la1.sum→sum_o
- 未实例化 synchronizer 隔离 (不在 sa1 层级)

### 顺带修复: spec 幽灵文件 (C 组全量跑发现)

`test_replication_lhs_is_sv_illegal` 两个 bug:
1. **引用 /tmp/spec_probe_repl_lhs.sv 幽灵文件** — 从未创建, FileNotFoundError
2. **断言消息错误** — 期望 "expression is not allowed as a statement", pyslang
   实测报 [ExpressionNotAssignable] / "expression is not assignable"

修复: 补 fixture spec_golden/probe_repl_lhs.sv + 断言改 ExpressionNotAssignable。
**探针发现**: pyslang 对 `{4{q},4{q},4{q}}=q` (非等宽) 宽容接受, 对 `{4{q}}=q`
(等宽) 报 ExpressionNotAssignable — fixture 用可复现的等宽形式。

### 验证

- truth 层全量: **28 passed + 4 skipped** (显式 skip, d1 的 pyslang mutex lock)
- regression: 808 passed (无破坏)
- ruff clean
- 有效性: revert test_generate_for_chain_truth 断言 → FAIL → 恢复通过

## 💡 关键发现 / 决策

1. **1:1 truth 的价值**: 图结构精确断言 (节点集合 + 边集合) 是"语义不变量" —
   任何提取逻辑变化 (pyslang API/generate 展开/位选) 导致偏离立刻暴露, 比
   regression 行为断言 (单边存在) 更强。
2. **幽灵文件是 pre-existing 测试坏死的典型**: 引用从未创建的 /tmp 路径,
   断言文本也是编的 (没跑过) — 这类测试要么修要么删, 不能留。
3. **pyslang 对 replication LHS 的行为非直觉**: 等宽报错, 非等宽接受 —
   fixture 必须选可复现形态。

## 📌 状态

- ✅ C 组完成 (2 truth 文件 10 测试 + spec 修复)
- ✅ **A/B/C 全部完成** (A: 42 语法测试 / B: 2 断言修复+12 环境定性 / C: 10 truth+1 spec)
- 提交: 2 truth 文件 + spec fixture + spec 测试 + TEST_MAP + 任务记录 + 本记录
