# Iteration 111: CORDIC 流水线实例链 truth — 真实工业算法 fixture (补记)

**Metadata**:
- **Iteration #**: 111
- **Task Tree Level**: L1 (openrtl 工业算法摸底 → 缺口修复)
- **Parent Task**: CORDIC 摸底验证 (iter_109/110 修复验收)
- **Created**: 2026-09-02 23:34 GMT+8 (commit 329afc3)
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (本文档为 commit 后补记, 原 commit 未附迭代文件)

## 🎯 本次目标

为 CORDIC (真实工业算法, opencores verilog_cordic_core) 建立 truth 层金标准测试 —
真实验证 iter_109 (generate-for 实例化链) 与 iter_110 (嵌套作用域) 修复。

## 🔬 实际结果

- **fixture**: `sim/tests/fixtures/golden_mini/golden_dataflow_39_cordic_pipeline.v`
  (379 行, 拷自 openrtl/verilog_cordic_core/cordic.v, PIPELINE 配置, ITERATIONS=16)
- **测试**: `sim/tests/test_cordic_pipeline_truth.py` (6 个, 集合相等断言):
  15 个 rotator 实例 (带索引路径) / x[0..15] 数组 / 15 级 CONNECTION 链 /
  rotator 内部作用域 (iter_110 修复验证) / 无占位节点 / 图规模
- 结构锁定: 365 节点, 100 DRIVER (iter_110 作用域修复后 rotator 内部信号进图)

## 💡 关键发现 / 决策

truth 层引入**真实工业 fixture** (非自造 toy) — 黄金文件直接拷开源 RTL,
测试 = 对真实结构做集合断言, 比自造 fixture 更能锁住提取质量。

## 📌 状态

- ✅ commit 329afc3 (代码+fixture+测试)
- ⚠️ 迭代文档当时未建 — 本文补记 (2026-09-03)
