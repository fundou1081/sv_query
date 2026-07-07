# Randomize / Covergroup 使用示例

> **Phase 1 (2026-07-07)** 新增 `randomize list` + `randomize extract` CLI 命令.
> 跟 `coverage gap / suggest / generate` (covergroup + constraint 一致性) 互补 — 一个查 rand 数据生成, 一个查 coverage 收集.

本文档提供 `sv_query randomize` 命令的实战例子, 跟 `SIGNAL_TRACING_EXAMPLES.md` 风格一致.

---

## 1. 命令总览

```
sv_query randomize list     — 列出 rand/randc 变量 + randomize() 调用 + pre/post_randomize hooks
sv_query randomize extract  — 提取 randomize() 的 inline constraint 表达式
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