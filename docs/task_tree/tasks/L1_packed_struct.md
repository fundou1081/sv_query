# L1 — packed struct/union 宽度、signedness、成员布局（PLAN P11）

**Status**: ✅ 完成（P11.1~P11.3，iter_299）
**Created**: 2026-10-26

## 目标

typedef 的 packed struct/union 在 syntax 层没有宽度/signedness；用语义符号补齐，
并修正成员节点（`p.a`）的宽度与父聚合位段。

## 验收

- [x] struct/union/signed struct 聚合宽度 + signedness（含嵌套）
- [x] 结构体端口 / wire / 变量声明一致
- [x] 成员布局：宽度、signedness、parent、parent_bit_start/end（MSB 优先；union 重叠）
- [x] JSON 往返保留
- [x] 图基线零差异（标量约定保持）；CLI golden 有意重生成（count_q 宽度修正）
- [x] 全量门禁 2482 passed

## 非目标（已登记）

- 成员位级查询桥（`p.a[1]` → `p[5]`）
- 深层成员节点自动创建
- 有符号算术/比较、integer 算术逐位
