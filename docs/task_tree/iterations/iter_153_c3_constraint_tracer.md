# Iteration 153: C3 constraint 语义查询 — ConstraintTracer (架构决策 D4)

**Metadata**:
- **Iteration #**: 153
- **Task Tree Level**: C3 (class 追踪迭代 — 按架构决策 D4)
- **Parent Task**: [class_tracing_plan.md](../../architecture/class_tracing_plan.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (unit +4; 回归见 commit)

## 🎯 本次目标

C3: constraint 语义查询 (D4: 独立 tracer, 不走数据 fanin)。

## 🔬 实际结果

### 实证 (约束图已全, class_graph_builder 建)

- 节点: CONSTRAINT_BLOCK (c_addr/c_data_if/c_range) / CONSTRAINT_EXPR
  (::expr_N) / CONSTRAINT_IF (::if_0) / CONSTRAINT_ELSE (::alt_0)
- 边语义: class -CONSTRAINS-> 属性/块; 块 -CONSTRAINS-> 属性/expr;
  expr -HAS_LHS-> 约束变量; if -HAS_CONDITION-> 条件变量 /
  HAS_CONSEQUENT / HAS_ALTERNATE

### 实现 (D4: query/constraint.py 独立 tracer)

`ConstraintTracer(graph).trace(prop_id)` → list[ConstraintInfo]
(block_id / vars (HAS_LHS) / conditions (HAS_CONDITION) / expr_count):
- 类型级 (packet.addr) 直接查; 实例属性 (top.p.addr) 自动解析类型级
  (路径 1: MEMBER_SELECT 反向; 路径 2 fallback: 剥成员 → 实例
  IS_INSTANCE_OF → 类型 — REG 化实例属性无 MEMBER_SELECT 出边, 实测)
- UnifiedTracer.trace_constraints 包装; 不走 fanin (D4/iter_139)

### 证据

- trace_constraints(packet.addr) → c_addr (vars addr/data 交叉) + c_range
- packet.data → c_addr + c_data_if (cond=[tag] if 识别); 实例 top.p.addr
  同结果 (REG fallback 路径 2)
- fanin(p.addr) 不含约束块 (约束不进数据源)
- unit +4 (TestConstraintTracing); 回归见 commit

## 💡 关键发现

1. **REG 化实例属性无 MEMBER_SELECT 出边** (被 always_ff 驱动 → kind REG):
   实例→类型解析需 fallback (实例 IS_INSTANCE_OF 路径) — C2 只覆盖
   CLASS_INSTANCE_PROPERTY 形态。
2. **约束查询 = 图遍历反向 CONSTRAINS/HAS_***: 声明式关系, 无数据流 —
   独立 tracer 保持 fanin 纯净 (D4 兑现)。

## 📌 状态

- ✅ C3 闭环: ConstraintTracer + trace_constraints (类型级 + 实例自动解析)
- ✅ 约束不进数据 fanin; unit +4
- 下一步: C4 (查询层 class kind 收束 + namespace 规则 + 冲突检测, D5)
