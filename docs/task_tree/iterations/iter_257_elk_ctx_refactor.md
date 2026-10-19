# Iteration 257: T3-6 — `expr_trees_to_elk` 闭包拆分（858 → 438 行）

**Metadata**:
- **Iteration #**: 257
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-20 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 成功（858 → 438 行；**6 份 SVG 逐字节一致**；全量 3422 passed）

## 🎯 目标

按 iter_256 写的计划，把 `expr_trees_to_elk` 的闭包主体（`render_tree` 292 行 /
`render_ternary` 135 行）拆成模块级函数。

## 🔬 改法：显式 context 对象

```python
@dataclass
class _ElkCtx:      # 31 行
    root_children, root_edges, input_set, output_set,
    input_paths, output_paths, input_short_to_fulls, output_short_to_fulls,
    signal_cache, being_rendered, gen_block_map_global, emitted_port_ids,
    ctr, viz, expr_trees, output_names
    def ne(self): ...        # 与调用方共享 ctr, 保证 edge id 连续
    def emit_edge(self, ...)
```

- `render_tree` → `_render_tree(ctx, ...)`（292 行，模块级）
- `render_ternary` → `_render_ternary(ctx, ...)`（135 行，模块级）
- `_resolve_emitted_port_id` → 模块级（7 行）
- `expr_trees_to_elk` 只保留编排 + 构造 ctx：**858 → 438 行**

改造用 **tokenize 而非正则**：只改 NAME token，不碰字符串/注释（这个文件里
解释性注释极多，用正则重写会毁掉它们）。

## 🕳️ 过程中踩的 4 个坑（都留了记录）

| # | 现象 | 原因 | 修法 |
|---|---|---|---|
| 1 | 第一次脚本写坏文件（`IndentationError`） | 有个嵌套函数缩进比预期深，按"去 4 格"处理导致错位 | `git checkout` 回滚，只提纯函数 |
| 2 | `def _render_ternaryctx, (` 语法错 | token 改名与 ctx 插入在同一次编辑里按列改，位置互相偏移 | 合并成一个编辑列表，从右往左统一应用 |
| 3 | `NameError: viz is not defined` | **闭包还捕获了函数参数**（`viz`），而我的捕获分析只统计了"赋值的局部变量" | 把 `viz` / `expr_trees` 也放进 ctx |
| 4 | `NameError: output_names is not defined` | 同上（另一个参数） | 加入 ctx |

> 教训：**"闭包捕获"要算上函数参数**，不只算局部赋值。我用 AST 只扫了
> Assign 目标，漏了 `def f(viz, expr_trees, ...)` 这类。

## ✅ 验收：6 份 SVG 逐字节一致

不是"测试绿了就算"，而是先锁基线再比对：

```bash
git stash                      # 回到重构前
visualize dataflow/timed × 3 fixtures  → /tmp/base_head/*.svg
git stash pop                  # 恢复重构
同命令再跑一遍                  → /tmp/after/*.svg
cmp 逐份比较
```

结果：**6/6 逐字节相同**（binary_ops / calc_chain / case_demo × dataflow/timed）。

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| `expr_trees_to_elk` | 858 行 | **438 行** |
| 模块级可读函数 | 2 | **5**（+`_render_tree` / `_render_ternary` / `_resolve_emitted_port_id`） |
| 显式 state | 0 | `_ElkCtx`（16 字段 + 2 方法） |
| SVG 输出 | — | **逐字节不变** |
| 全量测试 | 3422 | **3422 passed / 0 failed** |

## 💡 决策

1. **context 对象优于"参数列表"**：16 个状态传参会让签名爆炸；dataclass 同时给出
   字段清单文档与默认值。
2. **edge id 必须共享计数器**：`ctx.ne()` 用的是**调用方传入的同一个 `ctr` 列表**，
   否则子树的 id 会与外层重复（ELK 会静默错位）。
3. **逐字节比对是这类改动的唯一硬证据**：测试断言只检查结构（节点数/标签），
   顺序或 id 变化可能让测试全绿但图形错乱。

## 🔗 相关

- 计划来源: [iter_256](iter_256_elk_bridge_partial.md)
- 评审: [2026-10-19_core_smell_review.md A4](../../refactoring/2026-10-19_core_smell_review.md)
- 剩余: `viz_to_elk`（584 行，同样的模式可套）
