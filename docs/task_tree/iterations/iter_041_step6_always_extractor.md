# Iteration 041: #1 Step 6 — 拆 always_extractor (9 方法 / ~790 行)

**Metadata**:
- **Iteration #**: 041
- **Task Tree Level**: L2
- **Parent Task**: ARCHITECTURE_TODOLIST #1 (拆 driver_extractor)
- **Created**: 2026-08-28 19:10 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 0 回归, always 全路径探针 byte-identical

---

## 🎯 本次目标

用户指令: **"继续做 step6"** → 拆 always_extractor（#1 剩余步骤中**最高风险**）。

从 `driver_extractor.py` 拆出 9 个 always 相关方法 (~790 行) →
`extractors/always_extractor.py`:

| 方法 | 行数 | 职责 |
|---|---|---|
| `_create_always_edges` | **453** | 主入口 — always_ff/comb/latch |
| `_add_condition_drivers` | 81 | [Phase 7.6] 已 disabled |
| `_collect_signals_from_ast` | 48 | AST 遍历提取 cond signals |
| `_is_valid_signal_name` | 15 | SV 标识符检查 |
| `_collect_stmts_with_context` | 62 | statement + ctx 收集 |
| `_extract_reset_from_always` | 41 | reset 提取 |
| `_get_always_body_items` | 24 | always body 展平入口 |
| `_extract_clock_from_always` | 11 | 时钟提取 |
| `_extract_clock_from_event_ctrl` | 39 | 时钟事件提取 |

---

## 🔑 调查发现: 共享 helper 边界要精确定义

**最初以为 11 个方法都搬**，但深挖后发现 2 个是**共享基础设施**，不能搬：

| 方法 | 被谁调用 | 结论 |
|---|---|---|
| `_is_compile_time_symbol` | `_expr_is_compile_time` / `_filter_signal_conditions_by_module`（**always 块外**） | 🔴 **留在 driver_extractor** |
| `_is_sv_literal_token` | `_filter_signal_conditions_by_module`（always 块外） | 🔴 **留在 driver_extractor** |
| `_is_valid_signal_name` | 只被 `_collect_signals_from_ast`（always 块内） | ✅ 搬走 |

这两个方法被 assign/always/function 三处共用，搬走会断掉 Step 4/7 的依赖。
**通过 AlwaysHelpers 注入**给 always_extractor 使用。

### 依赖注入 (AlwaysHelpers dataclass)

沿用 Step 4 AssignHelpers 模式，注入 10 个共享 helper + 3 个状态对象：
`adapter` / `get_signal` / `get_all_real_signals` / `parse_assign` /
`store_expr_tree` / `handle_invocation` / `build_signal_source` /
`expr_is_compile_time` / `filter_signal_conditions_by_module` /
`flatten_semantic` / `is_sv_literal_token` / `signal_visitor` /
`edge_factory` / `cond_ast_by_str`。

---

## 🔬 实施中的问题 (诚实标注)

### 失误: `@staticmethod` 装饰器连带丢失

删除 `_collect_signals_from_ast`（它是 `_is_compile_time_symbol` 的前一个方法）
时，删除区间尾部把紧随其后的 `@staticmethod` 行也吞了 → `_is_compile_time_symbol`
从 staticmethod 变成普通实例方法 → 调用 `self._is_compile_time_symbol(sym)`
传 2 个参数报 `TypeError: takes 1 positional argument but 2 were given`。

**25 个 integration 测试因此失败**（test_ternary_in_if 等），错误信息直接定位。

**修复**: 加回 `@staticmethod`。

**教训**: 删除方法区间时，**区间的下一个方法的装饰器**（`@staticmethod`/`@classmethod`）
是区间外的行，要检查是否被误删。这类"边界行吞并"在行号切片删除时很容易发生。

### 其他小修正

- import 排序（ruff I001 自动修复）
- driver_extractor 删除搬走后未用的 `StatementKind` / `kind_matches` import
- `_EXCLUDED_SYMBOL_KINDS` 类属性 → 模块常量（随 `_collect_signals_from_ast` 搬走）

---

## 📈 验证 (git worktree A/B, 基线 = `dd9e196`)

### 回归: 全套 0 新增失败

| 测试套 | 基线 `dd9e196` | Step 6 后 | 结论 |
|---|---|---|---|
| `integration` | 13 failed | **13 failed** | ✅ 0 回归 (修 staticmethod 前 38, 修复后 13) |
| `cli` | 20 failed | **20 failed** | ✅ 0 回归 |
| `unit` | 4 failed (沙箱) | **4 failed** | ✅ 0 回归 |
| `test_case27_1to1_truth` | — | **4 passed** | ✅ 全绿 |

### 🔑 行为等价: always 全路径探针

覆盖 always_ff async reset + always_comb case + ternary 的 fixture，对比 16 条边 / 12 节点:

```
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n) o1<=0; else if(sel[0]) o1<=a; else o1<=b;
end
always_comb begin case(sel) 0:o2=a; 1:o2=b; default:o2=a^b; endcase end
always_ff @(posedge clk) o3 <= sel[1] ? a : b;
```

A/B diff **完全 byte-identical** — 包括 CLOCK/RESET 边、condition_chain
(`['!(!rst_n) && sel[0]']`)、ternary 的 BRANCH_* 边。

### lint

- `always_extractor.py`: **All checks passed!**（I001 自动修复后）
- `driver_extractor.py`: 删除 2 个本次引入的未用 import；剩 1 个 `side_kind` F841 是先期问题

---

## 📊 进度

| 指标 | 值 |
|---|---|
| `driver_extractor.py` | 3035 → **2292 行** (净减 743) |
| 累计拆出 (#1 全程) | 4101 → 2292, **净减 1809 行** |
| #1 步骤 | **7/9 完成** (1+2/3/3b/4/4b/5/6) |

---

## 📌 下一步

- **Step 7: 拆 function_extractor** (估 1 天) — `_handle_invocation` /
  `_create_invocation_edges` / `_find_func_assignment_rhs` 等
- Step 8: 删 driver_extractor.py 主体 (0.5 天)
- Step 9: 全套最终回归 (0.5 天)
