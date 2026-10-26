# Iteration 299: packed struct/union 宽度、signedness 与成员布局（PLAN P11）

**Metadata**:
- **Iteration #**: 299
- **Task Tree Level**: L2（[L1_packed_struct](../tasks/L1_packed_struct.md) / PLAN `P11`）
- **Created**: 2026-10-26 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "做 packed struct 这个，算术逐位先不做"）
- **Outcome**: ✅ 完成（聚合 + 成员；2482 passed）

## 🎯 问题

typedef 用户类型（packed struct/union）在 syntax 层没有宽度：
`pkt_t p;` 的节点宽度是 `(1,0)`，signedness 也丢失；成员 `p.a` 同样 (1,0)。

## 🔧 P11.1 聚合宽度/signedness

| 来源 | 实现 |
|---|---|
| 语义符号 | `type.bitWidth` / `type.isSigned`（TypeAliasType → canonicalType） |
| 变量声明 | `get_variable_symbols`（name → VariableSymbol），`create_var_nodes` 优先用语义符号 |
| net / 端口 | `extract_data_width` / `extract_port_width` 的 `bitWidth` 回退 |

效果（含嵌套）：

| 声明 | 修复前 | 修复后 |
|---|---|---|
| `struct packed {logic[3:0] a,b} p` | `(1,0)` | `(7,0)` unsigned |
| `struct packed signed {logic[3:0] sa}` | `(1,0)` | `(3,0)` signed |
| `union packed {logic[7:0]; logic[1:0][3:0]}` | `(1,0)` | `(7,0)` unsigned |
| `struct packed {pkt_t inner; logic[3:0] c}` | `(1,0)` | `(11,0)` |
| 结构体端口 / wire | `(1,0)` | 同上 |

## 🔧 P11.2 成员布局

`get_packed_member_layout(symbol)`：从 `canonicalType.syntax.members` 取成员名，
`lookupName(name)` 得 `FieldSymbol.bitOffset` / `type.bitWidth` / `isSigned`。

`GraphBuilder._apply_packed_member_layout`（所有 pass 结束后运行）：
- 重新扫描图里的 `parent.member` 节点（成员节点可能由后续 pass 建出）
- 用语义 `hierarchicalPath` 匹配父变量
- 修正成员节点：`width`、`is_signed`、`parent`、`parent_bit_start/end`
  （struct：首成员在 MSB；union：所有成员 offset=0）

效果：

| 成员 | 修复前 | 修复后 |
|---|---|---|
| `p.a`（struct 首成员） | `(1,0)` | `(3,0)`，父 p，位段 [7:4] |
| `p.b` | `(1,0)`/None | `(3,0)`，位段 [3:0] |
| `pu.u8`（union） | `(1,0)` | `(7,0)`，位段 [7:0] |
| `o.inner`（嵌套） | `(1,0)` | `(7,0)`，位段 [11:4] |
| `sp.sa` | `(1,0)` | `(3,0)`（成员自身 logic unsigned） |

## 📌 附带修正

- `extract_data_width` 标量约定保持：变量标量 `(1,0)`、net/端口标量 `(0,0)`
  （避免改动既有图基线；首版误把端口也归一成 `(1,0)`，被基线测试抓住）
- `CACHE_VERSION` 1.2 → **1.3**（旧图 struct 宽度错误）
- CLI golden 中 `uart_top.rx_fifo.count_q` 宽度由 `1` 修正为 `5`（真实 `[4:0]`），
  3 个 golden **有意重生成**（`--width-min 2` 现在正确包含它）

## 🧪 测试（`test_packed_struct.py`，11 个）

- 聚合：struct/union/signed/nested/net/端口/JSON 往返
- 成员：struct 位段（MSB 优先）、union 重叠、嵌套成员、成员 signedness

## 📌 边界（KNOWN_LIMITATIONS §3.6）

- 成员**位级**查询（`fanin(p.a[1])` → `p[5]`）仍粗粒度：成员没有 BIT_SELECT 桥
- 更深层成员节点（`o.inner.a`）若未在图里不会被创建
- 有符号算术/比较语义、integer 算术逐位仍不做

## 🔗 相关

- 计划: [PLAN.md P11](../../../PLAN.md)
- 前序: [iter_298 integer 宽度](iter_298_integer_width.md)
