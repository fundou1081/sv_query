# Iteration 152: C2 实例↔类型级桥 + 查询语义 (架构决策 D3)

**Metadata**:
- **Iteration #**: 152
- **Task Tree Level**: C2 (class 追踪迭代 — 按架构决策 D3)
- **Parent Task**: [class_tracing_plan.md](../../architecture/class_tracing_plan.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (unit +4; 回归见 commit)

## 🎯 本次目标

C2: 实例↔类型级桥 + 类型级查询语义 (D3: 类型级=结构宿主, 实例级=
数据端点)。

## 🔬 实际结果

### 实证 (多实例)

- 成员节点**按需创建**: p1.data (被 set 使用) 建, p2.data (未用) 不建 —
  数据端点按需, 不臆造 (iter_143 原则延伸)
- 实例→类型单向: p1.data -MEMBER_SELECT-> packet.data; 类型→实例无反向
- IS_INSTANCE_OF: p1/p2 → packet (实例枚举有)

### 实现 (unified_tracer, 3 个关系查询 API — 图不变, 不建反向边)

| API | 语义 |
|---|---|
| `trace_class_members(class)` | 类型级结构成员 (CLASS_PROPERTY/约束块/表达式) — D3 结构参考 |
| `trace_class_instances(class)` | 类型 → 实例 (IS_INSTANCE_OF 反向遍历) |
| `trace_member_instances(type_prop)` | 类型属性 → **图内已建**实例属性 (不臆造未用成员) |

### 证据

- trace_class_members(packet) = [addr, data, c_addr, expr_0]
- trace_class_instances(packet) = [p1, p2]; trace_member_instances(packet.
  data) = [p1.data] (p2 未用 → 不建); packet.addr → [] (未使用)
- D3 数据端点语义: fanin(p1.data) = {din} (C1 链) 保持
- unit +4 (TestClassInstanceTypeBridge); 回归 59 passed (class/query/accuracy)

## 💡 关键发现

1. **实例成员节点 = 按需数据端点**: 只在被 RTL 读写/方法调用创建 — 类型
   级查询用 trace_member_instances 只报已建 (诚实: 未使用的实例成员
   "在设计中存在但无数据活动", 不臆造节点 — 与 iter_143 切片位同原则)。
2. **桥 = 查询遍历非反向边**: IS_INSTANCE_OF/MEMBER_SELECT 单向前提下,
   反向查询 O(边) 遍历 — 图不变 (D5 图不膨胀), 实例多时查询线性。

## 📌 状态

- ✅ C2 闭环: 3 关系 API + D3 语义 (类型级结构 / 实例数据端点 / 桥)
- ✅ 未使用成员不臆造; fanin 数据语义保持; unit +4
- 下一步: C3 (constraint 语义查询, 按 D4)
