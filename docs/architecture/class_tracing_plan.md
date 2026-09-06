# Class 追踪整体规划 (Plan: class 纳入信号追踪)

> **创建**: 2026-09-05 GMT+8
> **背景**: 方豆方向指示 — 项目 focus = 信号追踪 (可视化后置); 追踪范围 =
> 可综合 RTL + **class / constraint** (covergroup 单独后议)。
> **状态**: 规划稿, 待方豆确认迭代顺序。

---

## 1. 目标语义 (用户问题形态)

追踪 class/constraint 时, 用户最想回答的问题 (与 RTL 信号追踪同构):

| # | 问题 | RTL 对应 |
|---|---|---|
| Q1 | 这个 class 实例属性**谁驱动** (含方法调用赋值)? | fanin(信号) |
| Q2 | 属性驱动到哪 (fanout: 谁用了这个属性)? | fanout |
| Q3 | 实例属性 (top.p.addr) 与**类型定义** (packet.addr) 的关系 | 类型↔实例 |
| Q4 | rand 属性受**哪些约束**? 约束引用哪些变量? | 约束语义查询 |
| Q5 | 方法调用点 (p.set(x)) 实参 → 方法体 → 成员赋值的完整链 | 调用展开 |

## 2. 现状地图 (2026-09-05 实证)

| 域 | 状态 | 证据 |
|---|---|---|
| **class 图结构** (CLASS/CLASS_PROPERTY/CLASS_INSTANCE/CLASS_INSTANCE_PROPERTY) | ✅ 建模完整 (pipeline 步骤 + _resolve_class_member_access) | test_class_oop_truth (1:1 节点/边集), golden_dataflow_35 |
| **约束建模** (CONSTRAINT_BLOCK/IF/EXPR + CONSTRAINS/HAS_*/SUPER_CALL) | ✅ 图内 (class_graph_builder) | 约束边族 + 继承约束传播 |
| **方法体成员赋值** (data = addr → DRIVER 边) | ✅ iter_075 #41-43 | packet.addr→packet.data DRIVER |
| **实例属性直接驱动** (p.addr<=din) | ✅ | fanin(top.p.addr) = {din} |
| **类型级属性** (packet.addr CLASS_PROPERTY) | ⚠️ 节点在图, 无驱动语义 (模板) — 需类型级查询 | fanin(packet.addr) 空 (合理, 无查询入口) |
| **class 方法调用链** (p.set(din+1) → data) | ❌ **断** | fanin(top.p.data) 空 — 实参→形参→方法体未串 |
| **实例↔类型桥** (p.addr ↔ packet.addr) | ❓ 无显式查询 | — |
| **rand/约束关系查询** | ❌ 无专用 API (CONSTRAINS 边在, 无查询) | — |
| **GenericClassDef (参数化 class)** | 🛡 iter_145 防崩 (跳过) | — |

## 3. 差距清单 (按迭代路线)

| # | 差距 | 现状 | 建议工作量 |
|---|---|---|---|
| **G-B** | class 方法调用展开 (p.set(x) 实参→形参→方法体→成员) | fanin(top.p.data) 空 | 中 (SubroutineExpander 扩 class 方法 / 类 MemberAccess 调用) |
| **G-C** | 实例↔类型级桥 (CLASS_INSTANCE_PROPERTY ↔ CLASS_PROPERTY) + 类型级查询语义 | 有节点无查询 | 中 |
| **G-D** | constraint 语义查询 (rand 属性受哪些约束 / 约束引用变量 / 继承约束链) | CONSTRAINS 边在无 API | 小-中 (查询层, 非数据 fanin) |
| **G-F** | 查询层 class kind 全面处理 (fanin/fanout 遇 CLASS_PROPERTY/CLASS_INSTANCE_PROPERTY/CONSTRAINT_BLOCK 的行为定义) | 部分 (REG 化实例属性已通) | 中 |
| **G-E** | 继承链建模完整化 (extends 属性/约束的实例级表现) + GenericClassDef 建模 | 类型级传播有; 泛型跳 | 小 |
| **G-A** | Accuracy Claim 范围: class/constraint 从 hybrid 例外域转正 (追踪域) | Claim 现标 hybrid 不承诺 | 文档 (class 稳定后) |

## 4. 建议迭代路线 (每迭代 = 可验证产出)

| 迭代 | 内容 | 验收 (测试) |
|---|---|---|
| **C1** | **class 方法调用链** (G-B): 实例方法调用点实参→方法体形参→成员赋值 DRIVER | unit: p.set(din+1) → fanin(p.data) 含 din; 真实验证: 现有 class fixture 升级 |
| **C2** | **实例↔类型级桥 + 查询语义** (G-C): p.addr ↔ packet.addr 双向; CLASS_INSTANCE_PROPERTY 归一 | truth 更新 (类级查询集) |
| **C3** | **constraint 语义查询** (G-D): trace_constraints(prop) → 约束块/引用变量; rand 标注 | unit: 约束链断言 |
| **C4** | **查询层 class kind 全处理** (G-F) + 继承/泛型收尾 (G-E) | fanin/fanout 对 class 各 kind 行为锁定; truth +N |
| **C5** | **声明转正** (G-A): Accuracy Claim 更新 (class/constraint 追踪域, 反例/范围调整); 文档 | 文档 + 全量回归 |

**依赖**: C1 独立优先 (最大缺口); C2 依赖 C1 的实例语义; C3 独立; C4 收束;
C5 最后。covergroup 单独规划 (方豆)。

## 5. 风险 / 注意事项

- **语义决策点** (需方豆拍板):
  1. class 方法调用是否**展开进图** (像 module task/function iter_076) vs
     只建"调用边" (调用点→方法, 粒度链)? 展开 = 数据链完整; 边 = 图小。
  2. 类型级 (packet.addr) 是否作为**追踪端点** (用户可查类型级驱动 = 所有
     实例的并集?) vs 仅结构参考。
  3. rand/constraint 的"驱动"语义: 约束不是数据驱动 — 用**专用查询**而非
     fanin (避免污染数据语义, iter_139 控制信号同原则)。
- **hybrid 域声明**: 现在 Accuracy Claim 说 class/constraint 是例外域 —
  转正过程逐步更新, 不一次性 (防过度承诺)。

## 6. 关联文档

- Accuracy Claim: [signal_graph_accuracy_audit.md](signal_graph_accuracy_audit.md)
- class 结构实现: class_graph_builder.py / unified_tracer._resolve_class_member_access
- iter_075 (#41-43 方法赋值) / iter_121-122 (对抗: sva/constraint/covergroup 提取)
- iter_145 (GenericClassDef 防崩)
