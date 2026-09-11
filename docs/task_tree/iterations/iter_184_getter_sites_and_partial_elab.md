# Iteration 184: getter 点续修 + "部分 elaboration" 真相暴露

> ⚠️ **iter_185 更正 (2026-09-08)**: 本记录里 "语料含非 UTF-8
> identifier / 内存压力导致部分 elaboration" 的归因 **已被证伪**。
> 真因 = `SVCompiler` 的 `SourceManager` 生命周期 (局部变量被 GC →
> 源文件 buffer 释放 → 符号名是指向释放内存的 `string_view`)。
> 见 `iter_185_slang_sourcemanager_lifetime.md`。本记录作为时间点
> 快照保留, 不修改当时观测数据。

**Metadata**:
- **Iteration #**: 184
- **Task Tree Level**: L1
- **Parent Task**: (iter_182/183 收敛续; iter_181 backlog)
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ⚠️ 崩溃消除 (3/5 → 0/4), 但暴露底层语料问题 (部分 elaboration)

## 🎯 本次目标

方豆 "继续" — 验证 iter_182/183 修复对 wrapper 语料间歇崩溃的实际效果。

## 🔬 实际结果

**修复前实测 (5 次)**: **3/5 崩溃** (`UnicodeDecodeError`, 无输出) — 说明
iter_182/183 后仍有余点。抓栈定位:
1. `graph_builder.py:822` — `toplevel[0].name` (getter) → 修 (`safe_attr`)
2. `bit_select_handler.py:330` — `mod.name` (getter, **平行实现**) → 修

**修复后实测 (4 次)**: **0/4 崩溃** ✓ — 但结构指标波动剧烈:
nodes **1,076 ~ 3,408**;clk fanout **0 ~ 137**。

**关键结论 (真相暴露)**: 崩溃消除后可见 — 该 filelist (axi 语料) 含**非 UTF-8
垃圾 identifier**, elaboration **本身不完整且不稳定** (clk fanout 有时 0)。
即:
- `safe_attr` 的收益 = **崩溃 → 优雅降级** (benchmark 不再中断), 这是正确方向;
- 但**精确结构基准在该语料上不可得** — 与 iter_180 的"深结构基准"设想冲突。
  → 基准保留**结构性下限**; 断言改 `clk fanout ≥30 **或** nodes ≥800`
  (部分 elaboration 时 clk=0 属预期, 不再误判);
  → **建议换干净语料** (或先清理 axi 语料垃圾字节) 才能得到精确基准。

## 💡 关键发现 / 决策

- **"消除崩溃" 不等于 "数据正确"**: 崩溃曾把语料问题掩盖成"随机失败"; 优雅降级后
  才看清 elaboration 不完整。这是"先让它不崩, 再评估数据可信度"的两步走。
- **平行实现是同类 bug 的温床**: `graph_builder._create_hierarchical_bit_nodes`
  与 `bit_select_handler._create_hierarchical_bit_nodes` 是两套同构实现, 修一处
  必须查另一处 (iter_134 也踩过同构双实现)。
- **基准语料要"干净"**: 精确基准依赖可复现的完整 elaboration; 含垃圾字节的第三方
  语料只适合做"不崩 + 下限"类断言。
