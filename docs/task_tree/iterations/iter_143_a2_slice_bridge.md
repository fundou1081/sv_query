# Iteration 143: A2 位对位切片偏移桥 — bus↔切片 CONNECTION 位级贯通

**Metadata**:
- **Iteration #**: 143
- **Task Tree Level**: L2 (准确性审计 → A2 残留: 切片/非零 base 偏移映射)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (全量回归见 commit)

## 🎯 本次目标

方豆 "先处理 #3" = iter_137 残留: A2 切片/非零 base 位偏移映射
(.y(y[7:4]) 型 bus↔切片 CONNECTION 仍 bus 粒度)。

## 🔬 实际结果

### 场景 (sub.y[3:0] → top.y[7:4] 输出切片; a[7:4] → sub.a[3:0] 输入切片)

图形态: `u_sub.y -CONNECTION-> top.y[7:4]` (一端 bus 一端切片, 含 [ ]);
iter_137 位桥只处理两端无 [ ] → 切片边跳过; 顶层单 bit 位节点不存在
(RTL 只出现 [7:4] 切片, 无逐位引用) → 位查询提升 bus → bus 粒度。

### 修复 (graph_builder._expand_bus_conn_bit_bridges 第二段)

对一端 bus 一端切片的 CONNECTION (bus 宽度匹配切片范围):
- **声明序低位对齐**: bus[blo+off] ↔ slice[slo+off] (top.y[4+k] ↔
  sub.y[k] — 偏移 4 由切片 lo 表达)
- bus 侧位节点存在才建 (bus 直通无位 → 保持粒度, iter_137 原则)
- 切片侧单 bit 节点缺失则**创建** (真实位 — 由切片连接驱动, 非
  iter_137 "不造假" 所指的 bus 直通假位)
- **不建切片位节点的 BIT_SELECT → base 聚合边**: 实测建了会让 bus
  提升查询 (悬空位 top.y[3] → top.y → BIT_SELECT 子递归) 收到切片位
  驱动 → 污染 (top.y[3] fanin 串入 a[0..3])。位查询经桥可达无需聚合边
- 桥方向 = 原 CONNECTION 方向 (切片 src → bus dst, 反之亦然)
- 宽度不匹配 (leaf 1 位接 2 位切片, iter_136 型) → skip (防错桥)

### 证据

- 输出切片: fanin(top.y[7]) = {a[3], u_sub.a[3]} (偏移 4 ✓); y[4+k]
  逐位不串; 悬空位 top.y[3] = {u_sub.y} (bus 粒度干净)
- 输入切片: fanin(top.u_sub.a[3]) = {top.a[7]} (sub.a[3] ↔ top.a[7] ✓);
  fanin(top.y[3]) = {a[7], u_sub.a[3]} (sub 内 y[3] 贯通到 top.a[7])
- 受影响子集 101 passed; unit +3 (TestA2SliceBridge: 输出偏移逐位 /
  悬空位干净 / 输入偏移); 全量回归见 commit

## 💡 关键发现 / 决策

1. **切片位节点 = 真实位但无聚合边**: 由切片连接驱动的顶层位是真实
   存在的 (应建模), 但建 BIT_SELECT 聚合边会让 bus 提升查询把位驱动
   全收 (悬空位污染) — 聚合边是 bus 级查询的"宽口", 位桥不该开它。
2. **声明序低位对齐映射**: .y(y[7:4]) 中 sub.y[k] ↔ top.y[4+k] (切片
   LSB 对齐 bus LSB); 方向由原 CONNECTION 方向继承。
3. iter_137 "不造假节点" 边界澄清: bus 直通 (assign y=a, 无真实位
   逻辑) 不造位; 切片连接 (每 bit 有真实驱动) 造位 — 两者可区分,
   后者是"补缺失"非"造假"。

## 📌 状态

- ✅ bus↔切片 CONNECTION 位桥 (双向, 偏移映射) — 位级贯通
- ✅ 悬空位无污染; 宽度不匹配不瞎桥; unit +3
- ✅ 受影响子集 101 passed; 全量回归见 commit
- 🗒️ audit L3 #3 残留移除 → A2 位对位 (同构 + 切片偏移) 全闭环
