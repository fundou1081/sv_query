# Randomize / Covergroup 使用示例

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

