# Graph Builder 重构详细执行计划

> 日期: 2026-05-23
> 版本: v2 (详细版)
> 目标: 将 graph_builder.py 重构为 Visitor 模式

---

## 一、方法映射表

### 1.1 _collect_stmts_with_context (line 176-308)

**当前问题**: 30+ if-elif 分支处理不同语法类型

**需要迁移的分支**:

| # | 条件分支 | 应转为 Visitor 方法 | 优先级 |
|---|----------|---------------------|--------|
| 1 | `if ".TokenKind." in ks or "Trivia" in ks` | skip (过滤) | P0 |
| 2 | `if "InitialBlock" in ks` | visit_initial_block | P1 |
| 3 | `if any(x in ks for x in ["AlwaysFF", "AlwaysComb", "AlwaysLatch"])` | visit_procedure_block | P1 |
| 4 | `if "TimingControl" in ks` | visit_timing_control | P2 |
| 5 | `if "Timed" in ks` | visit_timed_statement | P1 |
| 6 | `if "Block" in ks and "Statement" in ks` | visit_block_statement | P1 |
| 7 | `if "Case" in ks and "Statement" in ks` | visit_case_statement | P1 |
| 8 | `if "Conditional" in ks and "Statement" in ks` | visit_conditional_statement | P1 |
| 9 | `if "ElseClause" in ks` | visit_else_clause | P2 |
| 10 | `if "ExpressionStatement" in ks` | visit_expression_statement | P1 |
| 11 | `if "InvocationExpression" in ks or "Call" in ks` | visit_invocation | P1 |
| 12 | `if "Assignment" in ks` | visit_assignment | P1 |
| 13 | fallback: 遍历子节点 | generic_visit | - |

---

### 1.2 _get_signal (line 1633-2197)

**当前问题**: 30+ if-elif 分支处理不同信号类型

**需要迁移的分支**:

| # | 条件分支 | 应转为 Visitor 方法 | 优先级 |
|---|----------|---------------------|--------|
| 1 | `if str(signal.kind) == 'SyntaxKind.ScopedName'` | visit_scoped_name | P0 |
| 2 | `if 'IntegerVector' in str(signal.kind)` | visit_integer_vector | P0 |
| 3 | `if 'IntegerLiteral' in str(signal.kind)` | visit_integer_literal | P0 |
| 4 | `if 'Conversion' in str(signal.kind)` | visit_conversion | P1 |
| 5 | `if 'ElementSelect' in str(signal.kind)` | visit_element_select | P1 |
| 6 | `if 'MemberAccess' in str(signal.kind)` | visit_member_access | P1 |
| 7 | `if 'RangeSelect' in str(signal.kind)` | visit_range_select | P1 |
| 8 | `if 'IdentifierSelect' in str(kind)` | visit_identifier_select | P1 |
| 9 | `if kind and 'IdentifierName' in str(kind)` | visit_identifier_name | P0 |
| 10 | `if kind and 'ParenthesizedExpression' in str(kind)` | visit_parenthesized | P2 |
| 11 | `if hasattr(signal, 'left') and hasattr(signal, 'right')` | visit_binary_expr | P1 |
| 12 | `if kind and 'Conditional' in str(kind)` | visit_conditional | P2 |
| 13 | `if kind and 'Concatenation' in str(kind)` | visit_concatenation | P1 |
| 14 | `if kind and ('Unary' in str(kind) or 'NegateExpression' in str(kind))` | visit_unary | P2 |
| 15 | `if kind and 'SimplePropertyExpr' in str(kind)` | visit_simple_property_expr | P3 |
| 16 | `if kind and 'SimpleSequenceExpr' in str(kind)` | visit_simple_sequence_expr | P3 |
| 17 | `if kind and ('Invocation' in str(kind) or 'Call' in str(kind))` | visit_call | P1 |
| 18 | `if kind and 'HierarchicalValue' in str(kind)` | visit_hierarchical_value | P1 |
| 19 | `if kind and 'MultipleConcatenation' in str(kind)` | visit_multiple_concatenation | P2 |
| 20 | `if kind and 'Replication' in str(kind)` | visit_replication | P2 |
| 21 | fallback: 抛出 ValueError | - | - |

---

### 1.3 _get_all_signals (line 1391-1633)

**需要迁移的分支**:

| # | 条件分支 | 应转为 Visitor 方法 | 优先级 |
|---|----------|---------------------|--------|
| 1 | `if 'ConditionalOp' in kind_str or 'ConditionalExpression' in kind_str` | visit_conditional_op | P1 |
| 2 | `if 'ParenthesizedExpression' in kind_str` | visit_parenthesized | P2 |
| 3 | `if 'ConditionalPredicate' in kind_str or 'ConditionalPattern' in kind_str` | visit_conditional_predicate | P2 |
| 4 | `if 'TimingControlExpression' in kind_str` | visit_timing_control_expr | P3 |
| 5 | `if 'Conversion' in kind_str` | visit_conversion | P1 |
| 6 | `if 'Call' in kind_str or 'Invocation' in kind_str` | visit_call | P1 |
| 7 | `if 'ElementSelect' in kind_str` | visit_element_select | P1 |
| 8 | `if 'MemberAccess' in kind_str` | visit_member_access | P1 |
| 9 | `if 'Concatenation' in kind_str and 'Multiple' not in kind_str` | visit_concatenation | P1 |
| 10 | `if str(signal.kind) == 'SyntaxKind.ScopedName'` | visit_scoped_name | P0 |
| 11 | `if 'RangeSelect' in str(signal.kind)` | visit_range_select | P1 |
| 12 | `if hasattr(signal, 'left') and hasattr(signal, 'right')` | visit_binary_expr | P1 |
| 13 | fallback: `_get_signal` | - | - |

---

## 二、执行步骤 (详细)

### 阶段 1: 创建 SignalExpressionVisitor (P2)

**文件**: `src/trace/core/visitors/signal_expression_visitor.py` (新建)

#### Step 1.1: 实现基类

```python
class SignalExpressionVisitor:
    """信号/表达式提取 Visitor"""
    
    def __init__(self, adapter):
        self.adapter = adapter
    
    def visit(self, node):
        """分发到对应的 visit 方法"""
        if node is None:
            return None
        kind = getattr(node, 'kind', None)
        if kind is None:
            return None
        
        method_name = f"visit_{kind.name}" if hasattr(kind, 'name') else None
        if method_name and hasattr(self, method_name):
            return getattr(self, method_name)(node)
        
        # 默认: 尝试递归提取
        return self.generic_visit(node)
    
    def generic_visit(self, node):
        """默认递归进入子节点"""
        return None
```

#### Step 1.2: 实现 _get_signal 的分支 (P0)

| # | 方法名 | 实现 |
|---|--------|------|
| 1 | `visit_identifier_name` | 提取 `identifier.value` |
| 2 | `visit_scoped_name` | 递归提取点分路径 |
| 3 | `visit_integer_vector` | 返回字面量字符串 |
| 4 | `visit_integer_literal` | 返回 `value` |

#### Step 1.3: 实现 _get_signal 的分支 (P1)

| # | 方法名 | 实现 |
|---|--------|------|
| 5 | `visit_element_select` | 返回 `base[index]` |
| 6 | `visit_range_select` | 返回 `base[left:right]` |
| 7 | `visit_conversion` | 递归 operand |
| 8 | `visit_member_access` | 返回 `base.member` |
| 9 | `visit_call` | 返回函数名 |
| 10 | `visit_binary_expr` | 返回左操作数 |

#### Step 1.4: 实现 _get_all_signals 的分支 (P1)

| # | 方法名 | 实现 |
|---|--------|------|
| 11 | `visit_conditional_op` | 返回 [cond, left, right] |
| 12 | `visit_concatenation` | 递归所有操作数 |
| 13 | `visit_invocation` | 递归 arguments |

---

### 阶段 2: 创建 StatementCollectorVisitor (P2)

**文件**: `src/trace/core/visitors/statement_collector_visitor.py` (新建)

#### Step 2.1: 实现基类

```python
class StatementCollectorVisitor:
    """语句收集 Visitor - 携带语义上下文"""
    
    def __init__(self, adapter):
        self.adapter = adapter
        self.statements = []  # [(node, ctx), ...]
        self.ctx_stack = [{}]
    
    @property
    def current_ctx(self):
        return self.ctx_stack[-1] if self.ctx_stack else {}
    
    def visit(self, node):
        """分发到对应的 visit 方法"""
        ...
    
    def visit_always_ff(self, node):
        """提取时钟域，进入 body"""
        clock = self._extract_clock(node)
        self.ctx_stack.append({**self.current_ctx, "clock": clock})
        self.generic_visit(node)
        self.ctx_stack.pop()
    
    def visit_always_comb(self, node):
        """无时钟域，进入 body"""
        self.generic_visit(node)
    
    # ... 其他方法
```

#### Step 2.2: 实现 _collect_stmts_with_context 的分支

| # | 方法名 | 实现 |
|---|--------|------|
| 1 | `visit_initial_block` | 进入 statement |
| 2 | `visit_procedure_block` | 根据类型分发 (always_ff/comb/latch) |
| 3 | `visit_timing_control` | 提取时钟，进入 statement |
| 4 | `visit_timed_statement` | 进入 stmt |
| 5 | `visit_block_statement` | 进入 body |
| 6 | `visit_case_statement` | 处理 items，分支收集 |
| 7 | `visit_conditional_statement` | 处理 ifTrue/ifFalse，条件追踪 |
| 8 | `visit_expression_statement` | 进入 expr |
| 9 | `visit_invocation` | 收集调用 |
| 10 | `visit_assignment` | 收集赋值 |

---

### 阶段 3: 修改 graph_builder.py (P2)

#### Step 3.1: 导入新 Visitor

```python
from .visitors.signal_expression_visitor import SignalExpressionVisitor
from .visitors.statement_collector_visitor import StatementCollectorVisitor
```

#### Step 3.2: 添加实例

```python
class DriverExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
        self._signal_visitor = SignalExpressionVisitor(adapter)
        self._stmt_collector = StatementCollectorVisitor(adapter)
```

#### Step 3.3: 替换方法 (逐个)

**Phase A: 替换 _get_signal**

1. 保留 `def _get_signal(self, signal) -> Optional[str]:`
2. 在内部调用 `self._signal_visitor.visit(signal)`
3. 测试通过后删除原实现

**Phase B: 替换 _get_all_signals**

1. 保留 `def _get_all_signals(self, signal) -> List[str]:`
2. 在内部调用 `self._signal_visitor.get_all_signals(signal)`
3. 测试通过后删除原实现

**Phase C: 替换 _collect_stmts_with_context**

1. 保留原方法签名
2. 在内部调用 `self._stmt_collector.collect(node, ctx)`
3. 测试通过后删除原实现

---

## 三、测试策略

### 3.1 单元测试

每个 Visitor 方法必须有单元测试:

```python
def test_visit_identifier_name():
    visitor = SignalExpressionVisitor(adapter)
    node = create_identifier_node("clk")
    result = visitor.visit(node)
    assert result == "clk"

def test_visit_scoped_name():
    visitor = SignalExpressionVisitor(adapter)
    node = create_scoped_node("top.clk")
    result = visitor.visit(node)
    assert result == "top.clk"
```

### 3.2 集成测试

替换后的方法必须通过现有测试:

```bash
pytest sim/tests/ -k "test_ternary" -v
pytest sim/tests/ -k "test_alias" -v
pytest sim/tests/ --tb=no -q
```

### 3.3 回归测试

每次替换后运行完整测试套件:

```bash
pytest sim/tests/ --tb=no -q
```

---

## 四、详细任务分解

### Task 1: 创建 SignalExpressionVisitor (3小时)

| # | 子任务 | 预估时间 |
|---|--------|----------|
| 1.1 | 创建文件骨架 | 15分钟 |
| 1.2 | 实现 `visit_identifier_name` | 30分钟 |
| 1.3 | 实现 `visit_scoped_name` | 30分钟 |
| 1.4 | 实现 `visit_element_select` | 30分钟 |
| 1.5 | 实现 `visit_range_select` | 30分钟 |
| 1.6 | 实现 `visit_conversion` | 30分钟 |
| 1.7 | 实现 `visit_member_access` | 30分钟 |
| 1.8 | 实现 `visit_binary_expr` | 30分钟 |
| 1.9 | 实现 `visit_call` | 30分钟 |
| 1.10 | 实现 `visit_integer_literal` | 15分钟 |
| 1.11 | 单元测试 | 60分钟 |
| 1.12 | 调试修复 | 60分钟 |
| **总计** | | **5.5小时** |

### Task 2: 创建 StatementCollectorVisitor (4小时)

| # | 子任务 | 预估时间 |
|---|--------|----------|
| 2.1 | 创建文件骨架 | 30分钟 |
| 2.2 | 实现 `visit_initial_block` | 30分钟 |
| 2.3 | 实现 `visit_always_ff` | 30分钟 |
| 2.4 | 实现 `visit_always_comb` | 30分钟 |
| 2.5 | 实现 `visit_timed_statement` | 30分钟 |
| 2.6 | 实现 `visit_block_statement` | 30分钟 |
| 2.7 | 实现 `visit_case_statement` | 60分钟 |
| 2.8 | 实现 `visit_conditional_statement` | 60分钟 |
| 2.9 | 实现 `visit_expression_statement` | 30分钟 |
| 2.10 | 实现 `visit_invocation` | 30分钟 |
| 2.11 | 实现 `visit_assignment` | 30分钟 |
| 2.12 | 单元测试 | 90分钟 |
| 2.13 | 调试修复 | 90分钟 |
| **总计** | | **7.5小时** |

### Task 3: 修改 graph_builder.py - _get_signal (2小时)

| # | 子任务 | 预估时间 |
|---|--------|----------|
| 3.1 | 导入 SignalExpressionVisitor | 15分钟 |
| 3.2 | 添加实例到 DriverExtractor | 15分钟 |
| 3.3 | 替换 `_get_signal` 调用 | 30分钟 |
| 3.4 | 替换 `_get_all_signals` 调用 | 30分钟 |
| 3.5 | 运行测试 | 30分钟 |
| 3.6 | 调试修复 | 60分钟 |
| **总计** | | **3小时** |

### Task 4: 修改 graph_builder.py - _collect_stmts_with_context (3小时)

| # | 子任务 | 预估时间 |
|---|--------|----------|
| 4.1 | 导入 StatementCollectorVisitor | 15分钟 |
| 4.2 | 添加实例到 DriverExtractor | 15分钟 |
| 4.3 | 替换 `_collect_stmts_with_context` 调用 | 60分钟 |
| 4.4 | 运行测试 | 60分钟 |
| 4.5 | 调试修复 | 90分钟 |
| **总计** | | **4小时** |

### Task 5: 清理和验证 (2小时)

| # | 子任务 | 预估时间 |
|---|--------|----------|
| 5.1 | 删除旧代码 (if-elif 链) | 30分钟 |
| 5.2 | 运行完整测试套件 | 60分钟 |
| 5.3 | 性能检查 | 30分钟 |
| 5.4 | 文档更新 | 30分钟 |
| **总计** | | **2.5小时** |

---

## 五、总工作量

| Task | 名称 | 时间 |
|------|------|------|
| Task 1 | SignalExpressionVisitor | 5.5小时 |
| Task 2 | StatementCollectorVisitor | 7.5小时 |
| Task 3 | 修改 _get_signal | 3小时 |
| Task 4 | 修改 _collect_stmts_with_context | 4小时 |
| Task 5 | 清理和验证 | 2.5小时 |
| **总计** | | **22.5小时** |

---

## 六、里程碑

| 里程碑 | 完成标准 |
|--------|----------|
| M1 | Task 1 完成，SignalExpressionVisitor 通过单元测试 |
| M2 | Task 2 完成，StatementCollectorVisitor 通过单元测试 |
| M3 | Task 3 完成，_get_signal 替换通过集成测试 |
| M4 | Task 4 完成，_collect_stmts_with_context 替换通过集成测试 |
| M5 | Task 5 完成，完整测试套件通过 |

---

## 七、风险缓解

### 风险1: 重构破坏功能

**缓解**:
1. 每个 Task 完成后运行测试
2. 保留旧方法作为 fallback (标记为 deprecated)
3. 增量替换，不是全部替换

### 风险2: Visitor 方法遗漏

**缓解**:
1. 对照检查清单逐个实现
2. 添加 `visit_unknown` 处理未实现类型
3. 测试覆盖关键路径

### 风险3: 性能下降

**缓解**:
1. 使用 memoization 缓存结果
2. 避免不必要的递归
3. 性能测试对比

---

## 八、代码审查清单

在合并重构代码前，必须通过:

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 所有回归测试通过 (816 passed, 0 failed)
- [ ] 代码遵循铁律1-3, 铁律15
- [ ] 无 `except: pass` (铁律3.1)
- [ ] 文档已更新

---

## 九、后续行动

| 日期 | 行动 |
|------|------|
| 2026-05-23 | 批准计划 |
| 2026-05-23 | 开始 Task 1 |
| 2026-05-24 | 完成 Task 1 (SignalExpressionVisitor) |
| 2026-05-25 | 完成 Task 2 (StatementCollectorVisitor) |
| 2026-05-26 | 完成 Task 3 (_get_signal 替换) |
| 2026-05-27 | 完成 Task 4 (_collect_stmts_with_context 替换) |
| 2026-05-28 | 完成 Task 5 (清理验证) |

---

*本计划由 QClaw Agent 生成*
*日期: 2026-05-23 12:05 GMT+8*