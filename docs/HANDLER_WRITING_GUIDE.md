# Handler 编写指南 - 从 AST 提取数据

> 创建时间: 2026-05-24
> 状态: 完成

---

## 一、重构对扩展性的好处

### 1.1 统一入口，更易理解

**现有 (双接口)**:
```python
visitor.visit(node)           # 什么时候用？
visitor.get_all_signals(node)  # 什么时候用？
# 需要理解两个 API 的区别
```

**新 (单接口)**:
```python
visitor.extract(node) → SignalResult  # 只有一个入口
# 不需要记忆两个 API
```

### 1.2 注册式分派，新增只需加装饰器

**现有 (双接口)**:
```python
def visit_binary_expression(self, n):  # 需要改这里
    ...

def get_all_binary_expression(self, n):  # 还需要改这里
    ...
```

**新 (单接口)**:
```python
@SignalExpressionVisitor.on('BinaryOp')
def handle_binary_op(self, node):  # 只需要加这里
    ...
```

**扩展示例**: 新增支持 `TaggedTupleExpression`
```python
@SignalExpressionVisitor.on('TaggedTupleExpression')
def handle_tagged_tuple(self, node):
    value = self.extract(node.value) if hasattr(node, 'value') else SignalResult()
    return value
# 就这么简单，不需要改核心逻辑
```

### 1.3 单一职责，更易测试

```python
# SignalResult 可独立测试
result = SignalResult(primary='a', all_signals=['a', 'b'])
assert result.all_signals_unique == ['a', 'b']

# Handler 可独立测试
def test_handle_binary_op():
    result = handle_binary_op(sample_node)
    assert 'a' in result.all_signals
```

### 1.4 未知节点抛异常，不再静默

**现有**:
```python
def generic_visit(self, node):
    pass  # 静默通过，测试可能漏掉
# 问题: 不知道哪个节点类型没支持
```

**新**:
```python
def extract(self, node) -> SignalResult:
    if kind not in self._HANDLERS:
        raise NotImplementedError(f"No handler for {kind}")
# 问题立即暴露，立即修复
```

---

## 二、pyslang AST 基础

### 节点结构

```python
node.kind        # SyntaxKind 枚举
node.left       # 子节点
node.right      # 子节点
node.symbol     # 符号引用
node.name       # 名称字符串
```

### 常见属性获取

```python
getattr(node, 'left', None)   # 安全获取属性
hasattr(node, 'symbol')       # 检查属性存在
node.kind.name                 # 获取类型名 (如 'BinaryOp')
```

---

## 三、Handler 编写模板

```python
@SignalExpressionVisitor.on('NodeTypeName')
def handle_xxx(self, node):
    '''处理 NodeTypeName 类型的 AST 节点'''
    
    # 1. 递归提取子节点
    left_result = self.extract(node.left) if hasattr(node, 'left') else SignalResult()
    right_result = self.extract(node.right) if hasattr(node, 'right') else SignalResult()
    
    # 2. 合并结果
    return left_result.merge(right_result)
```

---

## 四、常用 Handler 示例

### 4.1 二元操作符 (BinaryOp)

**pyslang 节点**:
```python
node.left        # 左侧操作数
node.right       # 右侧操作数
node.op          # 操作符 (+, -, *, /, ...)
```

**Handler**:
```python
@SignalExpressionVisitor.on('BinaryOp')
def handle_binary_op(self, node):
    left = self.extract(node.left)
    right = self.extract(node.right)
    return left.merge(right)
```

**示例**: `a + b*c`
```
BinaryOp(+)
├── left: NamedValue('a')
└── right: BinaryOp(*)
    ├── left: NamedValue('b')
    └── right: NamedValue('c')

处理流程:
1. handle_binary_op(a + b*c)
   left = extract(a) → ['a']
   right = extract(b*c) → 递归 → ['b', 'c']
   return merge(['a'], ['b', 'c']) → ['a', 'b', 'c']
```

### 4.2 单目操作符 (UnaryOp)

**pyslang 节点**:
```python
node.expression   # 操作数
```

**Handler**:
```python
@SignalExpressionVisitor.on('UnaryOp')
def handle_unary_op(self, node):
    expr = self.extract(node.expression)
    return expr
```

### 4.3 条件表达式 (ConditionalOp)

**pyslang 节点**:
```python
node.condition           # 条件
node.true_expression    # 真分支
node.false_expression   # 假分支
```

**Handler**:
```python
@SignalExpressionVisitor.on('ConditionalOp')
def handle_conditional_op(self, node):
    cond = self.extract(node.condition)
    true_br = self.extract(node.true_expression)
    false_br = self.extract(node.false_expression)
    return cond.merge(true_br).merge(false_br)
```

**示例**: `en ? a : b`
```
ConditionalOp
├── condition: NamedValue('en')
├── true_expression: NamedValue('a')
└── false_expression: NamedValue('b')

处理结果: ['en', 'a', 'b']
```

### 4.4 命名值 (NamedValueExpression)

**pyslang 节点**:
```python
node.symbol     # 符号对象 (有 .name 属性)
```

**Handler**:
```python
@SignalExpressionVisitor.on('NamedValueExpression')
def handle_named_value(self, node):
    if hasattr(node, 'symbol') and node.symbol:
        name = node.symbol.name
        return SignalResult(primary=name, all_signals=[name])
    return SignalResult()
```

### 4.5 数字常量 (NumericLiteral)

**pyslang 节点**:
```python
node.value       # 数字值字符串
```

**Handler**:
```python
@SignalExpressionVisitor.on('NumericLiteral')
def handle_numeric_literal(self, node):
    # 数字常量不是信号，返回空
    return SignalResult()
```

### 4.6 括号表达式 (ParenthesisExpression)

**pyslang 节点**:
```python
node.expression   # 括号内的表达式
```

**Handler**:
```python
@SignalExpressionVisitor.on('ParenthesisExpression')
def handle_parenthesis(self, node):
    return self.extract(node.expression)
```

---

## 五、扩展示例

### 新增支持 TaggedTupleExpression

**Step 1: 了解 AST 结构**
```python
node.kind.name  # 'TaggedTupleExpression'
node.tag        # 标签名
node.value      # 值
```

**Step 2: 编写 Handler**
```python
@SignalExpressionVisitor.on('TaggedTupleExpression')
def handle_tagged_tuple(self, node):
    value = self.extract(node.value) if hasattr(node, 'value') else SignalResult()
    return value
```

**Step 3: 测试**
```python
result = visitor.extract(tagged_tuple_node)
assert result.all_signals == ['expected', 'signals']
```

**Step 4: 提交**
```bash
git add -A && git commit -m "feat: support TaggedTupleExpression"
```

---

## 六、最佳实践

### 6.1 递归终止条件

```python
def extract(self, node):
    if node is None:
        return SignalResult()  # 空节点返回空结果
    
    kind = self._get_kind_name(node)
    if kind not in self._HANDLERS:
        raise NotImplementedError(...)  # 未知节点抛异常
```

### 6.2 安全获取属性

```python
# 使用 hasattr 检查属性存在
if hasattr(node, 'left') and node.left:
    left = self.extract(node.left)
else:
    left = SignalResult()
```

### 6.3 合并结果

```python
# 使用 merge() 合并子节点结果
return left_result.merge(right_result)
```

### 6.4 返回值语义

```python
SignalResult:
    primary: 赋值目标信号 (如 'q' 在 'q = ...')
    all_signals: 所有涉及信号 (包括中间信号)

对于提取信号名:
    primary = None (除非你知道这是赋值目标)
    all_signals = [所有信号列表]
```

---

## 七、对比: 旧方法 vs 新方法

### 旧方法

```python
def visit_binary_expression(self, n):
    if n.op == '+' or n.op == '-':
        return self.visit(n.left)
    return None

def get_all_binary_expression(self, n):
    left = self.get_all_signals(n.left)
    right = self.get_all_signals(n.right)
    return left + right

# 问题: 逻辑分散，visit() 和 get_all_signals() 可能不一致
```

### 新方法

```python
@SignalExpressionVisitor.on('BinaryOp')
def handle_binary_op(self, node):
    left = self.extract(node.left)
    right = self.extract(node.right)
    return left.merge(right)

# 优点: 逻辑集中，一致性由框架保证
```

---

## 八、SignalResult 合并语义

```python
@dataclass(frozen=True)
class SignalResult:
    primary: Optional[str] = None
    all_signals: List[str] = field(default_factory=list)
    
    def merge(self, other: 'SignalResult') -> 'SignalResult':
        """合并两个结果"""
        return SignalResult(
            primary=self.primary or other.primary,  # 取第一个非 None
            all_signals=self.all_signals + other.all_signals  # 拼接
        )
```

**合并示例**:
```python
# a + b*c
left = SignalResult(primary='a', all_signals=['a'])
right = SignalResult(primary='b', all_signals=['b', 'c'])
result = left.merge(right)
# result.all_signals = ['a', 'b', 'c']
```