# Iteration 065: test_constraint_derivative 行为断言升级

**Metadata**:
- **Iteration #**: 065
- **Task Tree Level**: L2
- **Parent Task**: iter_064 行为断言补齐 (继续推进)
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (6 个测试补 CONSTRAINS 边断言, 1 个解释性保留, 7 passed)

## 🎯 本次目标

方豆指示: "升级 **constraint 域** 的测试文件, 让断言**更严格** — 在保留
现有断言 (AST 节点存在性) 的基础上, **补充行为断言**"。

目标文件: `sim/tests/regression/test_constraint_derivative.py` (7 个测试,
目前全是 AST 断言 — 只检查 `len(classes) == 1` + 节点存在)。

参考: iter_064 已升级的 `test_constraint_advanced.py` 的行为断言模式
(`_build_graph` + `_edges_of_kind` + `_assert_constrains`)。

## 📊 当前状态 / 预期结果

- 7 个测试, 每个只断言 AST 节点 (classes/members)
- 行为金标准 (constraint 域): **CONSTRAINS 边** — 约束块 → 被约束的
  CLASS_PROPERTY 变量 (铁律13)
- 预期: 6 个测试补 CONSTRAINS 边断言; `solve_before` 因为语义是求解顺序
  而非值约束, 解释性保留 AST 断言

## 🔬 实际结果

### 探针结果 (确认 7 种衍生约束的 CONSTRAINS 边实际形态)

写 `/tmp/probe_constraint.py`, 用 `UnifiedTracer` 对每种语法构建图,
过滤出 `EdgeKind.CONSTRAINS` 边:

| 测试 | block_id | CONSTRAINS 边 (block → vars) | 行为判定 |
|---|---|---|---|
| `inside` | `packet.c` | `packet.c → packet.addr` | ✅ 行为断言可加 |
| `implication` | `packet.c` | `packet.c → packet.data`, `packet.c → packet.en` | ✅ 行为断言可加 |
| `if_else` | `packet.c` | `packet.c → packet.addr`, `packet.c → packet.en` | ✅ 行为断言可加 |
| `dist` | `packet.c` | `packet.c → packet.addr` | ✅ 行为断言可加 |
| `solve_before` | `packet.c` | (无 var 边, 仅 `packet.c → packet.c::solve_0`) | ⚠️ 语义非值约束 |
| `unique` | `packet.unique_c` | `packet.unique_c → packet.a/b/c` | ✅ 行为断言可加 |
| `loop` | `packet.c` | `packet.c → packet.arr` | ✅ 行为断言可加 |

### 升级结果

升级 6 个测试, 加 `_assert_constrains(...)` 行为断言:

1. **`test_constraint_inside`**: `packet.c → packet.addr`
2. **`test_constraint_implication`**: `packet.c → packet.data`, `packet.c → packet.en`
3. **`test_constraint_if_else`**: `packet.c → packet.addr`, `packet.c → packet.en`
4. **`test_constraint_dist`**: `packet.c → packet.addr`
5. **`test_constraint_unique`**: `packet.unique_c → packet.a`, `→ packet.b`, `→ packet.c`
6. **`test_constraint_loop`**: `packet.c → packet.arr`

### `solve_before` 解释性保留

`solve addr before data` 是**求解顺序声明** (不是值约束)。pyslang 把它
解析成 `SolveBeforeConstraint`, 提取器为它生成 `packet.c::solve_0` 子节点,
但**不**抽取为 CONSTRAINS 边到 `addr/data` 变量 — 因为求解顺序不是"约束谁",
而是"谁先求谁后求"。

probed 图只有 `packet.c → packet.c::solve_0` 一条 CONSTRAINS (block 到子节点),
没有到变量的 CONSTRAINS 边。所以这个测试保留 AST 断言 (block 节点 + solve_0 子节点),
在 docstring 中明确解释**为何行为金标准不适用**。

### 验证

```bash
$ python -m pytest sim/tests/regression/test_constraint_derivative.py -q
.......                                                                  [100%]
7 passed in 0.13s
```

## 💡 关键发现 / 关键技术 / 决策

1. **CONSTRAINS 边的实际形态与 expected 不同**: 之前 iter_063/064 的
   `test_constraint_advanced` 假设 `block → var` 是单向边, 探针确认:
   1. 还有一条 `class → block` 边 (class 也 CONSTRAINS block, 因为 class
      "声明"了 block)
   2. 还有 `block → block::expr_N` / `block → block::if_N` 等 (block
      CONSTRAINS 自己的子节点)
   3. 行为金标准只关注 **block → CLASS_PROPERTY (变量)**, 这才是"约束谁"
   探针的好处: 提前发现真相, 而不是写完测试再 debug

2. **求解顺序 ≠ 值约束**: `solve a before b` 是约束求解器的顺序声明,
   而不是限制变量取值范围, 所以提取器合理地**不**把它建模为 CONSTRAINS 边。
   测试要尊重建模选择 — 硬塞 CONSTRAINS 断言等于要求工具改设计。

3. **implication 约束的条件变量也算 CONSTRAINS**: `(en) -> data == 1` 中
   `en` 是条件, `data` 是被约束值。提取器不区分条件 vs 值, 都建模为
   CONSTRAINS (与 `_assert_constrains` 期望一致)。这与 advanced 测试
   的 `if/else` 行为一致 — block → if/impl 子节点用 CONSTRAINS 边,
   if/impl 子节点到变量用 HAS_CONDITION 或 CONSTRAINS (设计选择)。

4. **测试写法原则 (iter_064 沉淀, 本次复用)**: 语法覆盖测试 =
   AST 断言 (验证解析) **+** 行为断言 (验证分析)。两者缺一不可 —
   前者防语法回归, 后者防语义回归。

5. **不在本次的发现**: `test_constraint_if_else` 的现有测试只断言
   `len(classes) == 1` (仅 1 行有效断言), 升级后加了节点存在 +
   2 条 CONSTRAINS 边断言, 信息量大增。
