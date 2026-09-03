# L2 connection RangeSelect 连接命名恒 '?' 修复 (iter_119)

> **创建**: 2026-09-03 GMT+8
> **来源**: iter_118 极端场景 S2 (四级嵌套 gen, `m2 实例 .a(a[i*4+:4])`) 出占位
> `top.u_m1.G1[1].u_m2.a[?]` — connection 侧 RangeSelect 连接信号命名无法求值。
> **父任务**: 极端场景验证 → 缺口修复系列

## 🎯 目标

| sub-task | 验收 |
|---|---|
| 1. 诊断 | S2 复现定位; S1 (同写法, top 级 gen) 为何无 '?' — fold 差异 or 分支差异 |
| 2. 修 | `_conn_expr_to_signal` RangeSelect 用 expr.left/right 求值 (semantic 无 .selector); `_eval_select_index` 支持 * / ; 命名含具体范围 |
| 3. 测试 | unit S2 形态 (无占位 + 范围名) + 回归 |
| 4. 文档 | iter_119 + overview + CURRENT_TODO |

## 🔬 已知事实 (iter_118)

- S2 conn `.a(a[i*4+:4])` (i=m1 genvar, entry G1[1]): expr kind=RangeSelect,
  **expr.selector=None** (semantic RangeSelect left/right 在 expr 上);
  expr.left = BinaryOp Multiply(NamedValue i, Conversion 4) → i*4;
  expr.right = IntegerLiteral 4
- `_conn_expr_to_signal` 的 select 分支只取 expr.selector → None → idx='?' 恒
- `_eval_select_index` 只支持 Literal/Conversion/NamedValue(gidx)/BinaryOp(±?) —
  无 Multiply
- S1 (同 .a(a[i*4+:4]), top 级 G1) 无占位 → 需查明差异 (slang 是否 fold 常量)
