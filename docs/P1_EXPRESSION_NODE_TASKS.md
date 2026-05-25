# P1 - Expression 节点实现任务清单

> 创建时间: 2026-05-25
> 状态: 开发中
> 依赖: TODO.md

---

## 任务分解

### 1. TraceNode 扩展

**文件**: `src/trace/core/graph/models.py`

**改动**:
```python
@dataclass
class TraceNode:
    # ... 现有字段 ...
    
    # 新增字段
    expression: Optional[str] = None    # "a + b", "sel ? a : b"
    operands: List[str] = []            # 顶层操作数
    signals: List[str] = []              # 所有信号引用
    function_name: Optional[str] = None
    function_return: bool = False
    condition: Optional[str] = None
    true_branch: Optional[str] = None
    false_branch: Optional[str] = None
```

### 2. NodeKind 扩展

**文件**: `src/trace/core/graph/models.py`

**改动**:
```python
class NodeKind:
    # ... 现有 ...
    
    # 新增
    EXPRESSION = auto()     # 表达式节点
    FUNCTION_CALL = auto()  # 函数调用节点
```

**状态**: 待开发

---

### 3. ExpressionBuilder 核心类

**文件**: `src/trace/core/builder/expression_builder.py` (新建)

**职责**:
- 表达式 → TraceNode 转换
- 创建 EXPRESSION 节点
- 添加 operand → expr → result 边

**接口**:
```python
class ExpressionBuilder:
    def build_expression(self, node, target_signal: str) -> Optional[TraceNode]:
        """构建表达式节点，返回表达式节点 ID"""
        
    def build_function_call(self, node, target_signal: str) -> Optional[TraceNode]:
        """构建函数调用节点"""
        
    def build_conditional(self, node, target_signal: str) -> Optional[TraceNode]:
        """构建条件表达式节点"""
```

**依赖**: SignalExpressionVisitor

**状态**: 待开发

---

### 4. Handler 补全清单

#### 4.1 表达式类

| Handler | 状态 | 说明 |
|---------|------|------|
| AddExpression | 待开发 | a + b |
| SubtractExpression | 待开发 | a - b |
| MultiplyExpression | 待开发 | a * b |
| DivideExpression | 待开发 | a / b |
| BinaryAndExpression | 待开发 | a & b |
| BinaryOrExpression | 待开发 | a \| b |
| BinaryXorExpression | 待开发 | a ^ b |
| EqualityExpression | 待开发 | a == b |
| InequalityExpression | 待开发 | a != b |
| LessThanExpression | 待开发 | a < b |
| GreaterThanExpression | 待开发 | a > b |
| LogicalAndExpression | 待开发 | a && b |
| LogicalOrExpression | 待开发 | a \|\| b |
| ArithmeticShiftLeftExpression | 待开发 | a << b |
| ArithmeticShiftRightExpression | 待开发 | a >> b |
| ConditionalExpression | 待开发 | sel ? a : b |

#### 4.2 函数/调用类

| Handler | 状态 | 说明 |
|---------|------|------|
| CallExpression | 待开发 | 函数调用 |
| FunctionDeclaration | 待开发 | 函数定义 |
| TaskDeclaration | 待开发 | Task 定义 |
| ReturnStatement | 待开发 | return 语句 |

#### 4.3 成员访问类

| Handler | 状态 | 说明 |
|---------|------|------|
| MemberAccessExpression | 待开发 | a.b |
| ElementSelectExpression | 待开发 | a[3] 或 a[7:0] |

#### 4.4 语句类

| Handler | 状态 | 说明 |
|---------|------|------|
| CaseStatement | 待开发 | case 语句 |
| ConditionalStatement | 待开发 | if 语句 |
| ForLoopStatement | 待开发 | for 循环 |
| WhileLoopStatement | 待开发 | while 循环 |

---

### 5. GraphBuilder 集成

**文件**: `src/trace/core/graph_builder.py`

**改动**:
1. 导入 ExpressionBuilder
2. 在处理 ContinuousAssign/Assignment 时使用 ExpressionBuilder
3. 创建表达式节点链

**状态**: 待开发

---

### 6. expand_function() 实现

**文件**: `src/trace/core/builder/function_expander.py` (新建)

**职责**:
- 获取函数定义
- 展开函数体为实际逻辑
- 替换 FUNCTION_CALL 节点

**接口**:
```python
def expand_function(func_name: str, call_node_id: str) -> List[TraceEdge]:
    """展开函数，返回替换用的边列表"""
```

**状态**: 待开发

---

## 优先级排序

1. **P1.1**: TraceNode 扩展 + NodeKind 扩展
2. **P1.2**: ExpressionBuilder 核心类
3. **P1.3**: 基础表达式 Handler (AddExpression 等)
4. **P1.4**: ConditionalExpression Handler
5. **P1.5**: FunctionCall Handler
6. **P1.6**: GraphBuilder 集成
7. **P1.7**: expand_function() 实现

---

## 测试用例

### 基础表达式测试
```systemverilog
module test;
    logic [7:0] a, b, data;
    assign data = a + b;
endmodule
```

预期结果:
- 节点: data, a, b, expr_add_1
- 边: a→expr_add_1, b→expr_add_1, expr_add_1→data

### 条件表达式测试
```systemverilog
module test;
    logic sel, a, b, data;
    assign data = sel ? a : b;
endmodule
```

预期结果:
- 节点: data, sel, a, b, cond_ternary_1
- 边: sel→cond_ternary_1, a→cond_ternary_1, b→cond_ternary_1, cond_ternary_1→data

### 函数调用测试
```systemverilog
module test;
    function [7:0] calc(input [7:0] a, input [7:0] b);
        calc = a + b;
    endfunction
    logic [7:0] a, b, data;
    assign data = calc(a, b);
endmodule
```

预期结果:
- 节点: data, a, b, func_calc_1
- 边: a→func_calc_1, b→func_calc_1, func_calc_1→data

---

## 备注

- Handler 补全需要验证 pyslang 中存在对应类型
- 使用 `hasattr(SyntaxKind, 'HandlerName')` 确认后再创建
- 每个 handler 开发后需要添加对应测试用例