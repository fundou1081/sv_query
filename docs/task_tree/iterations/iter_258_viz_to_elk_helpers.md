# Iteration 258: T3-7 — `viz_to_elk` 纯 helper 提取（584 → 521 行）

**Metadata**:
- **Iteration #**: 258
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-20 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 成功（584 → 521 行；6 份 SVG 逐字节一致；全量 3422 passed）

## 🎯 目标

`viz_to_elk` 是 elk_bridge 里第二大的函数（584 行）。按 iter_257 的手法先做**纯 helper 提取**
（不做主体拆分）。

## 🔬 做法

AST 量了 4 个嵌套闭包的捕获：

| 嵌套 | 行数 | 捕获 |
|---|---|---|
| `ne` | 1 | `ctr` |
| `_emit_edge` | 14 | `_EDGE_STYLES`（局部常量表） |
| `_collect_all_emitted_ids` | 10 | **0** |
| `_collect_post_ids` | 9 | **0** |

把后三者 + `_EDGE_STYLES`（30 行）提到模块级：

- `_EDGE_STYLES_VIZ`（常量，避免与 `expr_trees_to_elk` 的同名概念混淆）
- `_emit_edge_viz(...)`（带 `edge_obj` 参数的那个版本）
- `_collect_all_emitted_ids(...)` / `_collect_post_ids(...)`

`ne()` 仍留在函数内（它只捕获 `ctr`，且与调用方的 id 序列强绑定，提出去反而要传参）。

### 一个自己造的坑（第一次做错，已回滚重来）

第一次用全局 `str.replace("_emit_edge(", "_emit_edge_viz(")` 改名，
结果**把 `expr_trees_to_elk` 里的同名局部 helper 也改了** ——
两个不同签名的 `_emit_edge_viz` 同时存在（一个局部、一个模块级），语义混乱。

修法：`git checkout` 回滚，改成**只在 `viz_to_elk` 的行区间内**替换调用点，
并用 `_EDGE_STYLES_VIZ` 这类独立命名避免与另一函数的概念撞名。

> 教训：跨函数同名 helper 的重命名必须**限定作用域**，全局替换会在同名场景下制造歧义。

## ✅ 验收

- 6 份 SVG（3 fixtures × dataflow/timed）与 iter_257 后的基线 **逐字节相同**
- 全量门禁 **3422 passed / 0 failed**

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| `viz_to_elk` | 584 行 | **521 行** |
| `elk_bridge.py` | 2,410 行 | 2,420 行（helper 移出的净效果 + 模块级常量） |
| 模块级可读 helper | — | +3（`_emit_edge_viz` / 两个 collect） |

## 💡 决策

**主体不做进一步拆分**：`viz_to_elk` 是**顺序相位**结构（Phase 0~4 + 后处理），
没有大片闭包。要拆只能按行切成"相位函数"，而它们共享 20 多个可变状态
（`root_children` / 各 dedup map / `graph`）—— 收益是"每段短一点"，
代价是把顺序耦合变成参数耦合，且 SVG 输出对顺序敏感。

**判断**：521 行的顺序函数虽然长，但它的"阅读成本"是可接受的（每段有 Phase 注释），
再拆的边际收益低于风险。**记为"评估后不做"，而不是"没做"**。

## 🔗 相关

- 同模式: [iter_257 expr_trees_to_elk ctx 拆分](iter_257_elk_ctx_refactor.md)
- 评审: [2026-10-19_core_smell_review.md A4](../../refactoring/2026-10-19_core_smell_review.md)
