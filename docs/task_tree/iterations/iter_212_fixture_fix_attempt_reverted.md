# Iteration 212: 修 fixture 尝试 → 暴露依赖链, 已回退 (关键发现)

**Metadata**:
- **Iteration #**: 212
- **Task Tree Level**: L1 (纪律收口 / fixture 修复)
- **Parent Task**: iter_211 遗留 18 failed (方豆: 先不处理可视化相关的, 先处理其他的)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ⚠️ 修复方向正确但有**依赖链** → 已回退, 登记为专门批次

## 🎯 本次目标

按方豆指示跳过可视化, 先修非可视化失败 (`test_coverage_gen_demo.py` 2 个)。

## 🔬 实际结果

### 真因确认 (正确): fixture `sim/test_comprehensive.sv` 本身写错

输出端口声明成**隐式 wire** (`output wire q`) 却被 `always_ff` 过程赋值 →
slang 报 **19 个 `AssignToNet`**; 过去 `tools/coverage_gen_demo.py` 用 `strict=False`
(`--no-strict`) 跑 → 优雅降级成 partial AST → 测试"通过" = **假绿**。

修成 `output logic` 后实测: `risk analyze` **rc=1 (19 errors) → rc=0**。方向正确。

### 但暴露**依赖链**: 18 failed → **40 failed**

修完 fixture + 把工具脚本默认改严格后, 全量门禁 **40 failed / 3276 passed** ——
**新增 24 个失败**, 主要在 `sim/tests/usage/test_coverage_generate.py`。

**含义 (本次最有价值的发现)**: 那批测试的**期望值是基于"被破坏 fixture 的 partial
分析结果"建立的** —— fixture 一旦修好, 它们断言的旧输出就不再成立。
换句话说: **`--no-strict` 的假绿不只影响"能不能跑", 还固化了错误的期望值**。

### 处置: 回退 (保持可预测状态)

按纪律不在无验证的情况下留下 40 failed → 回退 3 个文件
(`sim/test_comprehensive.sv` / `tools/coverage_gen_demo.py` /
`sim/tests/cli/test_coverage_gen_demo.py`), 回到 iter_211 的 **18 failed** 已知状态
(其中 16 个是可视化, 按方豆指示暂缓)。

## 💡 关键发现 / 关键技术 / 决策

1. **假绿有"记忆"**: flag 掩盖的不只是"报错", 还有**下游测试的期望值**。修 fixture 必须
   **同批更新依赖它的断言**, 否则修得越对, 测得越红。
2. **修改范围的评估**: iter_212 的教训与此前 iter_205 同类 —— **改动前要问"谁依赖了
   这个行为"** (AGENTS §7 决策前评估影响范围), 本次我是"改了再跑门禁"才发现的。
3. **回退也是纪律**: 40 failed 的中间状态不可提交; 回退 + 精确记录依赖链, 比留下一个
   说不清的红状态更有价值。

## 📢 下一步 (专门批次, 一起做)

1. 修 `sim/test_comprehensive.sv` (`output logic`, 10 处);
2. **同批**更新 `sim/tests/usage/test_coverage_generate.py` 等 24 个依赖测试的期望值
   (它们当前断言的是 partial AST 的输出);
3. `tools/coverage_gen_demo.py`: 默认 `strict=True` + `strict=False` 显式报错;
4. 可视化那 16 个 (按指示暂缓)。

## 📎 关联

- 前序: `iter_211_no_strict_all_removed.md` (用法清零, 18 failed 遗留)
