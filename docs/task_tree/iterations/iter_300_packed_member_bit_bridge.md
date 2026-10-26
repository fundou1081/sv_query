# Iteration 300: packed 成员位级查询桥（PLAN P12）

**Metadata**:
- **Iteration #**: 300
- **Task Tree Level**: L2（[L1_packed_member_bridge](../tasks/L1_packed_member_bridge.md) / PLAN `P12`）
- **Created**: 2026-10-26 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "做吧"）
- **Outcome**: ✅ 完成（成员位 ↔ 聚合位贯通；2489 passed）

## 🎯 问题

P11 给了成员宽度/位段，但位查询仍粗粒度：
`fanin(p.a[1])` 不知道 `p.a[1]` 就是 `p[5]`，回落成员总线/空答；
`fanout(p.a[1])` 也会错误地落到 `p[1]`（成员内位 1 当成聚合位 1）。

## 🔧 实现

### P12.1 位换算（parent 链）

`SignalTracer._packed_parent_step(node, bit)`：
- **成员总线**（`p.a`，`extra.packed_member`）：`p.a[k]` ↔ `p[lo + k]`（lo = min(parent_bit_start/end)）
- **成员的位节点**（`p.a[1]`）：父是成员总线 → `(p.a, 1)`

`_packed_top_bit` 沿 parent 链一路换到顶层聚合（支持嵌套 `o.inner[1]` → `o[5]`）。

接入：
| 方向 | 行为 |
|---|---|
| fanin | 成员位无驱动时，换到聚合位继续追（`p.a[1]` → `p[5]` → `x[5]`） |
| fanout | 先换到聚合位再取负载，并**跳过** `_load_bus_fallback`（否则会错误落到 `p[1]`） |
| 父总线负载映射 | 成员节点在 `_parent_driver_loads` 里先把成员位换成聚合位再 map |

### P12.2 未被引用的成员也建节点

之前的成员节点只来自 RTL 引用；查询 `p.a[1]` 时若 `p.a` 不存在，
`_trace_missing_node` 找不到 base 直接空答。现在 `_apply_packed_member_layout`
会为每个 struct 变量补齐所有成员节点（宽度/signedness/parent 位段/`packed_member` 标记）。

## 📊 效果

| 查询 | 修复前 | 修复后 |
|---|---|---|
| `fanin(p.a[1])` | `{}` / 成员总线 | **`{x[5]}`**（a 在 [7:4]） |
| `fanout(p.a[1])` | `{y[1]}`（错位） | **`{y[5]}`** |
| `fanout(p.b[2])` | — | **`{y[2]}`**（b 在 [3:0]） |
| `fanin(pu.u8[5])` | `{}` | **`{x[4]}`**（union offset=0） |
| `fanin(o.inner[1])` | `{}` | **`{x[3]}`**（inner 在 [11:4]） |
| `fanin(p.a)`（总线查询） | `{}` | `{}`（不触发位桥，语义不变） |

跨位检查：`p.a[1]` 不含 `x[4]` / `x[6]`。

## 🧪 测试（`test_packed_struct.py` 11 → 18）

新增 7 个：struct 成员位 fanin/fanout、低成员偏移、union 成员、嵌套成员、
**不跨位**、成员总线查询不被劫持。

图基线/CLI golden 无差异（fixture 无 struct 声明；verilog-axi 也无 packed struct）。
缓存 `CACHE_VERSION` 1.3 → **1.4**（旧图缺成员节点）。

## 📌 边界（KNOWN_LIMITATIONS §3.6）

- 更深层成员节点（`o.inner.a`）不会自动创建（查询会空答）；当前补齐只到一层成员
- 成员位桥只处理 **packed struct/union**；非 packed struct 不参与

## 🔗 相关

- 计划: [PLAN.md P12](../../../PLAN.md)
- 前序: [iter_299 packed struct](iter_299_packed_struct.md)
