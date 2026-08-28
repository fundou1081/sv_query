# Iteration 040: #1 Step 5 — 拆 statement_flattener (8 方法 / 204 行)

**Metadata**:
- **Iteration #**: 040
- **Task Tree Level**: L2
- **Parent Task**: ARCHITECTURE_TODOLIST #1 (拆 driver_extractor)
- **Created**: 2026-08-28 18:20 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 0 回归, flattener 全路径探针 byte-identical

---

## 🎯 本次目标

用户指令: **"继续"** → Step 5 拆 statement_flattener。

拆出 `driver_extractor` 里 8 个 `_flatten_*` 方法 (line 2048-2251, 204 行) →
`extractors/statement_flattener.py`:

| 方法 | 行数 | 职责 |
|---|---|---|
| `_flatten_assignments` | 10 | DEPRECATED 兼容入口, 委派 semantic |
| `_flatten_semantic` | 33 | 主调度: 按 StatementKind 分发 |
| `_flatten_block` | 24 | Block 展平 |
| `_flatten_timed` | 5 | Timed 跳 timing |
| `_flatten_conditional` | 41 | Conditional 展开 if/else |
| `_flatten_loop` | 10 | 各类循环 |
| `_flatten_expression_statement` | 31 | ExpressionStatement |
| `_flatten_case` | 50 | Case/PatternCase |

---

## 🔑 依赖分析 (调查先行)

实测只有 **2 个外部依赖**:

1. **`_get_signal`** — 3 个 visitor 用 (conditional/expression/case)。Step 3 已迁
   `_common.get_signal`, 薄壳是 `self._get_signal`, 直接 Callable 注入。
2. **`self._cond_ast_by_str`** — 实例 dict (line 122 init / line 1968 read),
   记录 cond_string → AST 节点映射, 供 `_collect_stmts_with_context` 回填
   `condition_ast` (Plan F3-pre 2026-08-13)。

**关键设计**: `_cond_ast_by_str` 是**跨方法共享的可变状态**。不是把它变成全局单例
(违反纪律 #2 无副作用), 而是**作为参数传入** — 调用方持有 dict, flattener 往里写,
调用方之后读。递归时自动转发。

其余 6 个 visitor **只互调 `_flatten_semantic`**, 无外部依赖 — 纯模块内。

---

## 🔬 实施细节

### 生成脚本的两次修正 (诚实标注)

1. **第一次生成漏了参数转发**: `_flatten_semantic` 调 `_flatten_block(stmt, result, cond_stack)`
   但后者的签名已加 `*, get_signal, cond_ast_by_str` → 运行时 TypeError。
   **修正**: 正则把所有 `self._flatten_xxx(...)` 调用改为
   `_flatten_xxx(..., get_signal=get_signal, cond_ast_by_str=cond_ast_by_str)`。

2. **import 修正**: 生成的模块缺 `StatementKind`/`ExpressionKind` import (从
   `pyslang.pyslang.ast` 导入); 且 header 里多余的 `Any/Callable` import 是死代码。

3. **薄壳 import 名修正**: 生成模块的函数名带下划线 (`_flatten_assignments`),
   薄壳最初写 `flatten_assignments` (无下划线) → NameError。修正为带下划线名。

**这轮失误比 Step 4b 少**, 因为 flattener 的依赖形状更简单 (递归参数自动转发
比"返回值契约"好处理)。教训依旧: **机械转换后必须跑真实路径测试** (integration
里 always/if/case 相关 11 个测试) 才能暴露这类接口错配。

---

## 📈 验证 (git worktree A/B, 基线 = `427879b`)

### 回归: 全套 0 新增失败

| 测试套 | 基线 `427879b` | Step 5 后 | 结论 |
|---|---|---|---|
| `integration` | 13 failed | **13 failed** | ✅ 0 回归 |
| `cli` | 20 failed | **20 failed** | ✅ 0 回归 |
| `unit` | 4 failed (沙箱) | **4 failed** | ✅ 0 回归 |
| `test_case27_1to1_truth` | — | **4 passed** | ✅ 全绿 |

### 🔑 行为等价: flattener 全路径探针

专门写了覆盖 if/else + case + for loop + timing 的 fixture, 对比 19 条边 / 11 节点:

```
if (!rst_n) o1<=0; else if(sel[0]) o1<=a; else o1<=b;
case(sel) 0:o2<=a; 1:o2<=b; default:o2<=a^b; endcase
for(...) o3<=a;
@(posedge clk) o4<=a;
```

A/B diff **完全 byte-identical** — 包括 condition_chain (`['!(!rst_n) && sel[0]']`
这种嵌套条件路径) 和 case 的 `sel == 2'b0` 文本。

### lint

- `statement_flattener.py`: **All checks passed!**
- `driver_extractor.py`: 删了 1 个本次引入的 `ExpressionKind` 未用 import;
  剩 1 个 `side_kind` F841 是先期问题 (Step 4 已确认, 非本次引入)

---

## 📊 进度

| 指标 | 值 |
|---|---|
| `driver_extractor.py` | 3211 → **3035 行** (净减 176) |
| 累计拆出 (#1 全程) | 4101 → 3035, **净减 1066 行** |
| #1 步骤 | **6/9 完成** (1+2 / 3 / 3b / 4 / 4b / 5) |

---

## 📌 下一步

- **Step 6: 拆 always_extractor** (估 1.5 天, **最高风险** — `_create_always_edges`
  和 assign 共享 `_parse_assign` / `_expr_is_compile_time` /
  `_filter_signal_conditions_by_module` / `_build_signal_source` 等 helper)
- Step 7: function_extractor (1 天)
- Step 8: 删 driver_extractor.py 主体 (0.5 天)
- Step 9: 全套最终回归 (0.5 天)
