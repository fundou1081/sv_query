# Iteration 142: interface 多写共享语义 — 诊断闭环 (Claim L3 #2)

**Metadata**:
- **Iteration #**: 142
- **Task Tree Level**: L2 (准确性审计 → iter_129 backlog / Accuracy Claim L3 #2)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 诊断闭环 (7 场景实测无真缺陷 — 语义澄清; 无代码改动)

## 🎯 本次目标

方豆 "继续处理反例里面的 interface 问题" = L3 反例 #2: interface
master+slave 同线多写共享语义 (多实例同时驱动 interface 成员的归属/合并)。

## 🔬 实际结果

### 7 场景实测 (iter_129 单向成员桥现状)

| 场景 | 桥/查询结果 | 判定 |
|---|---|---|
| 1. 双 writer 同驱 bf.addr | u_master.b.addr→bf.addr + u_slave.b.addr→bf.addr; fanin(bf.addr) = {两个 writer 成员} | ✅ 多源集合 (谁写都可能) |
| 2. writer + reader | 单向: u_w.b.addr→bf.addr (写) / bf.addr→u_r.b.addr (读); fanin = {u_w.b.addr} | ✅ 读不反向 |
| 3. writer + top 直驱成员 | fanin(bf.addr) = {a_top (DRIVER), u_w.b.addr (桥)} | ✅ 外部+实例多源 |
| 4. master 写 addr + slave 读 addr 写 data | 各成员方向独立正确; fanin(bf.addr) = {u_m.b.addr} | ✅ 成员级方向 |
| 5. 双写 wdata + 一读 | fanin(bf.wdata) = {u_a1, u_a2}; 读方 u_b 不反向 | ✅ 双写多源 |
| 6. modport master/slave 同成员 | fanin(bf.data) = {u_m.b.data} (方向按 modport 驱动侧) | ✅ |
| 7. 同成员读写 (loop 回读) | fanin(u_l.y) = {b.data, x, top.x} — 回读看到自己写的源 | ✅ 物理正确 (单 loop 器件线只被自己驱动) |

### 结论: iter_129 单向桥已覆盖多写共享语义 — 同 inout (#1) 定性

- **共享成员多写 → 静态可能写方集合** (fanin 已实现, 正确)
- **"归属单点" (协议阶段谁在驱动) 依赖时序/仲裁** — 超出 signal graph
  承诺域 (与 i2c 开漏同构)
- 读方向不反向、成员级方向独立、外部直驱并入 — iter_129 的方向检测
  (实例内部是否有 incoming DRIVER) 在多实例场景全部正确
- **7 场景未发现真缺陷** → 反例 #2 从"待建模"改为"语义澄清闭环"
  (若方豆观察到具体错误现象, 请提供复现, 另立专项)

### 顺带 (Accuracy Claim 文档更新)

Claim 头部 + 各节标注 iter_136~141 演进 (L1: 连接完整性/解码健壮性;
L2: 位对位/控制排除; 语料 3058; CVA6 编译通 + 建图内存边界)。

## 💡 关键发现 / 决策

1. **interface 与 inout 的共享语义同构**: 共享线/成员的"谁在驱动"都依赖
   时序协议 — 静态图统一给**可能源/写方集合**; iter_129 的单向桥 (方向 =
   实际驱动侧) 天然实现此语义, 多实例时逐实例建桥 = 多源正确并列。
2. **成员级方向检测在多实例下正确**: "实例内部有 incoming DRIVER → 写方
   (成员→线), 否则读方 (线→成员)" — 每个实例独立判定, 不互相干扰。
3. 反例表处置模式固化: 语义边界类 (inout/interface 多驱动归属) = 澄清
   闭环; 真缺陷类 (Conversion/位桥/控制信号) = 修复闭环 — 两类都从反例
   表移出并注明。

## 📌 状态

- ✅ 7 场景实测: interface 单向桥多写共享语义正确 (无真缺陷)
- ✅ Claim L3 反例 #2 → 语义澄清闭环 (与 #1 同构); 反例表 3 项 → 2 项
- ✅ Accuracy Claim 文档演进标注 (iter_136~141)
- 无代码改动
