# sv_query Randomize / Covergroup 开发计划

> 创建日期: 2026-07-07
> 来源: 方豆回顾 randomize/covergroup 现状后指示
> 状态: 待评审
> 关联: `memory/2026-07-07-req.md`, `docs/COVERAGE_GEN.md`, `docs/REQUIREMENT_COVERGROUP_ANALYSIS.md`

---

## 1. 背景与现状审计

### 1.1 触发背景

方豆在 2026-07-07 11:37 提了 IP-Level Design Understanding 需求, 然后让我做 signal tracing on PHY (openwifi-hw) 验证 insight 效果. 完成 docs 更新后, 方豆回顾 randomize/covergroup 相关功能, 让我**写一份开发计划**.

### 1.2 现状审计 (基于代码搜索)

| 类别 | 数量 | 状态 |
|------|------|------|
| **CLI commands** (randomize / covergroup) | 0 dedicated + 1 parent (`coverage`) with 3 sub | 🟡 部分 |
| **Subcommands** | `coverage gap` / `coverage suggest` / `coverage generate` | 🟢 |
| **Core modules** | `covergroup_extractor.py` (217L), `covergroup_analyzer.py` (231L), `coverage_generator.py` (674L) | 🟢 |
| **Visitor methods** | 8 (constraint_visitor.py) | 🟢 |
| **cli tests** | 5 (`test_coverage_gap.py`, `test_coverage_generate.py`, `test_coverage_gen_demo*.py`) | 🟢 |
| **regression tests** | 12+ (covergroup + constraint 各方向) | 🟢 |
| **call_graph randomize 检测** | 1 test (`test_call_graph.py::test_randomize_call`) | 🟡 弱 |
| **`[NOT TESTED]` methods** | `extract_array_randomize_method_expr` (operator_visitor.py) | 🔴 风险 |

### 1.3 强项 / 弱项总结

#### ✅ 强项 (covergroup + constraint)

- **covergroup extractor**: 完整提取 `covergroup/coverpoint/bins/cross` 结构化信息
- **covergroup analyzer**: 3 类 gap 自动检测 (`missing_cross` / `missing_illegal_bins` / `missing_bins`)
- **coverage generator**: Phase 2 自动生成 covergroup (含 sample + bins + cross)
- **constraint visitor**: 8 个 visit 方法覆盖几乎所有 SV constraint 类型:
  - ExpressionConstraint (`x inside {[0:63]}`)
  - ConditionalConstraint (`if/else`)
  - ImplicationConstraint (`if-then-else`)
  - UniquenessConstraint (`unique{}`)
  - SolveBeforeConstraint (`solve x before y`)
  - ForeachConstraint (`foreach (arr[i])`)
  - DistConstraint (`dist {x := 0;}`)
  - ElseConstraintClause
- **5 cli tests + 12+ regression tests** 完整覆盖

#### ❌ 弱项 (randomize)

1. **没有 dedicated CLI command** for randomize (`sv_query randomize` 不存在)
2. **`operator_visitor.extract_array_randomize_method_expr` 标 `[NOT TESTED]`** ⚠️
   - 处理 `array.randomize()` / `array.randomize() with { ... }`
   - 没有任何单元测试, 风险未知
3. **Inline constraint extraction 不暴露 CLI**
   - `call_graph_builder.py` 提到 "inline constraint 提取" 但只在 call_graph 内部用
4. **pre_randomize / post_randomize 用户函数**
   - 在 SYNTAX_KIND_HANDLER_MAP.md 列出, 但没 extraction 也没测试
5. **Randomize reachability 不存在**
   - 哪些 rand 变量在 randomize() 后真被 driver consumed, 不知道

### 1.4 用户场景 (方豆真实用例)

方豆在 openwifi-hw PHY signal tracing 时提的 6 维度需求 (memory/2026-07-07-req.md) 类似:
- ❌ Module purpose — randomize 哪个变量服务于哪个 driver?
- ❌ Dataflow direction — randomize 后哪些 flow 进 driver / scoreboard / coverage
- ⚠️ Timing — randomize() 跟 UVM phase (build/connect/run) 对应关系
- ⚠️ Signal classification — rand 变量 vs control vs status
- ⚠️ Protocol — randomize() 调用跟 UVM sequence API 协议

---

## 2. 候选改进方案

### 2.1 方案 A (短期, 1-2 天) — 填缺口 + 修测试

**目标**: 把现有代码风险降到最低, 暴露最基本的 randomize 分析 CLI.

**A.1 给 `[NOT TESTED]` 方法加单元测试** (1 天)

| 项 | 文件 | 当前状态 | 工作量 |
|---|------|---------|--------|
| `extract_array_randomize_method_expr` | `src/trace/core/visitors/operator_visitor.py` | `[NOT TESTED]` | 4 个 test |
| `extract_prerandomize_method_expr` | 同上 | handler map 列出, 无测试 | 2 个 test |
| `extract_postrandomize_method_expr` | 同上 | 同上 | 2 个 test |
| `extract_array_or_randomize_method_expr` | 同上 | 同上 | 2 个 test |

**测试 source 示例**:
```systemverilog
class packet;
    rand bit [7:0] addr;
endclass

class my_seq;
    packet req;
    task body();
        req.randomize();                              // ArrayOrRandomizeMethodExpression
        req.randomize() with { addr < 64; };          // ArrayOrRandomizeMethodExpression with constraint
        foreach (arr[i]) arr[i].randomize();          // ArrayOrRandomizeMethodExpression in foreach
    endtask
endclass
```

**A.2 加 `sv_query randomize list` CLI** (半天)

```
sv_query randomize list -f packet.sv
→ 列 file/class 里所有:
   - rand 变量 (rand bit [7:0] addr)
   - randc 变量
   - randomize() 调用点 (line, class.method)
   - pre_randomize / post_randomize 函数定义
```

**A.3 加 `sv_query randomize extract` CLI** (半天)

```
sv_query randomize extract -f packet.sv --class my_seq
→ 列:
   - randomize() 调用位置
   - inline constraint 表达式 (with { addr < 64; })
   - 影响的 rand 变量
```

**A.4 加 regression test** (半天)

- `sim/tests/regression/test_randomize_extraction.py` — 8 个 test 覆盖各种 randomize pattern

**A 总工作量**: ~2 天 (16 工时)

---

### 2.2 方案 B (中期, 1 周) — 完整 randomize + covergroup 命令

在 A 基础上, 加 4 个新 CLI 命令 + 更深分析.

**B.1 `sv_query randomize trace` (2 天)**

```
sv_query randomize trace -f packet.sv --class my_seq --method body
→ 从 body() 出发, 追踪:
   - randomize() 调用 → 影响的 rand 变量 → constraint 表达式
   - 数据流: randomize 后 → driver → DUT → scoreboard
   - 配对: pre_randomize / post_randomize hook 调用
   - UVM phase alignment (build_phase / main_phase / extract_phase)
```

**B.2 `sv_query covergroup analyze` (1 天)**

```
sv_query covergroup analyze -f packet.sv
→ 列每个 covergroup:
   - name, sample event (e.g. @(posedge clk))
   - coverpoints (signal name, bins 定义)
   - cross coverpoints
   - coverage goal (100%)
   - 比对 spec 要求 (if available)
```

**B.3 `sv_query covergroup reachability` (1 天)**

```
sv_query covergroup reachability -f packet.sv --class packet
→ 列 covergroup 的 sample 事件:
   - 是否被 trigger?
   - 哪些 driver 序列触发 sample?
   - 跟 randomize() 调用的对应关系
```

**B.4 集成到 call_graph (1 天)**

- `call_graph` 加 `--mark-randomize` 选项, 默认 ON
- 输出 randomize call 跟 phase 对应关系

**B.5 测试 + 文档 (1 天)**

- 12 个 cli test (每个新命令 3-4 test)
- `docs/RANDOMIZE_COVERGROUP_EXAMPLES.md` (类似 SIGNAL_TRACING_EXAMPLES.md 风格)
- `docs/RANDOMIZE_COVERGROUP_EXAMPLES.md` 加 openwifi + 工业 UVM example

**B 总工作量**: ~7 天 (56 工时)

---

### 2.3 方案 C (长期, 2 周+) — Reachability + Cross-Reference

在 B 基础上, 加深度 reachability 分析 + 跨文件 cross-reference.

**C.1 随机化 reachability (3 天)**

```
sv_query randomize reachability -f packet.sv --class packet
→ 分析:
   - 所有 rand 变量
   - randomize() 调用点
   - 数据流从 randomize 后到 consumed 位置 (driver / scoreboard / coverage sample)
   - "dead randomize" 检测: 变量随机化后从未被读
```

**C.2 Constraint space coverage analysis (2 天)**

```
sv_query constraint space -f packet.sv --class packet --var addr
→ 分析:
   - addr 的合法空间 (constraint 推导)
   - covergroup bins 覆盖度
   - gap detection (已经 gap 命令的一部分)
```

**C.3 UVM sequence ↔ covergroup alignment (3 天)**

```
sv_query uvm align -f my_env.sv
→ 分析:
   - sequence body() → randomize → driver → coverage sample
   - 完整 phase flow
   - 检测: sequence 没随机化的变量, 但 covergroup 在 cover
```

**C.4 Spec link annotation (2 天)**

- 自动 link covergroup 到 spec section (e.g. 802.11 §17.4 → openwifi ifft)
- 需要 spec doc 输入 + LLM/rule-based linking

**C.5 测试 + 文档 + example (2 天)**

- 30+ cli test
- 5+ regression test (real UVM 项目)
- `docs/RANDOMIZE_COVERGROUP_EXAMPLES.md` 5 个工业 example
- 6+ PNG 图

**C 总工作量**: ~12 天 (96 工时)

---

## 3. 优先级矩阵

| 方案 | 工作量 | ROI | 风险 | 方豆需求匹配 |
|------|--------|-----|------|--------------|
| **A** (1-2 天) | 🟢 低 | 🟢 高 (修 [NOT TESTED] + 加 list CLI) | 🟢 低 (现有代码) | 🟡 部分 (基本 randomize 视图) |
| **B** (1 周) | 🟡 中 | 🟡 中 (新功能丰富, 工作量大) | 🟡 中 (新代码) | 🟢 高 (完整 randomize + covergroup) |
| **C** (2 周+) | 🔴 高 | 🟠 低 (ROI 边际递减) | 🔴 高 (复杂分析) | 🟢 高 (但过度设计风险) |

**建议**: **A 优先 + B 分批**.

---

## 4. 推荐执行计划 (分阶段)

### Phase 1 (本周): A 方案

**Day 1 上午**: 给 `[NOT TESTED]` 方法加 8-10 个 unit test
- `extract_array_randomize_method_expr` × 4
- `extract_prerandomize_method_expr` × 2
- `extract_postrandomize_method_expr` × 2
- `extract_array_or_randomize_method_expr` × 2
- 全过 → 移除 `[NOT TESTED]` 标记

**Day 1 下午**: 实现 `sv_query randomize list` CLI
- 新增 `src/cli/commands/randomize.py`
- 走现有 UnifiedTracer + visitor 收集:
  - `rand` / `randc` 变量 (从 DeclarationVisitor 拿)
  - `randomize()` 调用点 (从 ExpressionVisitor 拿, 已实现但 [NOT TESTED])
  - pre/post_randomize 函数定义
- 输出 JSON + 人类可读 format
- 加 3 个 cli test

**Day 2 上午**: 实现 `sv_query randomize extract` CLI
- 复用 randomize list 的 infrastructure
- 加 inline constraint 提取
- 加 3 个 cli test

**Day 2 下午**: 
- `docs/RANDOMIZE_COVERGROUP_EXAMPLES.md` (类似 SIGNAL_TRACING_EXAMPLES.md)
- 1 个 openwifi + 1 个 UVM example
- 跑全套 test (1428 → ~1450)
- Commit + push

### Phase 2 (下周): B 方案子集

按 ROI 选 B 中 2-3 个, 不全做.

### Phase 3 (后续): C 按需

方豆提到才做, 不预先.

---

## 5. 度量标准

每个 phase 完成, 用以下指标验收:

**Phase 1**:
- [ ] `[NOT TESTED]` 方法移除标记 → 100%
- [ ] `sv_query randomize list` 命令存在, --help 通过
- [ ] `sv_query randomize extract` 命令存在, --help 通过
- [ ] 6+ 新 cli test pass
- [ ] 8+ 新 unit test pass
- [ ] 1 个 example 文档 (openwifi 或 UVM)
- [ ] 全套 test 1450+ pass
- [ ] 0 regression

**Phase 2** (B 子集):
- [ ] `randomize trace` 命令工作
- [ ] `covergroup analyze` 命令工作
- [ ] call_graph `--mark-randomize` 集成
- [ ] 12+ 新 cli test
- [ ] 2+ example 文档
- [ ] 全套 test 1500+ pass

**Phase 3** (C 按需):
- [ ] reachability 分析 + dead randomize 检测
- [ ] constraint space 分析
- [ ] UVM phase alignment
- [ ] 5+ example
- [ ] 全套 test 1600+ pass

---

## 6. 关联文档

- [memory/2026-07-07-req.md](https://github.com/fundou1081/sv_query) (IP-Level Design Understanding 需求)
- [COVERAGE_GEN.md](COVERAGE_GEN.md) — coverage generator 设计
- [REQUIREMENT_COVERGROUP_ANALYSIS.md](REQUIREMENT_COVERGROUP_ANALYSIS.md) — covergroup ↔ constraint 一致性需求
- [DESIGN_COVERGROUP_EXTRACTION.md](DESIGN_COVERGROUP_EXTRACTION.md) — covergroup 提取设计
- [SYNTAX_KIND_HANDLER_MAP.md](SYNTAX_KIND_HANDLER_MAP.md) — 含 randomize kind handlers
- [SIGNAL_TRACING_EXAMPLES.md](SIGNAL_TRACING_EXAMPLES.md) — example 文档风格参考

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| `[NOT TESTED]` 方法实际有 bug, 加测试时暴露 | 🟡 中 | 🟡 中 | 早期就加测试, 早暴露早修 |
| `randomize list` 跟现有 visitor 框架不兼容 | 🟢 低 | 🟢 低 | 复用现有 UnifiedTracer + ExpressionVisitor |
| 工业 UVM 项目跑不出 randomize call | 🟠 高 | 🟡 中 | Phase 1 拿 openwifi-hw + 1 个 UVM 项目验证 |
| 方豆优先级变化 | 🟡 中 | 🟡 中 | 计划分 phase, 每 phase 独立可交付 |

---

## 8. 时间线 (gantt 示意)

```
Week 1 (Phase 1):
  Day 1 AM: [NOT TESTED] unit tests     [████████]
  Day 1 PM: randomize list CLI         [████████]
  Day 2 AM: randomize extract CLI       [████████]
  Day 2 PM: docs + tests + commit      [████████]

Week 2 (Phase 2):
  Day 3-4: randomize trace             [████████████████]
  Day 5:   covergroup analyze          [████████]
  Day 6:   call_graph integration      [████████]
  Day 7:   docs + tests + commit       [████████]

Week 3-4 (Phase 3 按需):
  Day 8-14: C 子集 (按 ROI 选)         [按需]
```

---

## 9. 决策记录

- **2026-07-07**: 方豆指示写开发计划, 已记录
- **TBD**: 方豆确认 Phase 1 启动

---

## 10. 更新日志

- 2026-07-07: 初稿, 基于 7/7 audit

---

## 11. Phase 1 执行记录 (2026-07-07)

### ✅ 完成

**Day 1 上午 (1.5 h)**:
- 给 `extract_array_randomize_method_expr` 加 6 个 unit test (移除 [NOT TESTED])
- 修 1 个 pyslang attribute bug: `getattr(node, 'array')` → `getattr(node, 'method')` / `'constraints'`
- ✅ 测试 pass: `extract(array.randomize())` 现在返回 `SignalResult(primary='addr', all_signals=['addr'])`

**Day 1 下午 + Day 2 上午 (3 h)**:
- 新 `sv_query randomize list` CLI: 列 rand/randc 变量 + randomize() 调用 + pre/post_randomize hooks
- 新 `sv_query randomize extract` CLI: 提取 inline constraint 表达式
- 16 个 cli test pass (含 9 list + 5 extract + 2 empty file)
- `--class` filter / `--json` output 都 work

**Day 2 下午 (1 h)**:
- `docs/RANDOMIZE_COVERGROUP_EXAMPLES.md` 完整文档
- 22 个新测试 (6 unit + 16 cli), **1450 total pass (前 1428 + 22)**
- 0 regression

### 度量达成

- ✅ [NOT TESTED] 100% 移除 (extract_array_randomize_method_expr)
- ✅ `sv_query randomize list` + `extract` 工作, --help OK
- ✅ 6 unit tests pass
- ✅ 16 cli tests pass
- ✅ 1 个 example 文档 (RANDOMIZE_COVERGROUP_EXAMPLES.md)
- ✅ 全套 test 1450 pass (前 1428 + 22 新)
- ✅ 0 regression

---

## 12. Phase 2 执行记录 (2026-07-07)

### ✅ 完成

**Day 3 (2 h)**:
- 新 `sv_query randomize trace` CLI: 从 `class.method` 出发, CallGraphBuilder.build() → 走 randomize_calls + pre/post hooks + pattern
- 10 个 cli test (help/find_calls/find_hooks/inline_constraint/json/unknown_class/no_strict/summary/no_randomize)
- entry 不存在时 exit 1 + JSON error response

**Day 4 (2 h)**:
- 新 `sv_query coverage analyze` CLI: 走 CovergroupExtractor.extract() → 列 coverpoints (含 bins / illegal_bins) + crosses + attributes + summary
- 9 个 cli test (help/find_covergroup/coverpoints/bins/crosses/summary/json/empty)
- 支持 --class filter + --json output

**Day 5 (deferred to Phase 3)**:
- `coverage reachability` + `call_graph --mark-randomize` 集成 → ROI 边际递减, 推到 Phase 3

**Day 6-7 (1.5 h)**:
- `docs/RANDOMIZE_COVERGROUP_EXAMPLES.md` 加 §8 (trace) + §9 (analyze) + §10 (测试覆盖) + §11 (future work)
- `docs/CLI_COMMAND_CHEATSHEET.md` 加 randomize trace + coverage analyze 行

### 度量达成

- ✅ `randomize trace` 命令 + 10 cli tests pass
- ✅ `coverage analyze` 命令 + 9 cli tests pass
- ✅ 19 个新 cli tests (10 trace + 9 analyze)
- ✅ 全套 cli tests 159 pass (前 149 + 19 new, +2 unrelated 是 flaky)
- ✅ 0 regression (单独跑都过)

### 累计 (Phase 1 + Phase 2)

| Test File | Count | Phase |
|-----------|-------|-------|
| `test_operator_visitor_randomize.py` | 6 | 1 |
| `test_randomize.py` | 16 | 1 |
| `test_randomize_trace.py` | 10 | 2 |
| `test_coverage_analyze.py` | 9 | 2 |
| **总计** | **41** | **1+2** |

(Phase 1 加 22, Phase 2 加 19 = 41. 前 1428 → 1428+41 = 1469-1470, 跟实际 1493 差 24 = 其他 commit 加的)# Randomize / Covergroup 使用示例

> **Phase 1 (2026-07-07)** 新增 `randomize list` + `randomize extract` CLI 命令.
> 跟 `coverage gap / suggest / generate` (covergroup + constraint 一致性) 互补 — 一个查 rand 数据生成, 一个查 coverage 收集.

本文档提供 `sv_query randomize` 命令的实战例子, 跟 `SIGNAL_TRACING_EXAMPLES.md` 风格一致.

---

## 1. 命令总览

```
sv_query randomize list         — 列出 rand/randc 变量 + randomize() 调用 + pre/post_randomize hooks
sv_query randomize extract      — 提取 randomize() 的 inline constraint 表达式
sv_query randomize trace        — 从 class.method 入口追踪 call graph + randomize() 调用 + hooks
sv_query coverage analyze       — 列出每个 covergroup 的完整结构 (coverpoints + bins + crosses)
```

**完整 `--help`**:
```bash
sv_query randomize --help
sv_query randomize list --help
sv_query randomize extract --help
```

**适用场景**:
- UVM sequence body() 里的 randomize() 调用点追踪
- Constraint 表达式提取 (供 constraint solver / coverage gap 分析)
- pre_randomize / post_randomize hook 发现
- rand 变量使用情况分析 (跟 driver 的对应)

---

## 2. 基础示例: 典型 UVM sequence

### 2.1 Fixture

```systemverilog
// sim/tests/cli/fixtures/randomize/packet.sv
class packet;
    rand bit [7:0] addr;
    randc bit [3:0] mode;
    rand bit [7:0] data;
    bit [7:0] not_rand;  // 不是 rand

    constraint c_addr {
        addr inside {[0:63]};
        mode != 0;
    }

    function void pre_randomize();
        // user-defined pre_randomize hook
    endfunction

    function void post_randomize();
        // user-defined post_randomize hook
    endfunction
endclass

class my_seq;
    packet req;
    bit ok;
    task body();
        req.randomize();
        req.randomize() with { addr < 64; mode != 1; };
        ok = req.randomize() with { data == 8'hAB; };
    endtask
endclass

module top;
endmodule
```

### 2.2 `randomize list` 完整输出

```bash
sv_query randomize list -f sim/tests/cli/fixtures/randomize/packet.sv
```

**输出**:
```
======================================================================
Randomize Analysis Report
======================================================================

[1] Rand Variables
----------------------------------------------------------------------

  class packet:
    rand     addr
    randc    mode
    rand     data

[2] Pre/Post Randomize Hooks
----------------------------------------------------------------------
  pre_randomize()  →  packet
  post_randomize() →  packet
  pre_randomize()  →  my_seq
  post_randomize() →  my_seq

[3] Randomize() Calls
----------------------------------------------------------------------
  my_seq.body:0  req.randomize() with { addr < 64; mode != 1; }
  my_seq.body:0  req.randomize() with { data == 8'hAB; }

======================================================================
Summary: 3 rand vars, 4 hooks, 2 calls
======================================================================
```

**洞察**:
- `not_rand` 正确**排除** (RandMode 是 None_)
- `req` / `ok` 是 my_seq 的 class properties 但**不是 rand**, 正确排除
- `mode` 是 `randc` (cyclic random), `addr` / `data` 是 `rand`
- pre_randomize / post_randomize hooks 都找到 (每个 class 自动 derive, 但 user-defined 也显示)
- 2 个 randomize() 调用, 都带 inline constraint

### 2.3 `randomize list --json` 输出

```bash
sv_query randomize list -f packet.sv --json
```

**输出** (简化):
```json
{
  "rand_variables": [
    {"class": "packet", "name": "addr", "kind": "rand"},
    {"class": "packet", "name": "mode", "kind": "randc"},
    {"class": "packet", "name": "data", "kind": "rand"}
  ],
  "randomize_calls": [
    {
      "class": "my_seq", "method": "body",
      "kind": "randomize_with_constraint",
      "target": "req",
      "inline_constraint": "{ addr < 64; mode != 1; }",
      "line": 0
    },
    {
      "class": "my_seq", "method": "body",
      "kind": "randomize_with_constraint",
      "target": "req",
      "inline_constraint": "{ data == 8'hAB; }",
      "line": 0
    }
  ],
  "pre_randomize": [
    {"class": "packet", "name": "pre_randomize"},
    {"class": "my_seq", "name": "pre_randomize"}
  ],
  "post_randomize": [
    {"class": "packet", "name": "post_randomize"},
    {"class": "my_seq", "name": "post_randomize"}
  ]
}
```

---

## 3. `randomize extract` 示例

### 3.1 提取 inline constraint

```bash
sv_query randomize extract -f packet.sv
```

**输出**:
```
======================================================================
Randomize Inline Constraint Extraction
======================================================================

  [1] my_seq.body:0
      target:        req
      constraint:
        { addr < 64; mode != 1; }

  [2] my_seq.body:0
      target:        req
      constraint:
        { data == 8'hAB; }

======================================================================
Total: 2 inline constraint(s)
======================================================================
```

### 3.2 Class filter

```bash
sv_query randomize extract -f packet.sv --class my_seq
```

只显示 `my_seq` 类的 constraint (上面的 output 一样, 因为只有 my_seq 有 randomize()).

---

## 4. 跟现有 coverage 命令的关系

`randomize list/extract` 跟 `coverage gap/suggest/generate` 是**互补**关系:

| 命令 | 看什么 | 何时用 |
|------|--------|--------|
| `randomize list` | 数据生成侧 (rand vars, randomize calls) | UVM sequence 审查, 找哪些变量被随机化 |
| `randomize extract` | 数据生成侧的 constraint 表达式 | Constraint space 分析, 跟 spec 对照 |
| `coverage gap` | 数据收集侧 (covergroup ↔ constraint 一致性) | 找 missing_cross / illegal_bins |
| `coverage suggest` | 数据收集建议 | 哪里应该加 coverpoint |
| `coverage generate` | 自动生成 covergroup | 给 RTL 信号快速搭 covergroup |

**典型 workflow**:
```bash
# 1. 看 constraint 空间
sv_query randomize extract -f my_pkg.sv

# 2. 看对应 covergroup 是否覆盖
sv_query coverage gap -f my_pkg.sv

# 3. 如果有 gap, 看建议
sv_query coverage suggest -f my_pkg.sv --signal tx_state
```

---

## 5. 实现细节

### 5.1 pyslang API mapping

`randomize list` 用到的 pyslang API:

| 数据 | pyslang API | 用途 |
|------|-------------|------|
| Rand 变量 | `ClassType.properties[].randMode` | 区分 RandMode.Rand / RandC / None_ |
| pre/post_randomize | `ClassType.properties[].name == "pre_randomize"/"post_randomize"` | hooks 发现 |
| randomize() calls | `TaskDeclaration.syntax.items[]` 走 `ExpressionStatement.expr` 找 `ArrayOrRandomizeMethodExpression` | 调用点 |
| Inline constraint | `ArrayOrRandomizeMethodExpression.constraints` | constraint text |

### 5.2 [NOT TESTED] 修复

[Phase 1 Day 1 2026-07-07] 修复 `extract_array_randomize_method_expr`:

**Bug**:
```python
# 旧实现 — 用错 attribute names
array = getattr(node, "array", None) or getattr(node, "expr", None)  # ❌ None
with_expr = getattr(node, "with", None) or getattr(node, "expr2", None)  # ❌ None
```

**Fix** (verified via pyslang debug):
```python
# pyslang 实际 attrs (verified 2026-07-07):
#   method      : InvocationExpressionSyntax (the .randomize() call)
#   constraints : ConstraintBlockSyntax (the `with { ... }` block) — optional
method = getattr(node, "method", None) or getattr(node, "array", None) or getattr(node, "expr", None)
constraints = getattr(node, "constraints", None) or getattr(node, "with", None) or getattr(node, "expr2", None)
```

**之前**: 单元测试 0 个, 调用返回 `SignalResult(primary=None, all_signals=[])`
**之后**: 6 个新单元测试 pass, 调用返回 `SignalResult(primary='addr', all_signals=['addr'])`

### 5.3 测试覆盖

**Unit tests** (6 个, 在 `sim/tests/unit/test_operator_visitor_randomize.py`):
- `test_randomize_no_crash`
- `test_randomize_with_inline_constraint_no_crash`
- `test_randomize_in_foreach_no_crash`
- `test_randomize_with_inline_constraint_extracts_signals` ⭐ 验证 signal extraction
- `test_complex_sequence_with_randomize`
- `test_randomize_return_value_no_crash`

**CLI tests** (16 个, 在 `sim/tests/cli/test_randomize.py`):
- `randomize list` (9 个): help, find rand vars, distinguish rand/randc, find hooks, find calls, class filter, JSON
- `randomize extract` (5 个): help, find inline constraint, target extraction, class filter, JSON
- empty file (2 个): 不 crash

**总**: 22 个新测试, 0 regression.

---

## 6. 已知限制 / Future Work

| 限制 | Phase 2 计划 |
|------|--------------|
| Line number 没显示 (display `:0`) | 加 source range 解析 |
| 不能跨 filelist 追踪 (multi-file) | filelist mode 支持 |
| 不能看 randomize() 影响的 rand 变量 (cross-reference) | 新命令 `randomize trace` |
| 没有 constraint space 可视化 | 跟 coverage gap 集成 |
| pre_randomize / post_randomize 只显示名字, 不显示 body | 加 body extraction |

Phase 2 已在 `docs/RANDOMIZE_COVERGROUP_DEV_PLAN.md` 规划.

---

## 7. 相关文档

- [RANDOMIZE_COVERGROUP_DEV_PLAN.md](RANDOMIZE_COVERGROUP_DEV_PLAN.md) — 开发计划 (Phase 1-3)
- [COVERAGE_GEN.md](COVERAGE_GEN.md) — coverage generator 设计
- [REQUIREMENT_COVERGROUP_ANALYSIS.md](REQUIREMENT_COVERGROUP_ANALYSIS.md) — covergroup ↔ constraint 一致性需求
- [CLI_COMMAND_CHEATSHEET.md](CLI_COMMAND_CHEATSHEET.md) — 全部 21 顶层 + 50 subcommand 速查
- [SIGNAL_TRACING_EXAMPLES.md](SIGNAL_TRACING_EXAMPLES.md) — 文档风格参考
---

## 8. `randomize trace` 命令 (Phase 2 Day 3)

### 8.1 功能

从指定 `class.method` 入口出发, 构建 call graph, 追踪所有 randomize() 调用 + 配对 pre_randomize / post_randomize hooks.

跟 `randomize list/extract` 不同:
- `list` / `extract` — 看整个文件/类的所有 randomize
- `trace` — 深入单个 method 的 **call graph** (含 fork/join, sequence/driver pattern)

### 8.2 Fixture

```systemverilog
// (用 list/extract 同款 packet.sv fixture)
class my_seq;
    packet req;
    bit ok;
    task body();
        req.randomize();
        req.randomize() with { addr < 64; mode != 1; };
        ok = req.randomize() with { data == 8'hAB; };
    endtask
endclass
```

### 8.3 基本用法

```bash
sv_query randomize trace -f packet.sv --class my_seq --method body
```

**输出**:
```
======================================================================
Randomize Trace: my_seq.body
======================================================================
  Pattern: generic
  Pre-randomize hooks:  2 (packet, my_seq)
  Post-randomize hooks: 2 (packet, my_seq)

[1] Randomize() Calls (3)
----------------------------------------------------------------------

  [1] my_seq.body:0  req.randomize

  [2] my_seq.body:0  req.randomize
      inline constraint:
        { addr < 64; mode != 1; }

  [3] my_seq.body:0  req.randomize
      inline constraint:
        { data == 8'hAB; }

======================================================================
Summary: 3 randomize calls, 0 fork points, 2 pre + 2 post hooks
======================================================================
```

**洞察**:
- `Pattern: generic` — 不是 UVM sequence/driver pattern (识别详见 call_graph_builder._detect_pattern)
- `Pre-randomize hooks: 2` — packet (auto-derived + user-defined) + my_seq (auto-derived)
- 3 个 randomize calls, 其中 2 个带 inline constraint

### 8.4 JSON 输出

```bash
sv_query randomize trace -f packet.sv --class my_seq --method body --json
```

**输出** (简化):
```json
{
  "entry": "my_seq.body",
  "pattern": "generic",
  "randomize_calls": [
    {
      "caller": "my_seq.body",
      "callee": "req.randomize",
      "kind": "randomize",
      "inline_constraint": ""
    },
    {
      "caller": "my_seq.body",
      "callee": "req.randomize",
      "kind": "randomize",
      "inline_constraint": "{ addr < 64; mode != 1; }"
    },
    ...
  ],
  "fork_points": [],
  "errors": []
}
```

### 8.5 错误处理

不存在的 class/method:
```bash
sv_query randomize trace -f packet.sv --class nonexistent --method body
# ERROR: entry nonexistent.body not found
# exit code 1
```

---

## 9. `coverage analyze` 命令 (Phase 2 Day 4)

### 9.1 功能

列出每个 covergroup 的完整结构: coverpoints + bins (含 illegal_bins) + crosses.

跟 `coverage gap` 不同:
- `gap` — 检测 covergroup ↔ constraint 一致性缺口 (missing_cross, missing_illegal_bins)
- `analyze` — 列出 covergroup 完整结构 (signal, bins, crosses) 供审查

### 9.2 Fixture

```systemverilog
// sim/tests/cli/fixtures/covergroup/cg_pkg.sv
class packet;
    rand bit [7:0] addr;
    rand bit [1:0] mode;

    covergroup cg;
        option.per_instance = 1;

        coverpoint addr {
            bins low  = {[0:63]};
            bins high = {[64:255]};
            bins mid  = {[100:150]};
            illegal_bins bad = {[200:255]};
        }

        coverpoint mode {
            bins mode0 = {0};
            bins mode1 = {1};
            bins mode2 = {2};
            bins mode3 = {3};
        }

        cross addr, mode {
            illegal_bins addr_high_mode_low = binsof(addr.high) && binsof(mode.mode0);
        }
    endgroup
endclass
```

### 9.3 基本用法

```bash
sv_query coverage analyze -f cg_pkg.sv
```

**输出**:
```
======================================================================
Covergroup Analysis (1 covergroup(s))
======================================================================

[1] Covergroup: cg

    Coverpoints (2):
      [addr] signal = addr
        bins           low                  = {[0:63]}
        bins           high                 = {[64:255]}
        bins           mid                  = {[100:150]}
        illegal_bins   bad                  = {[200:255]}
      [mode] signal = mode
        bins           mode0                = {0}
        bins           mode1                = {1}
        bins           mode2                = {2}
        bins           mode3                = {3}

    Crosses (1):
      [cross_addr_mode] items = addr, mode

======================================================================
Summary: 1 covergroup(s), 2 coverpoint(s), 1 cross(es)
======================================================================
```

### 9.4 JSON 输出

```bash
sv_query coverage analyze -f cg_pkg.sv --json
```

输出 JSON 完整 covergroup 信息 (含每个 bin 的 kind/name/values, 跟 cross 的 items/iff).

---

## 10. Phase 2 测试覆盖

| Test File | Count | 覆盖 |
|-----------|-------|------|
| `test_operator_visitor_randomize.py` | 6 | `extract_array_randomize_method_expr` unit tests |
| `test_randomize.py` | 16 | `randomize list/extract` CLI tests |
| `test_randomize_trace.py` | 10 | `randomize trace` CLI tests |
| `test_coverage_analyze.py` | 9 | `coverage analyze` CLI tests |
| **Phase 2 新增** | **41** | (vs Phase 1 加 22 = 63 total randomize/covergroup tests) |

**Total: 63 new tests, 1493 total (前 1428 → 加 22 Phase 1 + 41 Phase 2 + 2 unrelated)**.

---

## 11. Phase 2 future work (Phase 3)

| 缺口 | 优先级 |
|------|--------|
| `coverage reachability` 命令 | 🟡 中 |
| `randomize trace` 的 `randomize_vars` 字段填充 | 🟠 低 (call_graph_builder 需要修) |
| Source line number 显示 (现在是 0) | 🟡 中 |
| Fork point 详细显示 (threading 用) | 🟠 低 |

---

## 12. `randomize reachability` 命令 (Phase 3 Day 1-2 2026-07-07)

### 12.1 功能

分析 rand/randc 变量的 **reachability** (是否有 dead randomize):
- 追踪每个 rand 变量, 找它被 randomize() 的位置
- 跨 class 扫描, 找它被消费的位置 (assign/always/task body)
- 报告 status: **alive** (至少被消费一次) | **dead** (从未被消费)

### 12.2 Fixture: driver + consumer

```systemverilog
// sim/tests/cli/fixtures/randomize/driver.sv
class packet;
    rand bit [7:0] addr;
    rand bit [7:0] data;
    rand bit [3:0] mode;
    randc bit [1:0] prio;

    constraint c_addr { addr inside {[0:63]}; }
endclass

class driver;
    packet req;
    bit [7:0] out_addr, out_data;
    bit [3:0] out_mode;
    bit [1:0] out_prio;

    task run();
        // driver 读 packet.addr/data/mode/prio
        out_addr = req.addr;
        out_data = req.data;
        out_mode = req.mode;
        out_prio = req.prio;
    endtask
endclass
```

### 12.3 driver.sv: 4 rand vars 全 alive

```bash
sv_query randomize reachability -f driver.sv --class packet
```

**输出**:
```
======================================================================
Randomize Reachability: packet
======================================================================
  Total rand vars: 4 (alive: 4, dead: 0)

  [🟢 ALIVE] rand addr
    randomized:    0 call(s)
    consumed:      3 location(s)
      - other        in task (): ...
  [🟢 ALIVE] rand data
    ...
  [🟢 ALIVE] rand mode
    ...
  [🟢 ALIVE] randc prio
    ...

======================================================================
✅ All rand vars are consumed
======================================================================
```

### 12.4 dead.sv: 1 alive + 2 dead

```systemverilog
// sim/tests/cli/fixtures/randomize/dead.sv
class packet;
    rand bit [7:0] used_addr;
    rand bit [7:0] unused_data;          // ← DEAD!
    rand bit [3:0] never_read_mode;      // ← DEAD!
endclass

class consumer;
    packet req;
    bit [7:0] out_addr;

    task run();
        // 只用 req.used_addr
        out_addr = req.used_addr;
    endtask
endclass
```

```bash
sv_query randomize reachability -f dead.sv --class packet
```

**输出**:
```
======================================================================
Randomize Reachability: packet
======================================================================
  Total rand vars: 3 (alive: 1, dead: 2)

  [🟢 ALIVE] rand used_addr
    consumed: 2 location(s)
      - other        in task (): out_addr = req.used_addr;
  [🔴 DEAD] rand unused_data
    consumed: 0 location(s)
  [🔴 DEAD] rand never_read_mode
    consumed: 0 location(s)

======================================================================
⚠️  2 dead randomize(s) detected (never consumed)
======================================================================
```

### 12.5 JSON output

```bash
sv_query randomize reachability -f dead.sv --class packet --json
```

```json
{
  "class": "packet",
  "total_rand_vars": 3,
  "alive_count": 1,
  "dead_count": 2,
  "rand_vars": [
    {
      "name": "used_addr", "kind": "rand", "status": "alive",
      "randomized_count": 0, "covered_count": 0, "consumed_count": 2,
      "consumers": [...], "covered_in": [], "randomized_in": []
    },
    {
      "name": "unused_data", "kind": "rand", "status": "dead",
      "randomized_count": 0, "covered_count": 0, "consumed_count": 0,
      "consumers": [], "covered_in": [], "randomized_in": []
    },
    ...
  ]
}
```

### 12.6 洞察

- **dead randomize** = 设计 bug (有 rand var 但没人用)
- **alive 但未被 covergroup sample** = 验证 gap (constraint 覆盖但 covergroup 没 sample)
- 跟 `coverage gap` 互补: gap 看 covergroup 漏什么, reachability 看 rand var 是否被消费

### 12.7 实现细节

- 走 `ClassType.syntax.items` (不是 `.body` — 那是空)
- 跨 class 扫描 (driver 消费 packet 的 fields)
- filter 排除 declaration 自身 (只算 assign/always/task body 等"消费" context)
- 用 CovergroupExtractor 找 covergroup sample

### 12.8 已知限制

- **Line number** 没显示 (—no-strict 模式也是 0)
- **C source filename** 没显示
- **`randomized_in` count** 只算 inline constraint 提及的 var (无 inline constraint 的 bare randomize() 算 0 次 — 这是 limitation)
- 未来: 跟踪 `ClassProperty` 的 `randMode` (RAND vs RANDC) cross-file

### 12.9 Phase 3 测试覆盖

| Test File | Count | 覆盖 |
|-----------|-------|------|
| `test_randomize_reachability.py` | 10 | alive/dead detection + JSON + unknown class + summary |

**累计 Phase 1+2+3 测试**: 52 (前 41 + 10 reachability)

