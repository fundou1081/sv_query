# Iteration 256: T3-5 — `elk_bridge` 巨型函数：提取纯 helper + 拆解计划

**Metadata**:
- **Iteration #**: 256
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-20 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ⚠️ 部分完成（纯 helper 已提出，闭包主体**未拆**，附可执行的拆解计划）

## 🎯 目标

`expr_trees_to_elk` 是全仓最长函数（908 行，评审 A4）。目标是把它拆成可读的几段。

## 🔬 诊断：为什么不能直接按行切

用 AST 分析了 7 个嵌套函数的**闭包捕获**：

| 嵌套函数 | 行数 | 捕获外层变量 |
|---|---|---|
| `render_tree` | 292 | **11 个**（`root_children` / `root_edges` / `input_set` / `output_set` / `input_paths` / `output_paths` / `input_short_to_fulls` / `output_short_to_fulls` / `_being_rendered` / `_signal_cache` / `_gen_block_map_global`） |
| `render_ternary` | 135 | **6 个**（含 `root_children` / `root_edges` / `input_set` / `input_paths` / 两个 short_to_fulls） |
| `_resolve_emitted_port_id` | 7 | 3 个 |
| `_collect_sigs` / `_walk_refs` / `_a12_collect` | 5/14/8 | 1/2/1 |
| **`_parse_gen_block` / `collect_signals`** | 40/8 | **0（纯函数）** |

结论：主体是**闭包状态**，直接按行切会把"隐式共享状态"变成"显式参数"，
必须同时改造 11 个变量的读写点 —— 属于**中等风险重构**，不能在没读透渲染语义时动。

## ✅ 本次做了什么（零风险部分）

把 2 个**纯函数**提到模块级（捕获数 = 0）：

- `_parse_gen_block(parent_module, signal_label)` —— generate block 反推（40 行）
  - 顺带把函数内的 `import re as _re_v1610` 与 `_genblk_re` 提到模块级
    （否则提取后 `NameError`；这一步实测踩到了）
- `collect_signals(tree_node, into)` —— 递归收集 SignalRef label（8 行）

效果：`expr_trees_to_elk` **908 → 858 行**；两个函数现在**可独立单测**。

## 📋 拆解计划（下一阶段，需专门一轮 + SVG 基线）

1. 定义 `@dataclass _ElkCtx`：装那 11 个共享字段（children/edges/集合/paths/缓存/环检测）
2. `render_tree(ctx, ...)` / `render_ternary(ctx, ...)` 移到模块级，内部访问改 `ctx.X`
   —— 可用 AST 批量改（把捕获名在 Load/Store 上下文改成 `Attribute(ctx, name)`）
3. 保留 `expr_trees_to_elk` 作为编排：构造 ctx → 调各段 → 返回
4. **验收方式**：现有 SVG/ELK 断言（`sim/tests/cli/test_visualize_*`）+ 生成物逐字节对比
   （先存一份 SVG/ELK JSON 基线，改完 diff 必须为空）

**风险**：ELK 输出对节点/边顺序敏感，任何重排都会改 SVG（golden 会红）。
所以必须先锁基线再动，而不是"改完跑测试看看"。

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| `expr_trees_to_elk` | 908 行 | **858 行** |
| 模块级可单测 helper | 0 | **2** |
| `elk_bridge.py` | 2,340 行 | 2,350 行（helper 移出 + 模块级 import/常量） |
| 全量测试 | 3422 | **3422 passed / 0 failed** |

## 💡 决策

1. **只做零风险部分，其余写计划。** 主体的闭包改造会影响 SVG 输出，
   而当前可视化是稳定状态（iter_254 刚拆过、门禁全绿）。在没建立"逐字节基线"之前不动它。
2. **提取时暴露了一个隐性依赖**：`_parse_gen_block` 用的是函数内 `import re as _re_v1610`
   和局部编译的正则 —— 提取必须先把它变成模块级。这类"函数内 import"是拆分的常见地雷。
3. **拆解计划要写到可执行**：不是"以后拆一下"，而是给出 context 对象字段清单、
   AST 改写方式、以及"SVG/ELK 逐字节基线"的验收标准。

## 🔗 相关

- 评审: [2026-10-19_core_smell_review.md A4](../../refactoring/2026-10-19_core_smell_review.md)
- 前置: [iter_255 FSM 提取](iter_255_fsm_extract_and_facade_review.md)
- 后续 backlog: `render_tree`(292) / `render_ternary`(135) / `viz_to_elk`(584)
