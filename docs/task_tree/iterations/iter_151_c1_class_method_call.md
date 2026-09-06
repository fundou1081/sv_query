# Iteration 151: C1 class 方法调用链 — SubroutineExpander 复用 (D2)

**Metadata**:
- **Iteration #**: 151
- **Task Tree Level**: C1 (class 追踪迭代 — 按架构决策 D2)
- **Parent Task**: [class_tracing_plan.md](../../architecture/class_tracing_plan.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (C1 闭环; 回归 + unit +4 见 commit)

## 🎯 本次目标

方豆 "开工吧" → C1: class 方法调用链 (p.set(x) → 实例属性驱动)。

## 🔬 实际结果

### 语义形态探查 (pyslang)

- class 方法调用 = `ExpressionKind.Call` + **`.thisClass`** (receiver NamedValue p)
  + `.subroutine` (SubroutineSymbol 'set') — module function 调用无 thisClass
- receiver 变量 `p.type` (ClassType) name = 'packet'; **ClassSymbol 成员在
  迭代里** (for member in cls — 实测 .body 为空; class_graph_builder
  _iter_class_properties 同模式)

### 实现 (function_extractor.py, 按 D2 复用 module 调用机制)

1. `_handle_invocation`: 解析 receiver (thisClass → 变量名 + type name) →
   `_find_task_definition` (module) 找不到时 → **`_find_class_method`
   (get_classes 按 receiver 类型名匹配 → ClassSymbol 迭代找 Subroutine)**
2. `_create_invocation_edges` 加 receiver_id 参数 + **class 成员展开分支**:
   方法体 internal_drivers 中非形参目标 (data) → 实例属性
   (receiver_id.data), rhs 经 param_map (d→din) → DRIVER 边
   `top.din -blocking-> top.p.data`
3. 复用: 参数映射 (param_map) / internal_drivers 分析 / edge_factory —
   无第二套调用语义 (D2)

### 证据

- fanin(top.p.data) = {top.din} (方法调用 p.set(din) 链通 — C1 前为空)
- 边: top.din -DRIVER/blocking-> top.p.data; 实例↔类型 MEMBER_SELECT 边并存
- module task/function 调用路径不变 (receiver_id=None 默认)

### 验证

- unit +4 (TestClassMethodCallChain: set 展开 / 多成员 / 未调用不展开 /
  module function 不回归) — test_class_oop_truth 8 passed
- 回归: unit + function/class/assign/cordic truth 1157 passed (0 新增失败)
- 现有 truth (golden_dataflow_35 set_addr) 未破 — 其调用在非提取块

## 📌 状态

- ✅ C1 闭环: class 方法调用链 (D2: 复用 module 调用机制, receiver 解析 +
  class 方法查找 + 成员展开到实例属性)
- ✅ 未调用不展开; module 调用不回归; unit +4
- 下一步: C2 (实例↔类型级桥 + 查询语义, 按 D3)
