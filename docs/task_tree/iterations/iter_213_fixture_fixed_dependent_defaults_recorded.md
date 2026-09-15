# Iteration 213: fixture 修好 (28 passed) + 发现"降级默认值"是下一桶

**Metadata**:
- **Iteration #**: 213
- **Task Tree Level**: L1 (纪律收口)
- **Parent Task**: iter_212 登记的专门批次 (方豆: 可以, 做吧)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ fixture 层完成 (2 文件 28 passed) / ⚠️ 默认值层记录待办

## 🎯 本次目标

iter_212 登记的批次: ① 修 `sim/test_comprehensive.sv`; ② 更新依赖测试期望值;
③ tools 脚本严格默认。

## 🔬 实际结果

### ① ② 完成: fixture 修复 + 测试改写 → **28 passed**

- `sim/test_comprehensive.sv`: `output wire q` → **`output logic q`** (10 处) →
  `risk analyze` rc=1 (19 个 `AssignToNet`) → **rc=0**;
- `test_coverage_gen_demo.py::TestNoStrictFlag` → **`TestStrictModeFixture`**:
  正向断言"严格模式下必须编译通过并生成 covergroup" (原测试依赖被禁行为);
- 实测: `test_coverage_gen_demo.py` + `test_coverage_generate.py` = **28 passed**。

**关键澄清 (修正 iter_212 的判断)**: iter_212 里"24 个新失败"**不是** fixture 引起的 ——
只有 `test_coverage_gen_demo.py` 引用该 fixture; 那 24 个来自**工具脚本/CLI 的默认值改动**。

### ③ 工具默认值: 发现更深的一桶 (**未完成**, 已回退并记录)

把 `tools/coverage_gen_demo.py` 改成"默认 strict + `strict=False` 显式报错"后,
`sim/tests/usage/test_coverage_generate.py` **15 failed / 4 passed**。

诊断链:
1. 失败信息是 `ERROR: strict=False ... 已被 AGENTS 纪律 1 禁用` —— 该文本只存在于
   `tools/coverage_gen_demo.py:151` → 说明 **`sv_query coverage generate` 会走到该脚本**;
2. `src/cli/commands/coverage.py:232`: `coverage generate` 的 CLI 默认就是
   **`strict: bool = typer.Option(False, ...)`** ("default: --no-strict, 适合工业多文件项目")
   → **降级默认值在 CLI 层**;
3. 那 15 个测试的 fixture 在严格模式下有 elaboration 错误, 所以过去靠默认降级"通过"。

→ 这是**同一类问题的第二形态**: iter_211 清的是"**用法**"(`--no-strict` 字符串),
但 **默认值/参数语义**里还藏着降级 (iter_212 的 `strict=False` 空转参数 + 本次的 CLI 默认 False)。
按纪律回退工具脚本改动 (只保留已验证的 ①②), 记录为下一桶。

## 💡 关键发现 / 关键技术 / 决策

1. **违规有三种形态**: (a) 命令行**用法** (`--no-strict` 字符串) — iter_211 已清零;
   (b) **默认值** (`strict=False` 作 API/CLI 默认) — 本轮发现; (c) **空转参数**
   (flag 被删但参数还在, 行为与调用方预期脱节) — iter_212 发现。要按形态逐一清理。
2. **分层修改 + 分层验证**: 本轮把"fixture 层"与"默认值层"分开处理 —— 前者已验证落地
   (28 passed), 后者牵动 15 个测试的 fixture, 需要独立批次。
3. **一次改多处 → 归因困难**: iter_212 我同时改 fixture/工具/测试, 导致误判"24 个失败是
   fixture 引起"。本轮**先隔离变量** (只改 fixture + 测试) 才把归因做对。

## 📢 下一桶 (待方豆拍板)

| 项 | 内容 |
|---|---|
| 默认值层 | `src/cli/commands/coverage.py:232` 的 `strict=False` 默认 + `tools/coverage_gen_demo.py` 的 `strict=False` 默认 → 改 `True`, 并让 `strict=False` 显式报错 |
| 依赖测试 | `sim/tests/usage/test_coverage_generate.py` 15 个 (其 fixture 在严格模式下有错误) → 修 fixture |
| 其余 | 可视化 16 个 (按指示暂缓); 其它命令的 `strict` 默认值也需扫一遍 (`grep "Option(False, \"--strict/--no-strict\""`) |

## 📎 关联

- 修复: `sim/test_comprehensive.sv`、`sim/tests/cli/test_coverage_gen_demo.py`
- 前序: `iter_212_fixture_fix_attempt_reverted.md`
- 下一步线索: `src/cli/commands/coverage.py:232`
