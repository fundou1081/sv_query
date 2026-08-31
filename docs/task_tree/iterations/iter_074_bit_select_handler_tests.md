# Iteration 074: 补 bit_select_handler 单元测试 (signal graph 底层缺口)

**Metadata**:
- **Iteration #**: 074
- **Task Tree Level**: L2
- **Parent Task**: signal graph 底层测试补缺 (方豆: "继续补")
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (8 个单元测试, bit_select_handler 缺口补齐)

## 🎯 本次目标

iter_072 测试地图里 bit_select_handler 0 直接 import (🟡) — 补单元测试。

## 📊 当前状态 / 预期结果

- bit_select_handler: process() = Phase 1 宽度 + Phase 2 位选节点/边 (路径 A) + Phase 3 constraint 位选
- 预期: 直接驱动 (GraphBuilder 建图 + handler.process()) 验证 BIT_SELECT 边

## 🔬 实际结果

### 新测试 (sim/tests/unit/test_bit_select_handler.py, 8 个, 一次全过)

1. RHS 位选 data[7:4] → BIT_SELECT 边
2. LHS 位选 y[3:0] → y
3. 动态索引 data[idx] → data (符号下标聚合)
4. 位选节点 bit_range 属性
5. 无位选 → 无 BIT_SELECT 边 (负面)
6. 2D 数组层级聚合 (packed2d[0] → packed2d)
7. generate-for 内位选 (genvar 展开)
8. constraint 内位选 (Phase 3 不崩溃)

### 关键点

- 直接驱动方式: `GraphBuilder(adapter, target).build()` → `BitSelectHandler(adapter, graph).process()`
- iter_071 修复 (多级 ElementSelect 聚合) 让 2D 数组测试直接通过 — 补测试与之前修复形成闭环
- 一次全过 (bit_select_handler 行为比 connection_extractor 完整, 无新缺口)

### 验证

- 8 passed / ruff 全过
- SIGNAL_GRAPH_TECH_TEST_MAP 更新 (connection_extractor + bit_select_handler 均 ✅)

## 💡 关键发现 / 决策

1. **补测试与修复的闭环**: iter_071 修的多级 ElementSelect 错拼, 本次 test_multidim_hierarchy
   直接验证 — 如果当时没修, 这个测试会失败。补测试让修复有回归保护。
2. **signal graph 底层测试缺口清零**: connection_extractor (iter_073) + bit_select_handler
   (iter_074) 都有直接单元测试了 — 底层技术全覆盖。
