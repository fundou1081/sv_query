# L2 测试资产补强 — A/B/C 三阶段 (方豆 "先记录 A B C, 我们逐个做")

> **创建**: 2026-09-01 GMT+8
> **背景**: 方豆 "感觉有测试用例太少了, 完整的回归测试包含什么" → 差距分析 (iter_080):
> 测试总量 2997 不少, 但有三类真实缺口。方豆拍板 "先记录 A B C, 我们逐个做"。
> **父任务**: 测试资产梳理 (TEST_MAP §0 完整回归构成)

---

## 差距分析结论 (iter_080)

| # | 缺口 | 现状 | 方向 |
|---|---|---|---|
| A | **16 种主路径语法无独立 regression 文件** | assign/always_comb/顶层 wire/net decl 等约一半语法靠 integration 顺带测, 无独立行为断言文件 (对比: constraint 7 文件 148 测试) | 补独立 regression 行为断言 |
| B | **integration 14 个 pre-existing 失败** | benchmark_picorv32 / benchmark_regression / human_output(4) / tree_output(5) / real_project_viz(2) / bitselect_diff(已修) | 逐个诊断修复 |
| C | **truth 层仅 22 测试** | 只有 case27 SVG 断言 + d1 generate + spec unsupported | 扩 1:1 金标准 |

---

## A: 补主路径语法独立 regression (待做)

**目标**: 33 语法矩阵中"主路径全覆盖但无独立文件"的语法, 各建独立 regression
行为断言文件 (对齐 constraint/covergroup/sva 的密度: DRIVER/CONSTRAINS 边断言 + 有效性)。

**范围** (从 EXTRACTION_COVERAGE 完整支持 18 种中挑无独立文件的):
- `assign` (continuous)
- `always_comb` (含阻塞/非阻塞)
- `wire x = expr;` (顶层 / generate-for 内)
- `{a,b}` 拼接赋值 (RHS / LHS)
- `alias b = a;`
- 三元 `?:` (限 5 层边界)
- `parameter`/`localparam` 过滤
- `genvar + for` (generate-for)

**判定**: 每个文件 ≥3 测试 (正例边断言 + 反例 + 有效性 revert)。

## B: 修 integration 14 个 pre-existing 失败 (待做)

**清单** (2026-09-01 实测):
| 文件 | 失败数 | 疑似原因 |
|---|---|---|
| test_benchmark_picorv32.py | 1 | baseline L2 值 (需核对) |
| test_benchmark_regression.py | 1 | node drop 阈值 (需核对) |
| test_human_output.py | 4 | human 模式输出断言 (需核对) |
| test_tree_output.py | 5 | tree 模式输出断言 (需核对) |
| test_real_project_viz.py | 2 | darkriscv/picorv32 SVG (需核对) |

**判定**: 逐个诊断根因 (fixture/功能/断言), 按 AGENTS.md 归因顺序, 修完 integration 全绿。

## C: 扩 truth 层 1:1 金标准 (待做)

**目标**: 更多模块的 1:1 truth (case27 之外), 如 generate 复杂场景 / 跨模块 / class。
**判定**: 新增 truth 文件 + 断言, truth 全绿。

---

## 状态日志

- **2026-09-01** — 创建任务文件, 记录 A/B/C (方豆 "先记录 A B C, 我们逐个做")
