# Iteration 305: 深层 packed 成员节点（PLAN P13.4）

**Metadata**:
- **Iteration #**: 305
- **Task Tree Level**: L2（PLAN `P13.4`）
- **Created**: 2026-10-27 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "嗯，继续"）
- **Outcome**: ✅ 完成（`o.inner.a` 可建/可查；2512 passed）

## 🎯 问题

成员补齐只到一层：`o.inner.a` 不存在 → `fanin(o.inner.a[1])` 空答。
查询层 `_packed_parent_step` 本来支持多级 parent 链，缺的是**节点**。

## 🔧 实现

### 适配器：递归成员树

`get_packed_member_tree(var_symbol, max_depth=8)` → `[{name,width,offset,signed,children}]`：

- 从 `canonicalType.syntax.members` 取名字 + `lookupName(name).bitOffset/type`
- 成员类型若仍是 packed struct/union → 递归 `children`
- 每层 `offset` **相对直接父成员**（与 `parent_bit_start/end` 语义一致）
- 深度上限 8；`_packed_members_of_type` 为递归实现

### GraphBuilder：递归建节点

`_apply_packed_member_layout` 改为 `walk(tree, parent_id)`：

- 节点 id = `父路径.成员名`（`top.o.inner.a`）
- `parent` 指直接父成员（`top.o.inner`），位段相对父成员（`a` → `[7:4]`）
- 无引用成员也补齐；节点总量上限 5000（超限 warning）
- 新节点同样带 `extra.packed_member` / `is_signed` / `bit_range`

### 查询层：fanout 补位子节点

`fanout(o.inner.a[1])` 先把成员位换到聚合位 `o[9]`，但负载可能挂在**位子节点**
`o[9]` 上（`assign y[9]=o[9]`）而不是总线上。现在 fanout 同时并入：
`o`（整总线拷贝）与 `o[9]`（位负载）两路结果，去重。

## 📊 效果

| 查询 | 修复前 | 修复后 |
|---|---|---|
| `fanin(o.inner.a[1])` | `{}` | **`{x[1]}`**（inner[5] → o[9]） |
| `fanout(o.inner.a[1])` | `{}` | **`{y[9]}`** |
| `o.inner.a` 节点 | 不存在 | `(3,0)`，parent `o.inner`，位段 `[7:4]` |
| `o.inner` | 已存在 | parent `o`，位段 `[11:4]`（不变） |
| `fanin(o.inner.a)` 总线查询 | `{}` | `{}`（不触发位桥） |

## 🧪 测试

`test_packed_struct.py` 18 → 22：
- 二级成员节点/父链/位段
- 深层 fanin（`o.inner.a[1] → x[1]`）
- 深层 fanout（`→ y[9]`）
- 成员总线查询不被劫持

适配器 API 冻结表 +2（`get_packed_member_tree`、`_packed_members_of_type`）。

## ✅ 验证

- 全量：2508 → **2512 passed / 0 failed**
- 图基线 / CLI golden **无差异**（fixture 无嵌套 struct）
- check_docs / check_plan / check_cli_layers / check_except_pass 全绿

## 📌 边界

- 深度上限 8；成员节点总量上限 5000（超限 warn）
- 非 packed struct 仍不参与
- 深层成员**位级**查询桥复用 P12 的 parent 链，无新增语义

## 🔗 相关

- 计划: [PLAN.md P13.4](../../../PLAN.md)
- 前序: [iter_299 packed struct](iter_299_packed_struct.md) / [iter_300 成员位桥](iter_300_packed_member_bit_bridge.md)
