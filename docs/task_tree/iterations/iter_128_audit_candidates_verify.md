# Iteration 128: 审计待验证候选实测 — 2 修复 + 2 缺口登记 + 1 预期确认

**Metadata**:
- **Iteration #**: 128
- **Task Tree Level**: L2 (signal graph 准确性审计 → 待验证候选)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-04 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (2 修复 / 2 缺口登记 / 1 预期确认)

## 🎯 本次目标

方豆 "继续验证吧" — 实测审计文档 🔭 待验证候选 5 项, 判定每项正确性,
能修的小缺口直接修, 建模级缺口登记待决策。

## 🔬 实际结果

### 候选逐项判定

| 候选 | fixture | 结果 |
|---|---|---|
| 1. inout 双向端口 | bidir_io + top inout sda | 🐛 缺口: PORT_INOUT kind 正确, 但 connection_extractor 只有 input/output 分支 → inout 无跨模块连接边, top.sda ↔ u_io.sda 无桥, fanin(top.sda) 空答 |
| 2. struct 字段 | pkt_t {addr,data} + assign p.addr=a | ✅ 字段驱动正确; 连带发现 A2 提升 bug → 修 (见下) |
| 3. interface/modport | bus_if + slave modport | 🐛 缺口: 整体 CONNECTION (top.bf→u_slv.b) 有, 成员级无桥 (bf.addr ← writer.b.addr 断); bf.addr fanin 含 top.clk 假驱动 (BIT_SELECT 提升串扰) |
| 4. 派生时钟/多时钟域 | clkdiv→div2→cnt_b | ✅ CLOCK/RESET 边提取正确; 连带发现 fanin 假驱动 → 修 (见下) |
| 5. 顶层输入 fanin | input a | ✅ 预期: fanin 空 + confidence uncertain (外部驱动图内无源) — 测试锁定 + 文档化 |

### 修复 1: fanin CLOCK/RESET 边守卫

- **现象**: `fanin(top.cnt_b)` 含 top.clk (假驱动)。cnt_b<=cnt_b+1 数据驱动只有自身。
- **根因**: fanin 主循环 line ~349 "其他边类型继续递归追溯" 对 CLOCK/RESET 也递归 —
  跨模块时钟链 cnt_b ←CLOCK div2 ←CONNECTION u_div.clk ←CONNECTION top.clk 被当数据源追。
  隔离单模块场景不泄漏 (top.clk PORT_IN 无前驱不进结果), 有中间模块 (u_div) 时经
  PORT_IN via CONNECTION 分支 (无前驱 → append) 泄漏。
- **修复**: 主循环对 `edge.kind in (CLOCK, RESET)` 直接 continue (时序采样非数据驱动,
  不 append 不递归)。数据用 clk (`assign out=clk`, DRIVER continuous) 不受影响。

### 修复 2: A2 位提升条件修正

- **现象**: `fanin(top.p.addr)` 含 top.d (struct 兄弟字段泄漏)。
- **根因**: A2 提升条件 `not drivers` — drivers 在下方主循环**之前**几乎恒空
  (forward-lookup 是少数例外), 根查询有直接 DRIVER (p.addr←a) 也误提升, 沿 BIT_SELECT
  出边升到父 struct p → 把 p.data 驱动带回。
- **修 2a**: 条件改 `not has_driver_edge` → struct 修复, 但引入新回归:
  `test_multiple_bit_select_same_signal` — always_comb if/else 位选 (y=data[7]|data[0]),
  递归追 data[7] 自身驱动时 (顶层输入位, 无 incoming → has_driver_edge=False) 误提升到
  父总线 data → 其 BIT_SELECT 子节点探索 seen 污染兄弟位 data[0] → y 主循环真源被过滤
  (fanin(y) 丢 data[0])。
- **修 2b (终版)**: `not has_driver_edge and not drivers` — 有直接驱动不升 (字段),
  递归中间不升 (输入位 data[7] 被追时 drivers 已含它)。4 场景验证:
  struct p.addr→[a] ✓ / struct p→[a,d] ✓ / bitselect y→[data[0],data[7]] ✓ /
  out-bit y[0] 提升→[u_sub.y] ✓ / A2 top.y[3]→[u_sub.y] ✓

### 验证

- 新增 unit 8 (test_accuracy_a1_a2.py TestAuditCandidates: struct 不泄漏 / CLOCK 不假驱动 /
  assign out=clk 保留 / 顶层输入预期空)
- 全量回归: **2921 passed / 0 failed / 0 skipped** (2913 + 8 新)

## 💡 关键发现 / 决策

1. **CLOCK/RESET 边不是数据驱动源** — fanin 语义是"谁驱动这个信号的数据", 时序采样
   关系不该混入。图结构保留 CLOCK 边 (时钟域分析/可视化用), 查询层过滤。
2. **A2 位提升的边界 = 无直接驱动 且 非递归中间**: 两个条件缺一不可 —
   - 只查 drivers (iter_126 原版): 根查询有 direct DRIVER 也提升 → struct 字段泄漏
   - 只查 has_driver_edge: 递归中间位 (作为别的信号的源被追) 也提升 → 兄弟 seen 污染
   "drivers 非空" 恰好标记"我是作为源被递归进来的中间节点"。
3. **inout / interface 成员级连接是建模缺口** (非小修): 涉及双向驱动归属 / modport
   方向传播语义, 需方豆拍板方案后修 — 登记 audit + CURRENT_TODO backlog。

## 📌 状态

- ✅ 候选 2/4 修复 + 候选 5 预期锁定; 候选 1/3 缺口登记
- 全量 2921 passed / 0 failed
- backlog: inout 跨模块连接建模 / interface 成员级连接建模 (待决策)
