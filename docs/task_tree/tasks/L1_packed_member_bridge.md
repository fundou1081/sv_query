# L1 — packed 成员位级查询桥（PLAN P12）

**Status**: ✅ 完成（P12.1~P12.3，iter_300）
**Created**: 2026-10-26

## 目标

`p.a[1]` 与聚合位 `p[5]` 等价：fanin/fanout 都按 parent 链换算位，
并补齐未被引用的成员节点（否则查询不可达）。

## 验收

- [x] `fanin(p.a[1])` → `{x[5]}`（struct a 在 [7:4]）
- [x] `fanout(p.a[1])` → `{y[5]}`（不再错位到 p[1]）
- [x] `fanout(p.b[2])` → `{y[2]}`
- [x] union 成员 `pu.u8[5]` → `pu[5]`
- [x] 嵌套 `o.inner[1]` → `o[5]`
- [x] 不跨位（p.a[1] 不含 x[4]/x[6]）
- [x] 成员总线查询不被位桥劫持
- [x] 全量门禁 2489 passed

## 非目标（已登记）

- 更深层成员节点（`o.inner.a`）自动创建
- 非 packed struct
