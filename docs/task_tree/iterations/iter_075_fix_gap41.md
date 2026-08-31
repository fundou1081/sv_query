# Iteration 075: 修功能缺口 #41 + 评估 #42-44

**Metadata**:
- **Iteration #**: 075
- **Task Tree Level**: L2
- **Parent Task**: C 组功能缺口修复 (方豆 "一起做" — A+B+C)
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ⚠️ 部分完成 (#41 已修 + 2 测试; #42-44 评估为深层工程/不可修, 已记录)

## 🎯 本次目标

C 组: 修 EXTRACTION_COVERAGE #41-#44 (class 方法赋值 / task 输出参数 / task 多语句 / DPI)。

## 📊 当前状态 / 预期结果

- #41: class 方法体内赋值零边
- #42/#43: task 输出参数占位边 (EmptyArgument)
- #44: DPI 调用无边 (期望行为?)

## 🔬 实际结果

### ✅ #41 已修 (class 方法体赋值 → 成员驱动边)

class_graph_builder 新增 `_build_method_assignments` + `_iter_body_assignments`:
- 遍历 class Subroutine 方法 body, 递归提取赋值表达式
- 建 RHS 变量 → LHS 成员 DRIVER 边 (assign_type=blocking)

**两个坑** (探针 + 调试发现):
1. **NamedValueExpression.name 是空** — 需用 adapter._extract_signals_from_expr
   提取 (与 constraint 路径一致, symbol 层取名字)
2. **id() 复用导致非确定** — walk 的 seen set 用 id(n), Python id 复用导致
   同层第二条语句被误判已访问 (5 次跑 4 次丢 data=addr)。修: 去掉 seen
   (depth 限制已防环)。修复后 5/5 确定。

**测试**: test_class_method.py 新增 2 个:
- test_method_member_assignment_edge: data = addr → packet.addr → packet.data DRIVER
- test_method_constant_assignment_no_edge: 常量赋值无边 (RHS 无变量)

回归: class 系列 133 passed / 全量 764 passed。

### ⚠️ #42/#43 (task 输出参数 → 调用方) — 深层工程, 已记录

**诊断根因** (探针确认):
- pyslang 把 task 调用的 **output 实参表示为 AssignmentExpression**
  (left=dout, right=EmptyArgument) — 传引用语义
- 且 NamedValueExpression.name 属性空 (需 symbol 提取)
- 调用链多环节 (parse → param_map → internal_drivers → output 边), 输出参数
  映射 + 形参回连 涉及 function_extractor 核心, 修复风险高

**当前行为**: EmptyArgument → dout 占位边 (已登记 #42/#43)。
方法体内**成员间**赋值已被 #41 修复覆盖 (多语句场景)。

### 🚫 #44 (DPI) — 期望行为, 不可修

DPI 函数体在 C (外部接口), sv_query 无法追踪内部驱动 — "调用无边"是正确行为。

## 💡 关键发现 / 决策

1. **pyslang 的 output 实参是 AssignmentExpression**: task 调用 `my_task(din, dout)`
   的 dout 被表示为 left=dout + right=EmptyArgument — 这是 #42 根因, 修复需要
   在 _parse_invocation_call 的 Assignment 分支正确处理 (提取 left 作实参)。
2. **id() 复用是隐藏非确定源**: 凡是 walk 用 id(n) 做 seen 的地方都可能漏节点
   (同层对象 id 复用)。全仓需检查类似模式 (已修 class_graph_builder 一处)。
3. **#41 修复顺带覆盖 #43 的多语句**: 方法体多条赋值都会被提取 (确定后)。
4. **诚实评估**: #42 需要专门 session (调用展开重写), #44 语义上不可修 —
   记录而非硬修, 符合"不修超出范围/不可修"的纪律。

## 📌 状态

- #41 ✅ / #42/#43 ⚠️ (成员间已覆盖, 调用侧待专门工程) / #44 🚫 (期望行为)
- 提交: class_graph_builder + test_class_method + EXTRACTION_COVERAGE
