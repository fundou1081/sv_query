# 新架构设计：基于 pyslang.visit() 的 @on Handler

**日期**: 2026-05-24
**状态**: 设计中
**基础**: pyslang.SyntaxNode.visit() API

---

## 一、核心发现

### pyslang.visit() 已实现遍历

```python
node.visit(callback)
# callback 返回 VisitAction 控制遍历
```

**不需要自己实现子节点反射遍历！**

---

## 二、新架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│  extract(node) -> SignalResult                               │
│                                                             │
│  node.visit(callback)  ← pyslang 原生遍历                     │
│       │                                                      │
│       └── callback(node)                                    │
│               │                                             │
│               ├── handler = _HANDLERS[node.kind.name]       │
│               │                                             │
│               └── handler(node) → SignalResult              │
│                                                             │
│  pyslang 自动遍历所有子节点                                  │
│  handler 只处理当前节点逻辑                                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

```python
class SignalExpressionVisitor:
    """基于 pyslang.visit() 的信号提取 visitor"""
    
    # ========== 核心机制 ==========
    
    def extract(self, node) -> SignalResult:
        """主入口 - 使用 pyslang.visit() 遍历"""
        if node is None:
            return SignalResult()
        
        # 使用 pyslang 原生遍历
        self._current_result = SignalResult()
        node.visit(self._visit_callback)
        return self._current_result
    
    def _visit_callback(self, node) -> VisitAction:
        """pyslang.visit() 的回调函数"""
        kind_name = node.kind.name
        
        # 查找 handler
        if kind_name in self._HANDLERS:
            handler = self._HANDLERS[kind_name]
            result = handler(node)
            
            # 处理返回值
            if isinstance(result, SignalResult):
                self._current_result.merge(result)
        
        return VisitAction.Advance
    
    # ========== @on handler 注册 ==========
    
    @on('IdentifierName')
    def handle_identifier_name(self, node) -> SignalResult:
        """IdentifierName: 提取信号名"""
        identifier = getattr(node, 'identifier', None)
        if identifier:
            name = getattr(identifier, 'value', None)
            if name:
                return SignalResult(primary=str(name).strip())
        return SignalResult()
    
    @on('AssignmentExpression')
    def handle_assignment_expression(self, node) -> SignalResult:
        """AssignmentExpression: 赋值表达式"""
        # 不需要手动处理子节点！
        # pyslang 会自动遍历
        left = getattr(node, 'left', None)
        if left:
            return SignalResult(primary=self._get_signal_name(left))
        return SignalResult()
```

### 2.3 @on 装饰器

```python
def on(kind_name: str):
    """@on 装饰器 - 注册 handler"""
    def decorator(func):
        func._kind_name = kind_name
        return func
    return decorator
```

### 2.4 handler 注册

```python
class SignalExpressionVisitor:
    def __init__(self):
        self._HANDLERS = {}
        self._collect_handlers()
    
    def _collect_handlers(self):
        """收集所有 @on 装饰的 handler"""
        for name in dir(self):
            if name.startswith('_'):
                continue
            method = getattr(self, name, None)
            if callable(method) and hasattr(method, '_kind_name'):
                kind_name = method._kind_name
                self._HANDLERS[kind_name] = method
```

---

## 三、与旧架构对比

| 特性 | 旧 visitor | 新 @on + pyslang.visit() |
|------|-----------|--------------------------|
| 遍历方式 | 手动递归 self.visit() | pyslang 原生 visit() |
| 子节点处理 | handler 手动处理 | 框架自动处理 |
| dispatch | 方法名查找 | node.kind.name 查找 |
| 返回值 | `Optional[str]` | `SignalResult` |
| 代码量 | 45 个方法 | 536 个简化 handlers |
| 与 pyslang 对齐 | 低 | 高 |

---

## 四、实现步骤

### 阶段 1：核心框架

```python
# 1. 实现 extract() + _visit_callback
# 2. 实现 @on 装饰器
# 3. 实现 _collect_handlers() 注册

def extract(self, node) -> SignalResult:
    if node is None:
        return SignalResult()
    self._current_result = SignalResult()
    node.visit(self._visit_callback)
    return self._current_result

def _visit_callback(self, node) -> VisitAction:
    kind_name = node.kind.name
    if kind_name in self._HANDLERS:
        result = self._HANDLERS[kind_name](node)
        if isinstance(result, SignalResult):
            self._current_result.merge(result)
    return VisitAction.Advance
```

### 阶段 2：简化 handlers

移除 handler 中手动处理子节点的代码：

```python
# 之前
@on('AssignmentExpression')
def handle_assignment_expression(self, node):
    left = getattr(node, 'left', None)
    right = getattr(node, 'right', None)
    left_result = self.extract(left) if left else SignalResult()
    right_result = self.extract(right) if right else SignalResult()
    return left_result.merge(right_result)

# 之后 - 不需要手动处理子节点
@on('AssignmentExpression')
def handle_assignment_expression(self, node):
    # 只处理当前节点的逻辑
    # 子节点由 pyslang.visit() 自动遍历
    left = getattr(node, 'left', None)
    if left:
        name = self._get_signal_name(left)
        return SignalResult(primary=name)
    return SignalResult()
```

### 阶段 3：测试验证

```bash
pytest tests/ -x -q
```

### 阶段 4：清理

- 删除所有 `visit_` 方法
- 删除旧 dispatch 逻辑

---

## 五、优势总结

### 5.1 代码更简洁

- 不需要手动实现子节点遍历
- handler 逻辑简化
- 减少重复代码

### 5.2 与 pyslang 对齐

- 利用 pyslang 原生 API
- 1:1 对应 SyntaxKind
- 自动跟随 pyslang 更新

### 5.3 可维护性

- Handler 职责单一
- 一致性强
- 新增类型简单

### 5.4 性能

- pyslang.visit() 是 C++ 实现
- 遍历效率高
- 无反射开销

---

## 六、示例：完整 handler

```python
class SignalExpressionVisitor:
    
    def extract(self, node) -> SignalResult:
        """使用 pyslang.visit() 遍历"""
        if node is None:
            return SignalResult()
        self._result = SignalResult()
        node.visit(self._visit)
        return self._result
    
    def _visit(self, node) -> VisitAction:
        """pyslang 遍历回调"""
        handler = self._HANDLERS.get(node.kind.name)
        if handler:
            result = handler(node)
            if result:
                self._result.merge(result)
        return VisitAction.Advance
    
    # ========== Handlers ==========
    
    @on('IdentifierName')
    def handle_identifier_name(self, node) -> SignalResult:
        ident = getattr(node, 'identifier', None)
        if ident:
            val = getattr(ident, 'value', None)
            if val:
                return SignalResult(primary=str(val).strip())
        return SignalResult()
    
    @on('ElementSelectExpression')
    def handle_element_select(self, node) -> SignalResult:
        value = getattr(node, 'value', None)
        selector = getattr(node, 'selector', None)
        if value and selector:
            base = self._get_signal_name(value)
            sel_val = getattr(selector, 'value', None)
            if base and sel_val is not None:
                return SignalResult(primary=f"{base}[{sel_val}]")
        return SignalResult()
    
    @on('MemberAccessExpression')
    def handle_member_access(self, node) -> SignalResult:
        value = getattr(node, 'value', None)
        member = getattr(node, 'member', None)
        if value and member:
            base = self._get_signal_name(value)
            member_name = getattr(member, 'name', None) or str(member)
            if base and member_name:
                return SignalResult(primary=f"{base}.{member_name}")
        return SignalResult()
    
    # ... 其他 handlers 简化 ...
```

---

## 七、VisitAction 进阶用法

### 7.1 Skip - 跳过子节点

```python
@on('StringLiteralExpression')
def handle_string_literal(self, node) -> VisitAction:
    """字符串字面量不需要遍历子节点"""
    return VisitAction.Skip  # 告诉 pyslang 不要遍历子节点
```

### 7.2 Interrupt - 中断遍历

```python
def find_module(self, module_name: str):
    """查找特定模块，找到后中断"""
    def callback(node):
        if node.kind.name == 'ModuleDeclaration':
            header = getattr(node, 'header', None)
            if header:
                name = getattr(header, 'name', None)
                if name and str(name) == module_name:
                    self._found_module = node
                    return VisitAction.Interrupt
        return VisitAction.Advance
    
    self.root.visit(callback)
    return self._found_module
```

---

## 八、结论

**基于 pyslang.visit() 的 @on handler 是最佳方案**：

1. 利用 pyslang 原生遍历 API
2. Handler 职责单一（只处理当前节点）
3. 代码简洁、可维护
4. 性能最优（无反射开销）
5. 与 pyslang 设计理念一致