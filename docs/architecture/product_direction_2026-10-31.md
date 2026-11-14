# 产品方向 — Agent RTL 查询与客观校验层

**日期**: 2026-10-31
**状态**: 方豆拍板方向（未来工作重心）
**主目标**: 服务 agent 的 **RTL debug 与 design 理解**：以 **trace + verify** 为核心，
提供可查询、可验证、可追溯的事实；Scope inventory 是入口/上下文层。

> 本文是产品定位，不是迭代计划；代码计划仍以 [PLAN.md](../../PLAN.md) 为唯一源。

---

## 1. 一句话定位

> **sv_query 是 agent 的 RTL 查询 + 客观校验层。**
> 它不替代源码阅读，而是让“源码阅读的结论”可以被机器验证或反驳。

这意味着两件事同等重要：

1. **查询**：信号驱动/负载、路径、条件、连接、层级、参数、位映射。
2. **校验**：双向一致性、claim 验证、证据定位、显式 unknown/not_found。

---

## 1.1 Scope 层与 Trace/Verify 层

产品明确分成三层，避免把“目录浏览”和“因果分析”混为一谈：

| 层 | 回答 | 定位 | 典型命令 |
|---|---|---|---|
| **Scope / Inventory** | 这个 scope 里有什么？ID 是什么？ | **入口/上下文**，够用即可 | `scope` / `instances` / `hierarchy` / `ports` / `params` / `connections` / `class` |
| **Trace / Causality** | 它从哪来、到哪去、为什么？ | **核心价值** | `drivers/loads` / `paths` / `dataflow` / `controlflow` / `profile` / `evidence` / `lookup` |
| **Verify** | 这个结论成立吗？ | **核心价值** | `verify consistency` / `verify claim` |

工作流：

```
scope 定位候选与 canonical ID
  → trace 追定义/连接/条件/时间
  → evidence 钉源码
  → verify 确认/反驳
```

原则：

- Scope 是入口，不追因果；`connections` 只给 port↔internal 映射，不替代 fanin/fanout；
- Trace/Verify 是主目标与差异化；scope 做到“ID 稳定、interface/generate/class 可发现”即停止扩张；
- capabilities 用 `mode` 标注 `scope|trace|verify|locate|state`。

**实现状态（iter_345）**：`mode`、`scope` 聚合、interface/generate/class 可发现性已落地；scope 功能到此冻结。

### 1.2 验证结论的语义边界 (2026-11-11)

> 2026-11-11 复盘: “门禁全绿”不等于“语义正确”。产品要能对 agent 说
> “这个结论是 verified”，必须先满足 [SEMANTIC_CONTRACTS](../dev/SEMANTIC_CONTRACTS.md)。

- `paths --directed` / `verify claim type=path` 只允许数据边（DRIVER/CONNECTION），
  CLOCK/RESET/BIT_SELECT 不是数据路径；
- `verified` 只能用于完整覆盖、无 unknown/truncated、0 violations 的结果；
  sample/truncated 必须返回 `partial`/`unknown`；
- snapshot 支持范围、确定性、有界搜索、写入安全属于产品契约，不是实现细节；
- 公开能力与证据登记在 [CLAIMS](../dev/CLAIMS.md)；没有 gate 的 claim 只能是 `unverified`。

产品方向不变，但“客观校验层”的**可信边界**由上述契约定义。

## 2. 用户与工作流

### 2.1 Debug（主场景）

```
现象 / 信号
→ 解析 canonical signal（别名/层级/位）
→ fanin/fanout + conditions + precision
→ paths/dataflow（跨模块/跨层）
→ evidence（file:line / always / if / assign）
→ clock/reset/sequential profile
→ 形成 claim
→ verify claim（verified / contradicted / unknown）
→ 下一轮查询
```

特点：

- **迭代式**：一开始无法预知全部信息，需要逐步查。
- **多批次/脚本化**：agent 或脚本会批量调用，再根据结果决定下一批。
- **不要求一次 explain 拿全**：需要可组合、稳定、低成本的原语。

### 2.2 Design 理解

- 实例/层级/端口/参数/连接；
- 时钟/复位域、时序边界；
- 接口/协议角色（未来，启发式必须显式标注）；
- class 的调用链/继承/对象关系（不是内部细节）。

### 2.3 动态 debug 的分工

**波形值由外部工具提取；sv_query 提供关联元数据**：

| 我们提供 | 外部波形工具提供 |
|---|---|
| canonical id + aliases | 时间/采样值 |
| hierarchy path / 参数 | VCD/FST 解析 |
| width / signed / bit_range / parent / member | 值变化 |
| clock domains / reset（极性/同步） | 边沿采样 |
| sequential stage / always block | 时序窗口 |
| source declaration / evidence | — |

因此“动态 debug”不是让我们接波形，而是让 **profile/manifest** 足够稳定、可批量导出。

---

## 3. 产品原则（硬约束）

1. **事实优先于解释**：核心输出是节点/边/条件/文件行；自然语言总结不是 ground truth。
2. **证据优先于断言**：每个结论应能追到 node id + file:line；没有证据就标 unknown。
3. **显式失败/空/歧义**：
   - 未知信号 → `not_found` + 候选；
   - 无驱动 → `drivers=[]` 且明确“无驱动”；
   - 无法判定 → `unknown` / `null` / `truncated`，不能伪装成 false。
4. **双向可确认**：A→B 与 B→A、正向路径与反向路径、端口映射、位映射必须能交叉检查。
5. **可组合原语**：支持多批/脚本查询；不依赖一次性大 explain。
6. **启发式隔离**：风险/协议/审计类结论必须标 `heuristic`，不能与事实同层。
7. **core 只读 + 稳定 JSON**；exp 默认隐藏、不承诺契约。

---

## 4. 非目标（近期明确不做）

| 不做 | 原因 |
|---|---|
| 波形/仿真值提取 | 外部工具负责；我们只提供关联元数据 |
| 函数 inline | RTL 场景函数名 + 源码足够；class 看关系 |
| class 内部细节 | 调 call chain/关系；细节直接看源码 |
| audit / diagnose / view | 完成度低，已降级 exp，默认不提供 |
| 静态 X/四态求解 | 波形可提供值；静态求解成本高、易假阳性 |
| 继续给 exp 扩契约 | 不稳定输出不应冻结 |
| 纯启发式协议/风险评分作为主功能 | 违背“事实优先”，只保留 exp/标注 |
| Coverage generation / `coverage.gen` 作为当前功能 | 当前产品以查询 + 校验为主；coverage 生成是独立验证工作流，若重启，以 sv_query 为基底单开项目 |

### 4.1 Coverage generation 的项目边界（2026-11-14）

目前 sv_query 的重心是 **RTL 查询 + 客观校验**，不是 coverage 生成。
`ControlCoverageGenerator` / `coverage_gen_demo.py` 保留为历史 POC，不进入 core、
不恢复 CLI、不登记为新 claim。

如果未来要做 coverage 生成：

- **以 sv_query 为基底**（复用 query / graph / snapshot / verify 的只读事实层）；
- **单开一个项目**，独立测试、CI、claim 和发布节奏；
- 不把 covergroup 生成逻辑重新塞回本仓库的 core 或默认 CLI。

---

## 5. 现有能力优先级

### 高（继续投入）

- `drivers` / `loads`（fanin/fanout）：位级、条件、多驱动、dynamic/function 标记
- 条件输出（直接边 + 多路径 OR + condition_paths）
- `paths` / `dataflow`：跨模块/跨层根因
- `trace evidence`：源码定位（已稳定化赋值行/always/行号）
- `instances/hierarchy/ports/params/connections`：结构/波形对齐基础
- `graph nodes/edges`：底层 id/关系
- `capabilities` + JSON 契约：agent 入口

### 中（有用但需标注/补强）

- `controlflow analyze/list`：条件分析；L1 化简 + 语法级互斥（P48）
- `impact`：假设验证，risk 是 heuristic
- `snapshot compare`：回归/debug diff
- `stats` / `search`：辅助定位（`stats.modules` 仍空）
- `class`：当前关系查询弱

### 低 / exp

- `audit` / `diagnose` / `view`
- 函数 inline
- class 内部细节
- 协议/风险启发式
- 静态 X/波形集成

---

## 6. 缺口与优先级

### P0 — Grounding（防幻觉底座）

1. **canonical signal identity + aliases + not_found/ambiguous**
   - 规范 id、层级/相对/转义名、generate/interface 路径；
   - 未知信号不能返回 `ok=true, drivers=[]`。
2. **双向一致性检查**
   - fanin/fanout 互逆；正向/反向路径；端口连接；位映射 parent/bit_range。
3. **claim verification**
   - `verify driver / path / connection / bit`；
   - 返回 `verified|contradicted|unknown` + evidence + counterevidence。
4. **证据粒度**
   - 每个 driver/每跳路径的 file:line/表达式，而不只是信号级源码块。

### P1 — 动态 debug 元数据

5. **`trace profile` 批量导出**
   - canonical/aliases/width/signed/bit_range/parent/declaration/
     clock/reset/sequential/source。
6. **clock/reset/sequential profile**
   - clock domain、reset 极性/异步、register stage、always block。
7. **path 条件/segment 元数据**
   - `paths` 也输出条件/段证据（目前 dataflow 有）。

### P2 — 按目标设计补语义

8. **class 关系查询**：继承/方法调用链/对象成员关系（不做内部细节）。
9. **function 调用点/源码元数据**：名字、定义、call site、返回宽度/符号（不 inline）。
10. **批量/会话复用**：稳定 id、批量请求、缓存/延迟优化。

---

## 6.1 P0 进度（2026-10-31）

- ✅ canonical signal identity / aliases / not_found / ambiguous（P33，iter_329）
- ✅ 双向一致性 + claim verification（P34，iter_330）
- ✅ 全图 reciprocity `--full`（P49，iter_350）
- ✅ bit-level structural consistency（P50，iter_351）
- ✅ indexed part-select / multi-top 位选 ID 修正（P51，iter_352）
- ✅ bit parent width 元数据（P52，iter_353）
- ✅ 实例 parameter width（P53，iter_354）
- ✅ generate parameter width 验证（P54，iter_355）
- ✅ generate if/case width 常场景（P55，iter_356）
- ✅ generate if/case 嵌套 generate-for（P56，iter_357）：
  `verify consistency` / `verify claim`，三态 verified/contradicted/unknown
- ✅ trace profile / clock/reset/sequential（P36，iter_332）
- ✅ evidence 粒度到 driver/path（P37，iter_333）

## 7. 成功标准

- agent 的每个 debug 结论都能被 `verify` 判定为 verified/contradicted/unknown；
- 未知/空/歧义不会被误读为“无驱动/无路径”；
- 波形工具可用 `trace profile` 的 canonical/alias/bit/clock/reset/source 信息对齐值；
- 多批脚本查询稳定、可重复、可缓存；
- 启发式结果永不伪装成事实。

---

## 7.5 可视化方向调整（2026-11-02）

全设计图不再作为分析入口：

- 简单设计看图不如读代码；复杂设计全图不可读、不可算；
- `visualize` 全图命令保持 exp/隐藏，并在 P59 清理中退役/归档；
- 图的保留价值是 **core 数据结构**：fanin/fanout、bit consistency、verify；
- 新增方向：**`graph subgraph` 动态子图**（P60）+ **`verify structural` findings**（P61）；
- 图只作为 finding 的**可选局部 review artifact**（P62），必须局部、带证据；
- 交互式 debug 最后做，且有 gate；
- CIRCT/MLIR 架构级建模是独立未来 track，不在本计划。

完整计划：[structural_review_plan_2026-11-02.md](structural_review_plan_2026-11-02.md)

---

## 8. 与现有文档的关系

- 迭代历史与当前计划：[PLAN.md](../../PLAN.md)
- 能力/限制：[KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md)
- 精度矩阵：[trace_capability_review_2026-10-27.md](trace_capability_review_2026-10-27.md)
- JSON 契约：[json_contract_2026-10-31.md](json_contract_2026-10-31.md)
