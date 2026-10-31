# Iteration 334: class relations（PLAN P38.1）

**Metadata**:
- **Iteration #**: 334
- **Task Tree Level**: L2（PLAN `P38.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "补 class 关系"）
- **Outcome**: ✅ 完成（继承/成员/实例/约束/方法调用；2672 passed）

## 🎯 目标

class 场景关注**调用链和关系**，不展开内部细节：
- extends/ancestors/subclasses/descendants；
- 类型级成员、实例、成员实例；
- 约束边；
- 方法定义 + 方法体调用。

## 🔧 实现

- `UnifiedTracer._step_class` 保留 `ClassGraphBuilder` 的 `hierarchy`；
  新增 `get_class_hierarchy()`；
- `class <name> --relations` 输出 `relations`：
  - hierarchy：extends/ancestors/subclasses/descendants；
  - members/instances（复用 trace_class_*）；
  - member_instances：每成员图内实例 + count；
  - constraints：图的 `CONSTRAINS/HAS_*` 出边；
  - methods：pyslang ClassMethodDeclaration + 方法体文本调用；
  - 裸调用 `foo()` 解析到当前类/祖先的 owner；receiver 调用不猜类型。
- 契约 class_relations/class_method/class_call/member_instances/constraint。

## 🧪 测试

新增 `test_class_relations.py`（4）：
继承、方法调用链、OOP 实例、未知 class 显式错误。
契约 +1：class relations 字段/嵌套精确匹配。

全量 **2672 passed / 0 failed**。

## ⚠️ 边界

- 方法调用是从方法体文本提取（正则），不是完整表达式 AST；receiver 的类型不解析；
- 只列**图内已存在**的实例/成员实例，未使用节点不臆造；
- 继承成员的图节点可能按子类命名（如 child.x），关系与图节点需分别看；
- 同名 class 冲突策略仍是首定义保留（class_graph_builder D5）。

## 🔗 相关

- 计划: [PLAN.md P38.1](../../../PLAN.md)
