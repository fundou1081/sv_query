# Iteration 071: 修复 2 个 pre-existing 失败 — regression 首次全绿

**Metadata**:
- **Iteration #**: 071
- **Task Tree Level**: L2
- **Parent Task**: pre-existing 失败修复 (方豆: "再来看那两个 pre existing failed" → "修吧")
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (2 个失败修复, regression 762 passed **0 failed** — 首次全绿)

## 🎯 本次目标

修复 2 个 pre-existing 失败: test_cross_module_connection (断言过时) +
test_sub_bytes_genvar_iteration (功能缺口)。

## 📊 当前状态 / 预期结果

- Test 1: 断言依赖已移除的 self-loop (2026-08-13 跳过 SELFLOOP FIX)
- Test 2: 数组层级聚合缺失 (data_o[i][j] → data_o[i] 无边)

## 🔬 实际结果

### Test 2 (功能缺口, 真 bug): 多级 ElementSelect 聚合边缺失

**根因**: graph_builder.py `_create_hierarchical_bit_nodes` 的 full_id 覆盖逻辑
(line 660-668):
- 意图: 符号下标 (q[i] 变量索引) 时 chain 末位是 `top.q[?]` placeholder,
  用 full_id 的 `[i]` 替换
- **bug**: 无条件覆盖 (只要 `hit.full_id`), 且用 `full_id.find('[')` 取**首个**
  `[` 起的整个 select 文本 (`[0][0]`) 追加到 `base_no_sel` (已去掉一个维度) →
  `data_o[0][0]` 被错拼成 `data_o[0][0][0]` (多一个维度)
- 后果: `data_o[i][j] → data_o[i]` 聚合边缺失 → `trace_signal('data_o')` 查根
  信号返回 0 驱动 (子节点驱动无法向上聚合)

**修复**: 覆盖条件加 `'?' in child_id` — 只在 chain 末位确实含 placeholder 时
覆盖 (多级 ElementSelect 的 chain 末位已完整, 无需覆盖)。

**验证**: data_o[0][0] → data_o[0] 聚合边出现; trace data_o → [data_i] ✓

### Test 1 (断言过时): 更新为跨模块内部驱动验证

实例端口 self-loop (inst_port_id == child_signal_id) 自 2026-08-13 被有意跳过,
原 out_edges 断言依赖已移除行为。更新为验证**模块定义层内部驱动关系**:
- tb.clk → tb.clk_out (tb 内部 assign)
- dut.clk → dut.reg_data (CLOCK) + 32'd0 → dut.reg_data (DRIVER)

### 验证 (全绿)

- test_sub_bytes_genvar_iteration: PASSED
- test_cross_module_tracking: 49 passed
- **regression: 762 passed, 0 failed — 首次全绿**
- unit+cli: 1435 passed + 24 failed (沙箱 artifact, baseline 一致)
- truth: 4 passed; ruff: 零新增 (2 个 pre-existing lint 未动)

## 💡 关键发现 / 关键决策

1. **2 个失败性质完全不同**: 一个真 bug (多级 select 错拼, 影响数组聚合追踪),
   一个过时断言 (依赖已移除行为)。诊断必须分开做。
2. **bug 的隐蔽性**: full_id 覆盖逻辑只在**符号下标**场景必要, 却无条件执行 —
   多级字面索引 (genvar 展开) 场景被误伤。加 `'?' in child_id` 守卫后, 两种
   场景都正确。同类 bug 检查: 所有"为某场景设计的替换逻辑"都要确认不会误伤
   其他场景。
3. **回归首次全绿的意义**: 此前 2 个失败存在已久 (至少 iter_048 前), 一直
   被当"known issue"。这次深挖发现一个是真 bug — 说明"known pre-existing
   failure"也可能藏着真缺陷, 值得定期复查。
