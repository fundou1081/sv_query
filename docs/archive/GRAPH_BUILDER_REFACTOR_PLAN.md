# Graph Builder 重构计划 (Visitor 模式)

> 日期: 2026-05-23
> 目标: 将 graph_builder.py 重构为 Visitor 模式
> 状态: 计划中

---

## 一、现状分析

### 1.1 问题

| 问题 | 说明 | 严重度 |
|------|------|--------|
| 铁律15违反 | graph_builder.py 使用 if-elif 链处理语法类型 | 🟡 中 |
| 未使用Visitor | statement_visitor.py 和 assignment_visitor.py 定义但未使用 | 🟡 中 |
| 代码重复 | ScopedName 处理在多处分支中重复 | 🟢 低 |
| 维护困难 | 新语法类型需要修改多个 if-elif 链 | 🟡 中 |

### 1.2 当前结构

```
graph_builder.py (3304 行)
├── DriverExtractor (308-779)
│   ├── _collect_stmts_with_context()  # if-elif 链 (line 176-308)
│   ├── _collect_assignments_from_stmt()  # if-elif 链 (line 779-896)
│   ├── _parse_assign()  # 赋值解析
│   ├── _get_signal()  # if-elif 链 (line 1633-2197)
│   └── _get_all_signals()  # if-elif 链 (line 1391-1633)
├── LoadExtractor (2197-2606)
├── ConnectionExtractor (2606-3008)
└── ClockDomainExtractor (3008-3081)
```

### 1.3 现有 Visitor 文件

| 文件 | 类 | 状态 |
|------|-----|------|
| base_visitor.py | BaseVisitor | ✅ 可用 |
| statement_visitor.py | StatementVisitor | ❌ 未使用，需扩展 |
| assignment_visitor.py | AssignmentVisitor | ❌ 未使用，需扩展 |
| constraint_visitor.py | ConstraintVisitor | ✅ 已在使用 |

---

## 二、重构目标

### 2.1 架构目标

```
重构后的文件结构:

src/trace/core/
├── visitors/
│   ├── __init__.py
│   ├── base_visitor.py          # 抽象基类 (保留)
│   ├── statement_visitor.py      # 语句 Visitor (扩展)
│   ├── assignment_visitor.py     # 赋值 Visitor (扩展)
│   ├── signal_visitor.py         # 🆕 新增: 信号提取 Visitor
│   └── expression_visitor.py    # 🆕 新增: 表达式 Visitor
├── graph_builder.py              # 重构: 使用 Visitor
└── ...
```

### 2.2 分解目标

| 目标 | 说明 |
|------|------|
| 消除 if-elif 链 | `_collect_stmts_with_context` 中的 15+ 个分支 |
| 消除 if-elif 链 | `_get_signal` 中的 30+ 个分支 |
| 消除 if-elif 链 | `_get_all_signals` 中的 20+ 个分支 |
| 复用现有Visitor | 扩展 statement_visitor.py 和 assignment_visitor.py |
| 新增专用Visitor | signal_visitor.py 用于信号提取 |

---

## 三、重构计划 (分4阶段)

### 阶段 1: 准备和基础设施 (P2)

**目标**: 扩展现有 Visitor，建立信号提取基础

#### 1.1 扩展 statement_visitor.py

**新增方法**:
```python
class StatementVisitor(BaseVisitor):
    # 已有
    def visit_case(self, node): ...
    def visit_if(self, node): ...
    
    # 新增
    def visit_timed_statement(self, node): ...
    def visit_block_statement(self, node): ...
    def visit_expression_statement(self, node): ...
    def visit_initial_block(self, node): ...
    def visit_always_ff(self, node): ...
    def visit_always_comb(self, node): ...
    def visit_always_latch(self, node): ...
    def visit_invocation(self, node): ...
    def visit_assignment(self, node): ...
```

#### 1.2 新建 signal_visitor.py

**职责**: 专门处理信号名提取

```python
class SignalVisitor(BaseVisitor):
    """信号提取 Visitor"""
    
    def __init__(self, adapter):
        self.adapter = adapter
    
    def visit_identifier_name(self, node): ...
    def visit_scoped_name(self, node): ...
    def visit_element_select(self, node): ...
    def visit_range_select(self, node): ...
    def visit_concatenation(self, node): ...
    def visit_conditional_op(self, node): ...
    def visit_call(self, node): ...
    def visit_member_access(self, node): ...
    
    def get_signal_name(self, node) -> str: ...
    def get_all_signals(self, node) -> List[str]: ...
```

#### 1.3 新建 expression_visitor.py

**职责**: 专门处理表达式解析

```python
class ExpressionVisitor(BaseVisitor):
    """表达式 Visitor - 处理二元、三元、转换等"""
    
    def __init__(self, adapter):
        self.adapter = adapter
    
    def visit_binary_expression(self, node): ...
    def visit_unary_expression(self, node): ...
    def visit_conditional_op(self, node): ...
    def visit_conversion(self, node): ...
    def visit_parenthesized(self, node): ...
    
    def evaluate_expression(self, node) -> Any: ...
```

#### 1.4 交付物

- [ ] `statement_visitor.py` 扩展完成
- [ ] `signal_visitor.py` 新建完成
- [ ] `expression_visitor.py` 新建完成
- [ ] 单元测试通过

---

### 阶段 2: 重构 DriverExtractor (P2)

**目标**: 将 `_collect_stmts_with_context` 迁移到 StatementVisitor

#### 2.1 创建 StatementCollectorVisitor

```python
class StatementCollectorVisitor(StatementVisitor):
    """收集语句并携带上下文 (clock, condition)"""
    
    def __init__(self, adapter):
        super().__init__()
        self.statements = []  # [(node, ctx), ...]
        self.ctx_stack = [{"clock": "", "condition": ""}]
    
    def visit_always_ff(self, node):
        clock = self._extract_clock(node)
        self.ctx_stack.append({"clock": clock, "condition": ""})
        self.generic_visit(node)
        self.ctx_stack.pop()
    
    def visit_case(self, node):
        # 处理 case 语句的所有分支
        ...
    
    def visit_if(self, node):
        # 处理 if-else，追踪条件
        ...
    
    def visit_assignment(self, node):
        self.statements.append((node, self.current_ctx))
```

#### 2.2 迁移 `_get_signal` 和 `_get_all_signals`

**步骤**:
1. 在 `signal_visitor.py` 中实现各类型的 visit 方法
2. 替换 `graph_builder.py` 中的 if-elif 链

#### 2.3 交付物

- [ ] `StatementCollectorVisitor` 实现
- [ ] `SignalVisitor` 替代 `_get_signal`
- [ ] `SignalVisitor` 替代 `_get_all_signals`
- [ ] DriverExtractor 测试通过

---

### 阶段 3: 重构 LoadExtractor 和 ConnectionExtractor (P2)

**目标**: 将 LoadExtractor 和 ConnectionExtractor 也迁移到 Visitor

#### 3.1 创建 LoadExtractorVisitor

```python
class LoadExtractorVisitor(BaseVisitor):
    """负载追踪 Visitor"""
    
    def visit_continuous_assignment(self, node): ...
    def visit_nonblocking_assignment(self, node): ...
    def visit_blocking_assignment(self, node): ...
    def visit_invocation(self, node): ...
```

#### 3.2 交付物

- [ ] LoadExtractorVisitor 实现
- [ ] ConnectionExtractorVisitor 实现
- [ ] 集成测试通过

---

### 阶段 4: 清理和验证 (P3)

**目标**: 清理旧代码，验证功能

#### 4.1 删除旧代码

- [ ] 删除 `_collect_stmts_with_context` (旧方法)
- [ ] 删除 `_collect_assignments_from_stmt` (旧方法)
- [ ] 删除 `assignment_visitor.py` (合并到 signal_visitor.py)

#### 4.2 清理 Visitor 文件

- [ ] 删除 `statement_visitor.py` 中的未使用代码
- [ ] 删除 `assignment_visitor.py` (功能已合并)

#### 4.3 验证

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 所有回归测试通过
- [ ] 性能无下降

---

## 四、工作量估算

| 阶段 | 工作量 | 风险 |
|------|--------|------|
| 阶段1: 准备和基础设施 | 高 | 中 |
| 阶段2: DriverExtractor | 高 | 中 |
| 阶段3: LoadExtractor/ConnectionExtractor | 中 | 低 |
| 阶段4: 清理和验证 | 低 | 低 |

---

## 五、风险和缓解

### 风险1: 重构破坏现有功能

**缓解**:
1. 每阶段完成后运行完整测试
2. 使用 feature flag 逐步切换
3. 保留旧实现作为 fallback

### 风险2: Visitor 方法过多

**缓解**:
1. 使用泛型 `generic_visit()` 处理未实现的类型
2. 分层设计：顶层分发，底层处理具体类型

### 风险3: 性能下降

**缓解**:
1. 使用 memoization 缓存重复计算
2. 避免不必要的递归

---

## 六、备选方案 (如果重构风险太高)

### 方案 B: 局部改善

**不做完整重构，而是**:
1. 将 ScopedName 处理提取为公共函数
2. 将 RangeSelect/ElementSelect 处理提取为公共函数
3. 添加更多 Visitor 方法但不替换主流程

**优点**: 风险低，收益中
**缺点**: 不符合铁律15

### 方案 C: 保持现状

**理由**:
1. 当前功能正常
2. 重构风险高
3. 测试覆盖良好

**缺点**: 违反铁律15

---

## 七、建议

| 优先级 | 建议 |
|--------|------|
| P1 | 先完成方案 B (局部改善)，降低风险 |
| P2 | 在稳定后逐步迁移到方案 A (完整重构) |

---

## 八、下次审查

- 审查日期: 2026-06-23
- 重点: 阶段1 进展

---

*本计划由 QClaw Agent 生成*
*日期: 2026-05-23 11:52 GMT+8*