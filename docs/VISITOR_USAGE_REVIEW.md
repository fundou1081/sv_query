# Visitor 使用情况检查报告

> 审查日期: 2026-05-23
> 提交: 1ba032f

---

## 一、Visitor 文件清单

| # | 文件 | 类名 | 状态 |
|---|------|------|------|
| 1 | base_visitor.py | BaseVisitor | ✅ 被 ConstraintVisitor 引用 |
| 2 | statement_visitor.py | StatementVisitor | ❌ 未被使用 |
| 3 | assignment_visitor.py | AssignmentVisitor | ❌ 未被使用 |
| 4 | constraint_visitor.py | ConstraintVisitor | ✅ 被 class_graph_builder.py 使用 |

---

## 二、详细分析

### 2.1 ConstraintVisitor ✅ 已使用

**引用位置**: `src/trace/core/class_graph_builder.py`

```python
from .visitors.constraint_visitor import ConstraintVisitor
...
self._cv = ConstraintVisitor()
```

**用途**: Class OOP 图构建中的 Constraint 处理

---

### 2.2 StatementVisitor ❌ 未被使用

**文件**: `src/trace/core/visitors/statement_visitor.py`

**问题**: 定义了但未被任何地方导入或使用

**内容**:
- `visit_nonblocking_assignment()`
- `visit_blocking_assignment()`
- `visit_continuous_assignment()`
- `visit_case()`
- `visit_if()`
- `visit_loop_statement()`
- `visit_sequential_block()`
- `visit_timing_control()`
- `visit_always_block()`
- `visit_class_declaration()`
- `visit_class_property()`
- `visit_data_declaration()`
- `visit_expression_statement()`

---

### 2.3 AssignmentVisitor ❌ 未被使用

**文件**: `src/trace/core/visitors/assignment_visitor.py`

**问题**: 定义了但未被任何地方导入或使用

**内容**:
- `visit_nonblocking_assignment()`
- `visit_blocking_assignment()`
- `visit_continuous_assignment()`

**继承关系**: `AssignmentVisitor` → `StatementVisitor` → `BaseVisitor`

---

## 三、原因分析

### 为什么 StatementVisitor/AssignmentVisitor 未被使用？

1. **历史原因**: `graph_builder.py` 先于 Visitor 架构实现
   - graph_builder.py 是早期实现，使用 if-elif 链处理语法
   - Visitor 架构是后来添加的 (铁律15)

2. **迁移未完成**: 
   - graph_builder.py 仍然使用旧的 `_collect_stmts_with_context()` 方法
   - 没有迁移到 Visitor 模式

3. **ConstraintVisitor 单独迁移**: 
   - Class 相关功能后来添加，直接使用了新架构
   - 但主流程 (signal tracing) 仍在 graph_builder.py 中

---

## 四、解决方案

### 方案 A: 完全迁移到 Visitor 模式 (P2)

**优点**:
- 遵守铁律15
- 代码更易维护
- 新语法类型添加更容易

**缺点**:
- 工作量大，需要大规模重构
- 风险高，可能破坏现有功能

**步骤**:
1. 将 `_collect_stmts_with_context` 逻辑迁移到 StatementVisitor
2. 将 `_get_signal` / `_get_all_signals` 逻辑迁移到 AssignmentVisitor
3. 在 graph_builder.py 中调用 Visitor

### 方案 B: 保持现状，清理未使用代码 (P3)

**优点**:
- 风险低
- 工作量小

**缺点**:
- 违反铁律15
- 代码冗余

**步骤**:
1. 删除 `statement_visitor.py` 和 `assignment_visitor.py`
2. 如果未来需要 Visitor，再重新实现

### 方案 C: 部分使用 (P2)

**优点**:
- 平衡风险和收益
- 可以逐步迁移

**缺点**:
- 架构不一致

**步骤**:
1. 在 graph_builder.py 中新增 `_visitor` 属性
2. 使用 StatementVisitor 处理特定场景 (如 CaseStatement)
3. 保持主流程不变

---

## 五、建议

| 优先级 | 建议 | 说明 |
|--------|------|------|
| P2 | 方案 C: 部分使用 | 在 graph_builder.py 中使用 StatementVisitor 处理 case/if 语句 |
| P3 | 清理未使用代码 | 删除 statement_visitor.py 和 assignment_visitor.py |

---

## 六、下次审查

- 审查日期: 2026-06-23
- 重点: Visitor 使用情况

---

*本报告由 QClaw Agent 自动生成*
*审查时间: 2026-05-23 11:42 GMT+8*