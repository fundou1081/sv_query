# TDD 开发主线 - Expression 节点架构

> 创建时间: 2026-05-25
> 状态: 开发中
> 方法: TDD (Test-Driven Development)

---

## TDD 循环

```
Red (失败测试) → Green (通过实现) → Refactor (重构)
```

每阶段必须：
1. 写失败测试
2. 通过实现
3. 重构优化

---

## 开发主线

### P1 - TraceNode 扩展

#### 1.1 添加 NodeKind.EXPRESSION 和 NodeKind.FUNCTION_CALL

**测试用例** (Red):
```python
def test_node_kind_expression_exists():
    """NodeKind 应包含 EXPRESSION"""
    from trace.core.graph.models import NodeKind
    assert hasattr(NodeKind, 'EXPRESSION')

def test_node_kind_function_call_exists():
    """NodeKind 应包含 FUNCTION_CALL"""
    from trace.core.graph.models import NodeKind
    assert hasattr(NodeKind, 'FUNCTION_CALL')
```

**实现** (Green):
```python
class NodeKind(Enum):
    # ... existing ...
    EXPRESSION = auto()
    FUNCTION_CALL = auto()
```

#### 1.2 添加 TraceNode 扩展字段

**测试用例** (Red):
```python
def test_trace_node_expression_fields():
    """TraceNode 应支持 expression 相关字段"""
    node = TraceNode(
        id="expr_1",
        name="a + b",
        module="top",
        kind=NodeKind.EXPRESSION,
        expression="a + b",
        operands=["a", "b"],
        signals=["a", "b"]
    )
    assert node.expression == "a + b"
    assert node.operands == ["a", "b"]
    assert node.signals == ["a", "b"]
```

**实现** (Green):
```python
@dataclass
class TraceNode:
    id: str
    name: str
    module: str
    kind: NodeKind
    
    # 新增字段
    expression: Optional[str] = None
    operands: List[str] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)
    function_name: Optional[str] = None
    function_return: bool = False
    condition: Optional[str] = None
    true_branch: Optional[str] = None
    false_branch: Optional[str] = None
```

---

### P2 - ExpressionBuilder 核心类

#### 2.1 创建 ExpressionBuilder 类骨架

**测试用例** (Red):
```python
def test_expression_builder_initialization():
    """ExpressionBuilder 应可初始化"""
    from trace.core.builder.expression_builder import ExpressionBuilder
    builder = ExpressionBuilder()
    assert builder is not None
```

**实现** (Green):
```python
class ExpressionBuilder:
    def __init__(self, graph: SignalGraph):
        self._graph = graph
        self._node_counter = 0
    
    def _next_id(self, prefix: str) -> str:
        self._node_counter += 1
        return f"{prefix}_{self._node_counter}"
```

#### 2.2 实现 build_expression() - 简单二元表达式

**测试用例** (Red):
```python
def test_build_simple_expression():
    """data = a + b 应创建表达式节点"""
    # Given
    graph = SignalGraph()
    builder = ExpressionBuilder(graph)
    # AST mock: BinaryOpExpression(a, +, b) → data
    
    # When
    expr_node_id = builder.build_expression(
        node=mock_binary_op,
        operands=["a", "b"],
        expression="a + b",
        result="data"
    )
    
    # Then
    assert expr_node_id == "expr_1"
    assert graph.has_node("expr_1")
    assert graph.has_node("data")
    assert graph.has_edge("a", "expr_1")
    assert graph.has_edge("b", "expr_1")
    assert graph.has_edge("expr_1", "data")
```

**实现** (Green):
```python
def build_expression(self, node, operands: List[str], 
                     expression: str, result: str) -> Optional[str]:
    # 1. 创建表达式节点
    expr_id = self._next_id("expr")
    expr_node = TraceNode(
        id=expr_id,
        name=expression,
        module=self._current_module,
        kind=NodeKind.EXPRESSION,
        expression=expression,
        operands=operands
    )
    self._graph.add_node(expr_node)
    
    # 2. 添加 operands → expr 边
    for op in operands:
        self._graph.add_edge(TraceEdge(
            src=op,
            dst=expr_id,
            kind=EdgeKind.DRIVER
        ))
    
    # 3. 添加 expr → result 边
    self._graph.add_edge(TraceEdge(
        src=expr_id,
        dst=result,
        kind=EdgeKind.DRIVER
    ))
    
    return expr_id
```

#### 2.3 实现 build_function_call()

**测试用例** (Red):
```python
def test_build_function_call():
    """data = calc(a, b) 应创建函数调用节点"""
    # Given
    graph = SignalGraph()
    builder = ExpressionBuilder(graph)
    
    # When
    func_node_id = builder.build_function_call(
        node=mock_call,
        function_name="calc",
        arguments=["a", "b"],
        result="data"
    )
    
    # Then
    assert func_node_id == "func_calc_1"
    assert graph.has_node("func_calc_1")
    func_node = graph.get_node("func_calc_1")
    assert func_node.kind == NodeKind.FUNCTION_CALL
    assert func_node.function_name == "calc"
    assert func_node.arguments == ["a", "b"]
```

**实现** (Green):
```python
def build_function_call(self, node, function_name: str,
                        arguments: List[str], result: str) -> Optional[str]:
    func_id = self._next_id(f"func_{function_name}")
    func_node = TraceNode(
        id=func_id,
        name=f"{function_name}({', '.join(arguments)})",
        module=self._current_module,
        kind=NodeKind.FUNCTION_CALL,
        function_name=function_name,
        arguments=arguments
    )
    self._graph.add_node(func_node)
    
    # 添加 arguments → func 边
    for arg in arguments:
        self._graph.add_edge(TraceEdge(
            src=arg,
            dst=func_id,
            kind=EdgeKind.DRIVER
        ))
    
    # 添加 func → result 边
    self._graph.add_edge(TraceEdge(
        src=func_id,
        dst=result,
        kind=EdgeKind.DRIVER,
        function_return=True
    ))
    
    return func_id
```

#### 2.4 实现 build_conditional()

**测试用例** (Red):
```python
def test_build_conditional_expression():
    """data = sel ? a : b 应创建条件表达式节点"""
    # Given
    graph = SignalGraph()
    builder = ExpressionBuilder(graph)
    
    # When
    cond_node_id = builder.build_conditional(
        node=mock_conditional,
        condition="sel",
        true_branch="a",
        false_branch="b",
        result="data"
    )
    
    # Then
    assert cond_node_id == "cond_ternary_1"
    cond_node = graph.get_node(cond_node_id)
    assert cond_node.kind == NodeKind.EXPRESSION
    assert cond_node.condition == "sel"
    assert cond_node.true_branch == "a"
    assert cond_node.false_branch == "b"
```

**实现** (Green):
```python
def build_conditional(self, node, condition: str,
                     true_branch: str, false_branch: str,
                     result: str) -> Optional[str]:
    cond_id = self._next_id("cond_ternary")
    cond_node = TraceNode(
        id=cond_id,
        name=f"{condition} ? {true_branch} : {false_branch}",
        module=self._current_module,
        kind=NodeKind.EXPRESSION,
        expression=f"{condition} ? {true_branch} : {false_branch}",
        condition=condition,
        true_branch=true_branch,
        false_branch=false_branch
    )
    self._graph.add_node(cond_node)
    
    # 添加 condition → cond 边
    self._graph.add_edge(TraceEdge(
        src=condition,
        dst=cond_id,
        kind=EdgeKind.DRIVER
    ))
    
    # 添加 true/false branch → cond 边
    self._graph.add_edge(TraceEdge(
        src=true_branch,
        dst=cond_id,
        kind=EdgeKind.DRIVER
    ))
    self._graph.add_edge(TraceEdge(
        src=false_branch,
        dst=cond_id,
        kind=EdgeKind.DRIVER
    ))
    
    # 添加 cond → result 边 (带 condition)
    self._graph.add_edge(TraceEdge(
        src=cond_id,
        dst=result,
        kind=EdgeKind.DRIVER_CONDITIONAL,
        condition=condition
    ))
    
    return cond_id
```

---

### P3 - Handler 补全 (TDD)

#### 3.1 AddExpression Handler

**测试用例** (Red):
```python
def test_add_expression_handler():
    """a + b 应创建 expr 节点"""
    # Given
    sv_code = '''
    module top;
        logic [7:0] a, b, data;
        assign data = a + b;
    endmodule
    '''
    # When
    result = trace_signal(sv_code, "top.data")
    
    # Then
    assert result.confidence == "high"
    assert "expr_1" in result.upstream
    assert result.upstream["expr_1"]["kind"] == "EXPRESSION"
```

**实现** (Green):
```python
@on('AddExpression')
def handle_add_expression(self, node):
    left = self._extract_operand(node.left)
    right = self._extract_operand(node.right)
    expr = f"{left} + {right}"
    
    # 使用 ExpressionBuilder
    result_signal = self._current_target  # data
    self._builder.build_expression(
        node=node,
        operands=[left, right],
        expression=expr,
        result=result_signal
    )
```

#### 3.2 ConditionalExpression Handler

**测试用例** (Red):
```python
def test_conditional_expression_handler():
    """sel ? a : b 应创建条件节点"""
    sv_code = '''
    module top;
        logic sel, a, b, data;
        assign data = sel ? a : b;
    endmodule
    '''
    result = trace_signal(sv_code, "top.data")
    
    # Then
    assert result.confidence == "high"
    assert len(result.upstream) == 1
    upstream = result.upstream[0]
    assert upstream["kind"] == "EXPRESSION"
    assert upstream["condition"] == "sel"
```

**实现** (Green):
```python
@on('ConditionalExpression')
def handle_conditional_expression(self, node):
    cond = self._extract_operand(node.condition)
    true_val = self._extract_operand(node.true_value)
    false_val = self._extract_operand(node.false_value)
    
    self._builder.build_conditional(
        node=node,
        condition=cond,
        true_branch=true_val,
        false_branch=false_val,
        result=self._current_target
    )
```

#### 3.3 CallExpression Handler

**测试用例** (Red):
```python
def test_call_expression_handler():
    """calc(a, b) 应创建函数调用节点"""
    sv_code = '''
    module top;
        function [7:0] calc(input [7:0] a, input [7:0] b);
            calc = a + b;
        endfunction
        logic [7:0] a, b, data;
        assign data = calc(a, b);
    endmodule
    '''
    result = trace_signal(sv_code, "top.data")
    
    # Then
    func_nodes = [n for n in result.graph.nodes 
                  if n.kind == NodeKind.FUNCTION_CALL]
    assert len(func_nodes) == 1
    assert func_nodes[0].function_name == "calc"
```

**实现** (Green):
```python
@on('CallExpression')
def handle_call_expression(self, node):
    # 获取函数信息
    func_name = node.subroutineName
    args = [self._extract_operand(arg) for arg in node.arguments]
    
    self._builder.build_function_call(
        node=node,
        function_name=func_name,
        arguments=args,
        result=self._current_target
    )
```

#### 3.4 批量 Handler 实现清单

| Handler | 测试用例状态 | 实现状态 |
|---------|-------------|---------|
| AddExpression | ⬜ | ⬜ |
| SubtractExpression | ⬜ | ⬜ |
| MultiplyExpression | ⬜ | ⬜ |
| DivideExpression | ⬜ | ⬜ |
| BinaryAndExpression | ⬜ | ⬜ |
| BinaryOrExpression | ⬜ | ⬜ |
| BinaryXorExpression | ⬜ | ⬜ |
| EqualityExpression | ⬜ | ⬜ |
| InequalityExpression | ⬜ | ⬜ |
| LessThanExpression | ⬜ | ⬜ |
| GreaterThanExpression | ⬜ | ⬜ |
| LogicalAndExpression | ⬜ | ⬜ |
| LogicalOrExpression | ⬜ | ⬜ |
| ArithmeticShiftLeftExpression | ⬜ | ⬜ |
| ArithmeticShiftRightExpression | ⬜ | ⬜ |
| ConditionalExpression | ⬜ | ⬜ |
| CallExpression | ⬜ | ⬜ |
| MemberAccessExpression | ⬜ | ⬜ |
| ElementSelectExpression | ⬜ | ⬜ |

---

### P4 - GraphBuilder 集成

#### 4.1 集成测试

**测试用例** (Red):
```python
def test_graph_builder_integration():
    """完整流程测试: 代码 → 图"""
    sv_code = '''
    module top;
        logic [7:0] a, b, c, data;
        assign data = (a + b) * c;
    endmodule
    '''
    
    # When
    graph = build_signal_graph(sv_code, "top")
    
    # Then
    # 验证节点
    assert graph.has_node("top.data")
    assert graph.has_node("top.a")
    assert graph.has_node("top.b")
    assert graph.has_node("top.c")
    
    # 验证表达式节点链
    # data = (a + b) * c
    # a → expr_add → expr_mul → data
    # b → expr_add
    # c → expr_mul
    
    assert graph.has_edge("top.a", "expr_add_1")
    assert graph.has_edge("top.b", "expr_add_1")
    assert graph.has_edge("expr_add_1", "expr_mul_1")
    assert graph.has_edge("top.c", "expr_mul_1")
    assert graph.has_edge("expr_mul_1", "top.data")
```

#### 4.2 回归测试

**测试用例** (Red):
```python
def test_existing_functionality_preserved():
    """现有功能不能破坏"""
    sv_code = '''
    module top;
        logic [7:0] a, b;
        assign b = a;
    endmodule
    '''
    result = trace_signal(sv_code, "top.b")
    
    # 仍然应该能正常工作
    assert result.confidence == "high"
    assert len(result.upstream) == 1
    assert result.upstream[0]["path"] == "top.a"
```

---

### P5 - expand_function() 实现

#### 5.1 函数展开测试

**测试用例** (Red):
```python
def test_expand_function():
    """calc(a, b) 应可展开为实际逻辑"""
    sv_code = '''
    module top;
        function [7:0] calc(input [7:0] a, input [7:0] b);
            logic [7:0] tmp;
            tmp = a ^ b;
            calc = tmp + 1'b1;
        endfunction
        logic [7:0] a, b, data;
        assign data = calc(a, b);
    endmodule
    '''
    
    # When - 不展开
    graph_lazy = build_signal_graph(sv_code, "top", expand_functions=False)
    func_nodes = [n for n in graph_lazy.nodes if n.kind == NodeKind.FUNCTION_CALL]
    assert len(func_nodes) == 1
    
    # When - 展开
    graph_eager = build_signal_graph(sv_code, "top", expand_functions=True)
    func_nodes = [n for n in graph_eager.nodes if n.kind == NodeKind.FUNCTION_CALL]
    assert len(func_nodes) == 0  # 已展开
    
    # 验证展开后的节点
    assert graph_eager.has_node("top.calc.tmp")
    assert graph_eager.has_edge("top.a", "top.calc.tmp")
```

**实现** (Green):
```python
def expand_function(self, func_name: str) -> List[TraceEdge]:
    """展开函数体，返回替换边"""
    func_body = self._semantic_adapter.get_function_body(func_name)
    
    # 1. 解析函数体
    # 2. 追踪返回值信号
    # 3. 构建展开后的节点和边
    # 4. 返回替换边列表
```

---

## 测试验证矩阵

| 功能 | 测试用例数 | 覆盖场景 |
|------|-----------|---------|
| NodeKind 扩展 | 2 | EXPRESSION, FUNCTION_CALL |
| TraceNode 扩展 | 5 | expression, operands, signals, function_name, condition |
| ExpressionBuilder | 4 | build_expression, build_function_call, build_conditional, 错误处理 |
| Handler - 二元表达式 | 10 | + - * / & \| ^ == != < > && \|\| << >> |
| Handler - 条件表达式 | 1 | sel ? a : b |
| Handler - 函数调用 | 2 | 普通函数, 系统函数 |
| Handler - 成员访问 | 2 | a.b, a[3] |
| GraphBuilder 集成 | 3 | 简单表达式, 复杂表达式, 回归 |
| expand_function | 2 | 不展开, 展开 |
| **总计** | **33** | |

---

## TDD 循环日历

| 日期 | 任务 | 目标 |
|------|------|------|
| 2026-05-25 | P1.1 NodeKind 扩展 | 2 测试通过 |
| 2026-05-25 | P1.2 TraceNode 扩展 | 5 测试通过 |
| 2026-05-26 | P2.1 ExpressionBuilder 骨架 | 测试通过 |
| 2026-05-26 | P2.2 build_expression | 测试通过 |
| 2026-05-26 | P2.3 build_function_call | 测试通过 |
| 2026-05-27 | P2.4 build_conditional | 测试通过 |
| 2026-05-27 | P3.1 AddExpression | 测试通过 |
| 2026-05-28 | P3.2 其他二元表达式 (10个) | 10 测试通过 |
| 2026-05-29 | P3.3 ConditionalExpression | 测试通过 |
| 2026-05-29 | P3.4 CallExpression | 测试通过 |
| 2026-05-30 | P4 GraphBuilder 集成 | 3 测试通过 |
| 2026-05-30 | P5 expand_function | 2 测试通过 |
| 2026-05-31 | 回归测试 | 确保 834 测试通过 |

---

## 备注

1. **每个任务必须先写失败测试，再实现**
2. **实现后必须运行所有测试，确保不破坏现有功能**
3. **每天结束前运行完整测试套件**
4. **遇到阻塞及时反馈**