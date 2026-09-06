# 架构决策: class/constraint 纳入信号追踪 — 图模型与查询架构

**时间**: 2026-09-05 22:30 GMT+8 (讨论 2026-09-05, 方豆逐点对齐后落档)

**遇到的问题**: 方豆方向指示 — 项目 focus 信号追踪 (可视化后置), 追踪范围
从可综合 RTL 扩展至 **class / constraint** (covergroup 单独后议)。现 class
节点已部分入图 (CLASS/CLASS_PROPERTY/CLASS_INSTANCE/约束边族), 实例属性
被 RTL 读写时已"信号化"贯通 (fanin(out) 穿越 p.data), 但: ①class 方法调用
链断 (p.set(x)→属性无驱动) ②约束/类型级无查询入口 ③查询层对 class kind
语义未定义。架构上如何扩展, 以**未来可维护性**为第一裁判。

**考虑约束 (实证)**:
- RTL ↔ class 实例属性物理贯通已工作且正确 (fanin(top.out) = {din, p.data};
  fanout(din) 含 p.addr/p.data) — 拆隔离会破坏它
- module task/function 调用 = 展开进图 (iter_076 SubroutineExpander) —
  项目既有调用语义先例
- 类型级节点 (packet.*) 在 target=top 时未被 filter_by_target 过滤 —
  未定义行为, 需定规则
- 约束是声明式关系 (CONSTRAINS/HAS_* 边已建), 非数据流 — iter_139 原则:
  控制/关系语义不混入数据 fanin

---

## 决策点 (每点: 方案 / 利弊 / 决策)

### D1. 图承载模型 — 单图分层 (vs 隔离 ClassGraph)

| 方案 | 利 | 弊 |
|---|---|---|
| A. 单 SignalGraph 混合 (类型级+实例级+RTL) | 图基础设施一份 (路径/缓存/序列化/truth/可视化); class↔RTL 贯通天然 | 查询层需按 kind 分层语义 (风险: 分支散落) |
| B. 独立 ClassGraph | 语义隔离干净 | 两套 graph 基建/测试/缓存; class↔RTL 贯通需维护桥代码 — 维护成本翻倍 |

**决策**: A (单图分层)。kind 分支集中在**查询分派层**, 不散落 signal.py。
**理由 (维护性)**: 单一图基础设施 + 语义模块化; B 的双基建成本与桥维护
是长期债, 且破坏已工作贯通。

### D2. 方法调用机制 — 复用 SubroutineExpander 展开 (vs 调用边+查询解析)

| 方案 | 利 | 弊 |
|---|---|---|
| A. 复用 expander 展开进图 (扩 class callee) | 一套调用语义 (module 先例); 展开/递归守卫已有雏形; 数据链完整 | per-call-site 图边增; expander 本身复杂 |
| B. 调用边 + 查询时解析 | 图小稳定 | **第二套调用语义** (module 展开 vs class 解析) — 两套逻辑/debug/测试; 查询器复杂化 |

**决策**: A。class 方法 (MemberAccess callee) 走 expander, 形参←实参、
this←实例绑定, 展开落实例属性。
**理由 (维护性)**: 一致性 — 一个调用机制一处维护; B 的"两套调用语义"是
典型维护债源。

### D3. 类型级语义 — 结构宿主 (vs 聚合所有实例)

| 方案 | 利 | 弊 |
|---|---|---|
| A. 类型级 (packet.data) = 结构宿主 (方法/约束载体), 非数据端点; 数据端点 = 实例级 (top.p.data) | 语义单一; 无聚合/去重逻辑; truth 稳定 | 用户不能直接查类型级"驱动" (需经实例) |
| B. 类型级查询 = 所有实例并集 | 直接答类型级 | 聚合逻辑+去重+多实例性能; truth 随实例数变 — 脆弱 |

**决策**: A。方法赋值展开时落到实例属性; 类型级保留结构 (约束/方法/继承)。
**理由 (维护性)**: 无聚合债, 语义单一清晰; B 的实例数敏感 truth 是未来债。

### D4. 约束/rand 查询 — 独立 tracer (vs 混入 fanin)

**决策**: 新建 `query/constraint.py` tracer (trace_constraints(prop) → 约束
块/引用变量/继承链), 遍历 CONSTRAINS/HAS_* 边; 不走数据 fanin。
**理由 (维护性 + 可扩展)**: 约束 = 声明式关系非数据流 (iter_139 原则);
独立 tracer 职责单一; **范式可复用于未来 covergroup/SVA 关系查询**
(query/covergroup.py 同 pattern) — 新域只加不改。

### D5. kind 守卫与 namespace — 集中化

**决策**:
- graph 提供集中 helper (`is_data_node(kind)` / `is_class_structural(kind)`),
  查询层调用 — 收口现在 signal.py 已开始分散的 kind 判断
- **namespace 规则落文档**: class 类型级节点 (packet.*) = 全局定义 (与
  module 定义同级), 实例节点 (top.p.*) 在 target 树内; filter_by_target
  显式保留类型级 (结构需要) — 消除当前"未定义行为"
**理由 (维护性)**: 一处定义, 扩展新域 (covergroup/SVA) 只加不改。

---

## 架构原则 (汇总, 供后续迭代执行)

1. **图基础设施单一**: 单 SignalGraph (类型级 + 实例级 + RTL 同图)
2. **语义按 kind 分派到独立 tracer**: signal (数据流) / constraint (关系)
   / future: covergroup — signal.py 不膨胀
3. **调用机制复用 module 先例**: expander 展开, class 方法同机制
4. **类型级 = 结构宿主; 实例级 = 数据端点**
5. **关系查询独立 API** (不污染数据 fanin)
6. **kind 守卫集中 + namespace 规则文档化**

## 影响 / 关联

- **Accuracy Claim**: class/constraint 追踪域稳定后 (C 迭代), hybrid 例外
  域声明收窄 (class 转正; covergroup/SVA 仍例外) — C5
- **迭代路线** (class_tracing_plan.md): C1 (方法展开, 按 D2) → C2 (实例↔
  类型桥/查询语义, 按 D3) → C3 (约束 tracer, 按 D4) → C4 (kind 收束 +
  namespace, 按 D5) → C5 (声明转正)
- **可视化后置**: 单图模型预留 (class 节点可渲染), 不投入

## 遗留 / 风险

- expander 展开的图膨胀 (多调用/递归): 沿用现有 depth/seen 守卫, 超限
  显式降级 (不静默)
- class 方法体对实例状态 (p.data) 展开 vs 类型级共享: 展开 = 复制 DRIVER
  到实例属性 — 图略增, truth 更新随 C1 验证
- 本决策不覆盖 covergroup (后置单独规划, 可套 D4 范式)
