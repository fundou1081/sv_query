# Iteration 180: C 路线第二项 — bench 深结构基准 (pr5_wrap) + 2 个真实 bug

> ⚠️ **iter_185 更正 (2026-09-08)**: 本记录里 "语料含非 UTF-8
> identifier / 内存压力导致部分 elaboration" 的归因 **已被证伪**。
> 真因 = `SVCompiler` 的 `SourceManager` 生命周期 (局部变量被 GC →
> 源文件 buffer 释放 → 符号名是指向释放内存的 `string_view`)。
> 见 `iter_185_slang_sourcemanager_lifetime.md`。本记录作为时间点
> 快照保留, 不修改当时观测数据。

**Metadata**:
- **Iteration #**: 180
- **Task Tree Level**: L1
- **Parent Task**: (C 路线: 质量纵深)
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (兑现 iter_145 wrapper TODO; 顺带修 2 个真实 bug)

## 🎯 本次目标

方豆 "走C路线" — 兑现 iter_145 登记的 "wrapper 深度基准 TODO":
`axi_xbar_intf` 默认 `Cfg='0` → 空壳树 → 结构断言只能弱化。

## 🔬 实际结果

**wrapper 基准落地**:
- `sim/tests/fixtures/bench_wrappers/pr5_wrap.sv`: 真实 Cfg
  (4 slv / 3 mst / 32b addr / 64b data) 实例化 axi_xbar_intf。
- `test_benchmark_pr5.py` 新增 `TestBenchmarkWrapperDepth` 3 断言
  (L1 实例链 / L2 深结构 / L3 clk fanout 恢复) + filelist 自动追加 wrapper。
- **基准 (runs=1, depth=4)**: nodes **168 → 2,814**, instantiated_modules 271,
  最大深度 11,`clk_i` fanout **0 → 187** — iter_145 TODO 的链断言**恢复**。
- 记录文档: [docs/BENCH_BASELINE.md](../../BENCH_BASELINE.md) (命令/指标表/限制)。
- 结果: pr5 套件 **13 passed + 1 skipped** (原 10 passed, 新增 3)。

**深结构语料顺带炸出 2 个真实 bug (已修)**:
1. `semantic/_expr_helpers.py` **缺 `safe_str` 导入** — 但只在
   MemberAccess 表达式路径触发 (wrapper 里 axi 的成员访问踩中):
   `NameError: safe_str`。根因: iter_176 搬迁后我曾补过该导入, 但修补字符串
   未精确匹配 → **空操作**(静默未生效), 直到 deep 语料触发才暴露。
2. `extractors/_common.py:589` **非 UTF-8 identifier 解码崩溃**:
   `str(syn)` 抛 UnicodeDecodeError (iter_141 批量修复漏点, `iter_bit_selects`
   回调内)→ 改 `safe_str`, 解不出时退回 `{immediate}[?]` 显式占位。

**新发现 (登记 backlog, 未修)**:
- **benchmark `--runs > 1` 复跑结果退化**: runs=1 → 2 实例/2,814 nodes/clk 187;
  runs=2 → 0 实例/3,915 nodes/clk 0 (同进程二次 build 状态泄漏嫌疑)。wrapper
  基准因此固定 `runs=1`; 复跑稳定性列为独立专项。
- flakiness 阶段对 wrapper 目标失败 (整份 filelist 无 top_modules →
  free-floating type-param 报错, iter_145 同类) → 结构基准用 `--skip-flakiness`。

## 💡 关键发现 / 决策

- **"深结构真实语料"是 bug 探测利器**: 2 个真实 bug 都是空壳基准下**永远走不到**
  的路径 (成员访问表达式 / bit-select 非 utf8)。这印证了 C 路线的价值 — 阈值弱化
  的基准等于放弃探测能力。
- **补丁要验证生效**: 我此前的一次 `replace` 因字符串不匹配没生效却未断言 →
  静默失败; 教训: 脚本化修补必须 `assert old in text` (本次两处修补已加)。
- **基准要写清"为什么是这个数"**: BENCH_BASELINE.md 同时记录空壳 vs wrapper
  对照与断言余量, 使后续调整有依据而非拍脑袋。
