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