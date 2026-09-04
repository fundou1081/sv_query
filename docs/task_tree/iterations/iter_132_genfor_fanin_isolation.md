# Iteration 132: generate per-entry fanin 位隔离 (wrapper cross 守卫 + 提升条件)

**Metadata**:
- **Iteration #**: 132
- **Task Tree Level**: L2 (准确性审计 → per-entry 位隔离)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

推进 A2 位对位折算 (审计 A2 登记后续项) 前的诊断 — 发现 generate per-entry
场景 fanin 位查询**串扰** (比粒度粗更严重的错误答案), 修复隔离。

## 🔬 实际结果

### 诊断: fanin(top.y[3]) 串入全部 generate entry

fixture: top generate-for 4 个 leaf (G[0..3]), `leaf u_leaf(.a(a[i]), .y(y[i]))`。

图结构**正确**:
- top.y[3] ← CONNECTION top.G[3].u_leaf.y (PORT_OUT) ✓
- top.G[3].u_leaf.y ← DRIVER top.G[3].u_leaf.a (leaf 内部 assign y=a) ✓

但 `fanin(top.y[3])` = [G[0].u_leaf.y, G[1].u_leaf.a, G[2].u_leaf.a,
G[3].u_leaf.a, a[1], a[2], a[3]] — 串入 G[0]/G[1]/G[2] + 其他位源。
正确答案应只含 G[3] 链。

### 双根因 (iter_132)

**根因 1 — A2 位提升条件只看 incoming DRIVER** (query/signal.py ~183):
位节点 top.y[3] **存在**且有 incoming CONNECTION (来自实例输出 PORT_OUT
G[3].u_leaf.y, 真实驱动源) 时, `not has_driver_edge` 仍为真 → 触发提升到
父总线 top.y → 4 个 entry 全串。

修: 提升条件加 `not _has_incoming_conn` — 位节点有 incoming CONNECTION 是
"有真实驱动源"的位, 应走主循环 CONNECTION/PORT_OUT 处理而非提升。
提升只用于**完全无 incoming** 的叶子位。

**根因 2 — PORT_OUT via CONNECTION 的 wrapper cross-instance 展开无条件**
(query/signal.py ~340): 设计意图注释写明 "wrapper (0 internal driver) 才跨"
(axi_dp_ram.a_if ← b_if deep driver 场景), 但实现未检查 src 是否有内部
驱动 → leaf 4 实例共享 short-name 'leaf.y', 全跨 → 串扰。

修: cross 前检查 `_src_has_internal_driver` (incoming DRIVER, assign_type !=
"internal") — 有内部驱动的端口 = 真实逻辑实例 (leaf), 无 wrapper passthrough
语义, 不跨; 0 internal driver 的 wrapper 端口仍跨。

### 证据 (修复后)

- `fanin(top.y[i])` = 恰 `[top.G[i].u_leaf.y]` (i=0..3, 全隔离) ✓
- 逐层可追: y[3] → G[3].u_leaf.y → [G[3].u_leaf.a, top.a[3]] → G[3].u_leaf.a
  → [top.a[3]] → [] (顶层输入无源, 预期)
- bus fanin(top.y) 仍聚合 4 entry ✓ (隔离不伤聚合)
- A2 原始场景全保: 纯直通 fanin(top.y[3]) → [u_sub.y] (bus 粒度);
  xor → [a, b]
- wrapper 场景 (outer u0/u1, 无内部驱动) 不误伤: fanin(u0.y) 不跨 u1

### 验证

- 新 unit 3 (TestGeneratePerEntryFaninIsolation: bit 隔离 / bus 聚合保持 /
  wrapper cross 不误伤)
- 全量主回归: **2934 passed / 0 failed / 0 skipped**

## 💡 关键发现 / 决策

1. **"有 incoming CONNECTION" ≠ "无驱动"**: A2 提升条件 (无 DRIVER 即提升)
   忽略实例输出 CONNECTION 这条真实驱动路径 — per-entry 位节点存在且有
   CONNECTION 时必须走主循环 PORT_OUT 处理。
2. **wrapper cross 是设计意图明确但实现漏检查的特例**: 注释已写
   "wrapper (0 internal driver) 才跨", 实现无条件跨 — 同类 bug 的又一例
   (注释与实现漂移)。有内部驱动的端口 = 真实逻辑, 无 passthrough 语义。
3. 隔离修复后 per-entry 位查询逐层可追 (y[3]→G[3]→a[3]→无源) — 位对位
   折算的"链可达"已基本成立, 剩纯直通 (assign y=a 无 per-bit) 的 bus 粒度
   提升为位粒度 (仍需图构造层展开或表达式位对齐传播, 继续 backlog)。

## 📌 状态

- ✅ generate per-entry fanin 位隔离 + unit 3; 全量 2934 passed
- A2 位对位折算: per-entry 场景已逐层可达; 纯直通 bus 粒度提升 (位对位
  展开) 仍在 backlog (审计文档 A2 粒度说明)
