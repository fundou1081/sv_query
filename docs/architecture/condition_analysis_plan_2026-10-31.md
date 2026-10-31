# 条件化简 / 互斥判断 — 设计评估（未排期）

**日期**: 2026-10-31
**状态**: 只记录，**不实现**（方豆: "先只记录，先不做"；PLAN `P25` 待做）
**背景**: P23/P24 已实现路径条件组合与多路径 OR，保留原始条件；下一步是否化简/判互斥。

## 核心原则

1. **不改写** `condition` / `conditions` / `condition_paths`；只加派生字段。
2. 每条路径的原始条件必须保留，方便区分来源。
3. 任何化简/互斥结论必须带 method/confidence；不能证明就 `unknown`，不猜。

## 三层方案

### L1 局部布尔化简（先做）

- 实现一个只识别 `!` / `&&` / `||` / 括号的布尔 IR；其余整体作为 Atom。
- 恒等式：双重否定、幂等、吸收、补元、同一因子提取、同一余项、常量。
- 输出：
  ```json
  "condition_simplified": "...",
  "condition_analysis": {"changed": true, "method": "local_v1",
                          "tautology": false, "unsat": false,
                          "confidence": "atom_identity"}
  ```
- 原子文本不同（`a>0` vs `!(a<=0)`）不视为同一原子；不进化简。

### L2 来源互斥（需 extractor 支持）

- 边上增加 `branch: {group, arm}`（if/else、ternary、case item）。
- 同 group 不同 arm → 互斥；同 arm → 不互斥；无 group → unknown。
- `casez/casex` 可能重叠，不假设互斥；`unique case` 可高置信。
- 用途：多驱动 `driver_conflict`（none/possible/proven_exclusive/unknown），
  避免把 `sel?a:b` 误报为冲突。
- 四态注意：`else` 不等于严格 `!cond`（X 语义），文档注明。

### L3 精确布尔分析（可选）

- 原子数 ≤12 真值表；更多用 BDD（节点上限如 10k）。
- 判断永真/不可满足/两条件互斥/蕴含。
- 超限 `analysis_incomplete=true`，不输出“已化简”结论。
- 不做算术谓词关系（`a>0` vs `a<=0`）；不引入 SAT/SMT 外部依赖。

## 输出字段草案

| 现有 | 新增 |
|---|---|
| `condition` | `condition_simplified` |
| `conditions` | `conditions_simplified` |
| `condition_paths` | 每项 `simplified` / `unsat` |
| `condition_unconditional` | `condition_tautology` |
| `condition_truncated` | `condition_analysis_incomplete` |
| `multi_driver` | `driver_conflict` |

## 风险

- 直接改写字符串不可追溯；
- 原子不同无法判断导致“化简失败”是常态；
- casez/四态下互斥假设可能错误；
- BDD 原子多时爆炸，输出可读性差。

## 建议执行顺序

L1（独立、低风险）→ L2（extractor branch group、多驱动冲突）→ L3（可选，带上限）。
