# Iteration 138: inout 多驱动归属 (i2c 开漏) — 诊断 + 方案候选

**Metadata**:
- **Iteration #**: 138
- **Task Tree Level**: L2 (准确性审计 → iter_129 backlog / Accuracy Claim L3 #1)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: 🚧 诊断完成, 方案待方豆拍板 (未动代码)

## 🎯 本次目标

方豆 "继续" → B: iter_129 登记 backlog "i2c 开漏 inout 双向多驱动归属
(外部+实例同时驱动哪边算源)"。先诊断现状行为, 产出归属规则方案供拍板。

## 🔬 实际结果

### 场景实测 (iter_129 单向 output 式建模现状)

| 场景 | 现状 fanin(top.sda) | 判定 |
|---|---|---|
| 2. 双器件 (master+slave) 三态同线 | {data_m, data_s, en_m, en_s, u_master.data, u_slave.data} — **两个器件的真源都在** (多源集合) | ✅ 合理 (总线多驱动 = 多源) |
| 3. top 驱动 + reader 只读 (assign rd=sda) | {top.clk} — 外部源追到, **无反向污染** (reader 不冒充源) | ✅ iter_129 "不建 input 式" 生效 |
| 5. top 读 y_rd=sda + 实例驱动 | {data_io, en_io, sda, u_io.data} | ✅ 穿透正确 (含直接驱动 sda 线) |
| 6. 2 级 inout 级联 (bus_dev→core_io) | {data, en, u_dev.data, u_dev.en, u_dev.u_core.data} | ✅ 深层穿透逐级 |
| 4. 外部三态 + 实例三态同线 | {data_ext, data_io, **en_io**, u_io.data} — **en_ext 缺 / en_io 进** 不对称 | ⚠️ 小缺陷 (见下) |

### 关键结论 1: iter_129 的"多驱动归属"本质 = 语义边界, 非连接 bug

开漏总线 (多器件 + 上拉) 物理上"谁在驱动"取决于**运行时 en 状态** —
RTL 静态图只能给"**可能驱动方集合**"。现状 fanin 已天然是此语义
(场景 2/4/6 多源并列)。"归属到单点"需要时序/状态知识 → **超出 signal
graph 承诺域**。应在 Accuracy Claim L3 #1 澄清 (保留反例, 但定性为
语义边界而非缺失), 而非"修复归属"。

### 关键结论 2: en (三态使能) 与 data 混入 fanin 的不对称杂音 (场景 4)

driver_extractor 三态建模: data → sda **DRIVER/continuous (condition=
'en')**; en → ternary 节点 BRANCH_CONDITION → BRANCH_RESULT → sda。
fanin 主循环对非 DRIVER/CONNECTION 边 fallthrough 递归 → BRANCH 链被
追 → en 类控制信号部分场景进结果 (en_io 进), 部分不进 (en_ext 缺 —
起点 top.sda 递归序/seen 差异)。同类: iter_128 已把 CLOCK/RESET 从
fanin 数据源排除 — en (三态门控) 与 CLOCK 同性质 (控制非数据)。

## 💡 方案候选 (供方豆拍板, 未实施)

| 方案 | 内容 | 收益 | 代价/风险 |
|---|---|---|---|
| **1. 语义文档化 (零代码)** | Accuracy Claim L3 #1 改写: inout 多驱动 = 静态可能源集合 (已实现语义); en 杂音记已知小缺陷 | 澄清承诺边界, 零回归风险 | 无代码改进; 用户仍见 en 杂音 |
| **2. en 从 fanin 排除 (推荐)** | 三态 assign 的 condition 源 (BRANCH_CONDITION 上游控制信号) 不 append 为数据源 — 与 iter_128 CLOCK/RESET 同规则; en 保留在 DRIVER.condition 字段 + BRANCH 边 (fanin_detailed 可见) | 场景 2/4/6 结果干净 (去 en 杂音); "谁驱动"答数据源 | 需查既有 ternary/conditional truth 是否锁"fanin 含条件信号" (可能破, 需同步) |
| **3. 多驱动标注** | fanin_detailed 对 >1 真源 + 含三态的结果加 open-drain 多驱动标记 | 用户可识别"多驱动总线" | 改动中等; 语义受益小 |

**推荐**: 方案 1 + 2 组合 — 文档澄清 + en 杂音修复 (小、规则一致)。
等方豆拍板后实施 (若选 2 需先跑 conditional truth 影响面)。

## 📌 状态

- ✅ 6 场景实测: iter_129 单向建模覆盖 i2c 主要形态 (多源/穿透/方向)
- ✅ 定性: "多驱动归属" = 静态语义边界 (可能源集合), 非连接缺失
- ✅ 发现小缺陷: 三态 en 控制信号 fanin 不对称杂音 (场景 4)
- 🚧 方案 1+2 推荐, 待方豆拍板 (未动代码)
