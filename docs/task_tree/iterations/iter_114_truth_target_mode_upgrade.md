# Iteration 114: truth 层 target 模式升级 — 修 generate truth 的 driver 盲区 (cordic/genfor)

**Metadata**:
- **Iteration #**: 114
- **Task Tree Level**: L2 (iter_113 修复的测试兑现)
- **Parent Task**: [tasks/L2_cla_nested_generate_fix.md](../tasks/L2_cla_nested_generate_fix.md)
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

iter_113 修复 (graph_builder.walk 真正下钻 generate) 的直接收益验证 + 修掉
iter_111/iter_109 truth 的 **driver 盲区**: cordic/genfor truth 此前用 UnifiedTracer
无 target → driver 走 type-level 旧路径 → generate 实例内部逻辑从未被提取/断言
(旧 "rotator DRIVER >50" 计数实为 connection 端口自环 120 条, 非内部逻辑)。

## 🔬 实际结果

### 验证: iter_113 修复在 cordic 上的兑现

target 模式 (cordic) rotator-scope DRIVER dst **150**:
- x_1/y_1/z_1 ×15 (rotator 内部流水状态, always_ff) — 修复前 0 提取
- x_o/y_o/z_o ← x_1/y_1/z_1 (输出寄存器链)
- 源含字面量 '0' (reset 分支) — 作用域断言需放行无 '.' 字面量源

### truth 升级 (2 文件)

| 文件 | 改动 |
|---|---|
| `test_cordic_pipeline_truth.py` | builder 切 target='cordic' (SVCompiler+SemanticAdapter+GraphBuilder); +4 断言: 内部状态 x_1/y_1/z_1 全 15 驱动 / x_1 ← x_i+y_i_shifted 操作数 / x_o←x_1 输出链 / rotator scope 内部状态恰 45 |
| `test_genfor_instance_truth.py` | builder 切 target='top'; test_submodule_logic 由类型作用域 (rot.x→rot.xo) 改为**实例作用域** (top.g[i].U.x→xo ×4) + 断言类型作用域残留不存在 |

两文件现有断言在 target 模式全部保持通过 (连接/实例节点/链断言不变)。

### 验证

- 受影响批次 61 passed (cordic 10 + genfor 6 + cla 6 + 各 unit)
- 全量回归结果见 commit

## 💡 关键发现 / 决策

1. **无 target 的 UnifiedTracer 构建 ≠ target 构建**: type-level driver 路径对
   "generate 实例内部" 是盲区 — 凡断言 generate 实例内部逻辑的 truth **必须
   target 模式** (iter_111/109 truth 是测试资产, 同样受此盲区影响, 本轮补齐)。
2. **driver 源含字面量常量** (reset 分支 0) — 断言实例作用域时需放行无 '.' 源。

## 📌 状态

- ✅ 2 个 truth 文件升级 (+10 断言), 全量回归见 commit
