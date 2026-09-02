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

## B 组诊断 (iter_082) — 14 个失败分类

| 文件 | 失败 | 根因 | 处置 |
|---|---|---|---|
| test_benchmark_picorv32 | 1 | baseline 断言过时 (nodes 400-700, 实际 708, GAP-3 后) | ✅ 修断言 600-800 |
| test_benchmark_regression | 1 | variant 值基于旧 baseline 527 (10% drop 变 -33%) | ✅ 修 variant (637/354) |
| test_human_output | 5 | **sandbox cache 不可写** (~/.svq/cache, HOME 限制) | 🟡 环境问题, 可写 HOME 下 10 passed |
| test_tree_output | 5 | 同上 (cache 不可写) | 🟡 环境问题, 可写 HOME 下全绿 |
| test_real_project_viz | 2 | ~~同上 (cache 不可写)~~ → **❌ iter_082 误分类, 实为真实失败** (iter_086) | 见下 |

**iter_082 结论 (已被 iter_086 部分推翻)**: 14 个失败 = 2 个真实过时断言 (已修) + 12 个
sandbox 环境 artifact — **其中 real_project_viz 2 个是误分类**: iter_082 用
`HOME=/tmp/svq_home` 验证时 `~/my_dv_proj/...` 展开到不存在路径 → 这 2 个测试被动态
`pytest.skip('not found')` 跳过, "0 failed" 没包含它们。

## B 组复查 (iter_086) — real_project_viz 2 个真实失败

| 项目 | 根因 | 处置 |
|---|---|---|
| darkriscv | 断言过时: `--dot` 自 V100 起写 **SVG**, 断言还查 `'digraph'` (DOT 时代残留); CLI 本身 strict 模式可过 | ✅ 断言改 SVG 校验 + 删测试内 --no-strict |
| picorv32 | **真实管线 bug**: ELK JSON edge 引用 `port_picorv32_axi_dot_mem_axi_bvalid` 但从未 emit。根因: expr_tree key 模块级路径 vs viz 端口嵌套路径不一致 + edge 侧/emit 侧 SignalRef fallback 规则不一致 | ✅ **已修** (iter_106: _resolve_emitted_port_id 已 emit 优先 + 最终兜底补发; integration 全绿) |

**当前基线** (2026-09-02 iter_106 后): integration = **419 passed + 3 skipped, 0 failed**

## C 组完成 (iter_082/083) — 扩 truth 层

| 文件 | 测试 | 1:1 锁定的语义 |
|---|---|---|
| test_generate_for_chain_truth.py | 6 | 3 级 generate-for 链 (N=4): 索引节点精确存在 (buf1[0..3]/buf2[0..2]/buf3[0..2]) + 链边 (data→buf1[0], stage 间 buf1→buf2[i], buf2→buf3[i], buf3→chain_out) + prod 驱动各 stage + genvar 非信号 |
| test_cross_module_truth.py | 4 | minimal_3module 跨模块端口连接: 实例节点 (sa1/lp1/la1) + 端口映射边 (clk→lp1.clk, data_i→la1.a, valid_i→lp1.data_i) + 叶子输出回流 (lp1.data_o→leaf_ready, la1.sum→sum_o) + 未实例化模块隔离 |

**顺带修复** (发现于 C 组全量跑):
- test_spec_unsupported_syntax::test_replication_lhs_is_sv_illegal — 引用
  /tmp 幽灵文件 (从未创建) + 断言消息错误 (pyslang 实测 ExpressionNotAssignable,
  非 "expression is not allowed as a statement") → 补 fixture probe_repl_lhs.sv +
  修正断言。truth 层 28 passed (原 27 + 1 修复)。
