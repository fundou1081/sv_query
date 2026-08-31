# Iteration 070: 重建 test_generate_real_world — strict 编译通过 (修正测试方式)

**Metadata**:
- **Iteration #**: 070
- **Task Tree Level**: L2
- **Parent Task**: generate 相关测试修复 (方豆: "剩下那些 generate 相关的, 尝试修复语法错误, 让编译通过。可能本来测试目的也有不对的")
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (重建测试 strict 编译通过, 保留真实项目 generate 覆盖)

## 🎯 本次目标

方豆: 修复 generate 相关测试的编译问题。核实: 其余 9 个 generate 测试 (39 passed)
无编译错误 — **问题只在被删的 test_generate_real_world** (ZipCPU 单文件缺依赖 →
UnknownModule → 依赖 --no-strict)。方豆提示"测试目的可能也有不对的" — 重建修正。

## 📊 当前状态 / 预期结果

- 原文件: 单文件 (wbxbar 等) + --no-strict, 方式错误
- 预期: 用能 strict 编译的真实项目重建, 保留"真实 generate 覆盖"目的

## 🔬 实际结果

### 重建方案 (修正原测试的方式错误)

1. **候选验证**: zipcpu 全 rtl (51 文件) strict 编译通过 (3751 nodes / 5269 edges,
   iter_058 已验证); wbxbar 在 sim/rtl 不在 rtl/ — 改用 rtl/ 内 generate-heavy
   模块 (idecode 25 generate lines / zipcore)
2. **新测试** (test_generate_real_world.py, 4 测试, **strict 编译无 --no-strict**):
   - test_strict_compile_succeeds: ZipCPU 全 rtl strict 编译成功
   - test_graph_scale_reasonable: 图 >1000 节点/边 (真实 RTL 规模)
   - test_generate_heavy_modules_present: idecode/zipcore generate 展开信号存在
   - test_cross_module_driver_edges: DRIVER 边 >100 (generate 实例化跨模块连接)

### 关键修正 (方豆提示"测试目的不对"的落地)

| 原测试 | 问题 | 重建后 |
|---|---|---|
| 单文件 + --no-strict | 缺依赖模块, 违反纪律 #1 | 全 rtl strict 编译 |
| 断言 SVG 产出 (CLI 黑盒) | 依赖 visualize 路径, 不稳 | 直接断言图行为 (节点/边/模块) |
| wbxbar (sim/rtl) | 不在 rtl/ glob | idecode/zipcore (rtl/ 内) |

### 验证

- 新测试 4 passed (6.35s); ruff 全过
- regression 全量: 760 passed + 2 pre-existing

## 💡 关键发现 / 决策

1. **"测试目的不对"的实质**: 原测试想验证"真实 generate RTL 可分析", 但用
   单文件方式 (缺依赖) 被迫 --no-strict — 方式与目的矛盾。重建用全 rtl
   (有完整依赖) 让目的真正成立, 且断言从"CLI 不 crash"升级为"图行为正确"。
2. **真实项目覆盖保留**: 用仓库外 zipcpu 项目 (沙箱可读), 与 iter_058 真实
   项目等价性评估一致 — 真实 generate 覆盖不再丢失。
