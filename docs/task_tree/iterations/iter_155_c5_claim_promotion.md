# Iteration 155: C5 Accuracy Claim hybrid 域转正 — class/constraint 追踪域

**Metadata**:
- **Iteration #**: 155
- **Task Tree Level**: C5 (class 追踪迭代收尾 — 声明转正)
- **Parent Task**: [class_tracing_plan.md](../../architecture/class_tracing_plan.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (无代码改动; 全量 3085 passed)

## 🎯 本次目标

C5: class/constraint 从 Accuracy Claim "hybrid 例外域" 转正为**追踪承诺域**
(C1~C4 稳定后声明)。

## 🔬 实际结果

### 更新 (signal_graph_accuracy_audit.md)

- 头部演进: iter_151~155 class 转正轮
- 建模决策表: +class 类型级 (D3 结构宿主非数据端点, fanin 空 = 设计) /
  +class 约束 (声明式关系独立 tracer, 不走 fanin)
- L1: class 结构建模 (类型/实例属性/约束图/方法链) + 同名冲突显式告警
- L2: +class 实例属性数据流 (直接赋值 + 方法调用链) / 类型↔实例关系 /
  约束查询 — 类型级 fanin 空 = 设计 (D3)
- 语义域: class/constraint 转正; 仍例外: covergroup (单独规划) / SVA /
  procedural / inline 约束

### README 同步

- 为什么用 sv_query: +class/constraint 追踪 (方法链/关系/约束查询)
- Accuracy Claim 表: 追踪范围注 (RTL + class; covergroup 单独; 可视化后置)

### 验证

- 主全量 (class C1~C4 改动后): **3085 passed** (3071 + 14 class unit),
  唯一 fail [serv] = HOME env 假失败 — 零代码回归
- C1~C5 全闭环, class 追踪域声明转正 (D1~D5 架构决策兑现)

## 📌 状态

- ✅ Accuracy Claim class/constraint 转正 (文档)
- ✅ README 同步; 全量 3085 passed
- class 追踪路线 C1~C5 完成; covergroup 后续单独规划
