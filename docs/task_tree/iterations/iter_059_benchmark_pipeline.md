# Iteration 059: #7 收尾 — 全管线 benchmark (native 迁移后)

**Metadata**:
- **Iteration #**: 059
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #7 迁 pyslang 11.0 native API
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (#7 全部子任务完成)

## 🎯 本次目标

方豆 "跑#7 吧" — #7 剩余项: 全管线 benchmark (tools/benchmark/run_benchmark.py),
验证 native 迁移后的端到端表现, 建立新 baseline。

## 📊 当前状态 / 预期结果

- 枚举级 benchmark 已做过 (iter_057): native 2.14x (verilog-axi 641→300ms)
- 全管线 benchmark 工具现成 (PR5 2026-06-15), 旧 baseline: picorv32.json (迁移前)
- 预期: 全管线跑通, 图规模因 GAP-3 变大 (嵌套 generate 实例增加), 性能记录

## 🔬 实际结果

### 1. picorv32 (对照迁移前 baseline 2026-06-15)

| 指标 | 迁移前 (递归) | 迁移后 (native) | 变化 |
|---|---|---|---|
| L2 nodes | 527 | **708** | **+34.3%** (GAP-3: native 找全嵌套 generate 实例 → 图更完整) |
| L2 edges | 1199 | 1280 | +6.8% |
| build_time | 0.63s | 0.96s | +0.33s (含 2 个月其他改动, 不可归因; 且图大 34%) |
| IM | 2 | 2 | — |

check_regression: **全 PASS** (图变大 = 改善, 阈值只防"跌 >30%")。

### 2. verilog-axi (新 baseline, 更大规模)

- **nodes=8221, edges=9457, IM=51**, build 12.16s, **flakiness 确定性 100%**
- 之前 (iter_057) 枚举级: native 2.14x 快于递归

### 3. baseline 更新

- `tools/benchmark/baselines/picorv32.json` — 更新为 native 后 (旧版 git 可追溯)
- `tools/benchmark/baselines/verilog_axi.json` — 新建

## 💡 关键发现 / 关键技术 / 决策

1. **GAP-3 的图规模影响是正面的**: picorv32 节点 +34% 不是 regression — 是
   native 找全了递归漏掉的嵌套 generate 实例, 分析更完整。check_regression 的
   "只能跌不能涨" 语义正好符合 (图变大不报警)。
2. **全管线性能对比受 2 个月其他改动干扰**: build_time 0.63→0.96s 不能归因于
   native 迁移 (#1-#8 重构都在其间)。权威的 native 收益证据 = 枚举级 benchmark
   (同代码状态对比, 2.14x)。
3. **flakiness 100% 确定**: 全管线在图规模上稳定 (GAP-7 的垃圾实例过滤后,
   跨跑一致性良好 — 注意: 这是同一进程多次 build 的确定性, 与跨进程的
   pyslang elaboration 非确定性是两回事)。

## 📌 #7 完成度总结 (iter_053~059)

| 子任务 | 状态 |
|---|---|
| 评估 6 项目等价性 | ✅ 3/6 保留 (darkriscv EQUIVALENT / zipcpu+riscv_core GAP-4), 3 移出 (编译不过) |
| diff 验证脚本 | ✅ verify_native_parity.py (MIG 四表 + 差异归类 + 子进程隔离) |
| G3 计划 | ✅ docs/architecture/pyslang11_native_api_g3_plan.md |
| 实施 (阶段 1+2) | ✅ 5 调用方全量 native + 删 SyntaxTree 死代码 ~920 行 |
| 性能 benchmark | ✅ 枚举级 2.14x + 全管线 baseline |
| 回归全套 | ✅ 0 新回归 (unit/cli/integration/truth) |

**GAP-1~7 全部处理**: 1/2/5/6/7 修复, 3/4 拍板接受 (native 更正确)。
