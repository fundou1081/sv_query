# 底层抽象对比分析

**日期**: 2026-05-24

---

## 一、sv_query 现有底层抽象

### 1.1 BaseVisitor 架构

```python
class BaseVisitor(ABC):
    def visit(self, node):
        """分发到 visit_xxx"""
    
    def generic_visit(self, node):
        """通用递归 - 硬编码子节点属性名"""
        for attr in ['body', 'statement', 'statements', 'items']:
            if hasattr(node, attr):
                child = getattr(node, attr)
                # 遍历
```

### 1.2 问题

| 问题 | 说明 |
|------|------|
| **硬编码子节点属性** | `['body', 'statement', 'statements', 'items']` 固定 |
| **遍历逻辑分散** | 每个 visit_ 方法自己控制遍历 |
| **与 pyslang 耦合** | 如果 pyslang 节点结构变化，代码需要改 |
| **策略不灵活** | 只有一种遍历方式（DFS） |

### 1.3 SignalExpressionVisitor

```python
class SignalExpressionVisitor(BaseVisitor):
    # 45 个 visit_ 方法
    def visit_identifier_name(self, node):
        return self.visit(node.left)  # 手动递归
    
    def visit_assignment_expression(self, node):
        left_result = self.extract(node.left)  # 手动调用
        right_result = self.extract(node.right)
        return left_result.merge(right_result)
```

**问题**：
- handler 混入了遍历逻辑
- 子节点处理方式不统一
- 新增类型需要写很多样板代码

---

## 二、新架构底层抽象

### 2.1 基于 pyslang.visit()

```python
class Visitor:
    def extract(self, node):
        """使用 pyslang 原生遍历"""
        node.visit(self._callback)
    
    def _callback(self, node):
        handler = self._handlers[node.kind.name]
        result = handler(node)
        self._result.merge(result)
        return VisitAction.Advance
```

**优点**：
- 子节点遍历由 pyslang 处理
- 不需要硬编码属性名

**缺点**：
- 策略固定（DFS）
- Callback 模式不够灵活

---

## 三、更好的抽象设计

### 3.1 核心问题

现有设计混淆了：
1. **遍历策略**（DFS/BFS/Selective）
2. **节点访问**（获取子节点）
3. **业务逻辑**（处理特定节点类型）

### 3.2 分离关注点

```
┌─────────────────────────────────────────────────────────┐
│                    Task (业务逻辑)                        │
│                         │                               │
│                         ▼                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │              TraversalStrategy                     │  │
│  │  - DFS (深度优先)                                   │  │
│  │  - BFS (广度优先)                                   │  │
│  │  - Selective (选择性)                              │  │
│  │  - Bidirectional (双向)                            │  │
│  └───────────────────────────────────────────────────┘  │
│                         │                               │
│                         ▼                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │              NodeAccessor                          │  │
│  │  - 获取子节点                                      │  │
│  │  - 获取属性                                        │  │
│  │  - pyslang API 封装                                │  │
│  └───────────────────────────────────────────────────┘  │
│                         │                               │
│                         ▼                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │              NodeHandler                           │  │
│  │  - @on('SyntaxKind')                              │  │
│  │  - 只处理当前节点，不涉及遍历                       │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 3.3 各层职责

| 层 | 职责 | 接口 |
|----|------|------|
| **TraversalStrategy** | 控制遍历顺序 | `traverse(node, callback)` |
| **NodeAccessor** | 获取子节点 | `get_children(node)` → `[child]` |
| **NodeHandler** | 处理单个节点 | `handle(node)` → `Result` |

### 3.4 NodeAccessor 示例

```python
class PyslangNodeAccessor:
    """封装 pyslang 节点访问"""
    
    @staticmethod
    def get_children(node):
        """获取所有子节点（使用 pyslang.visit）"""
        children = []
        def callback(n):
            if n is not node:  # 不包含自己
                children.append(n)
            return VisitAction.Advance
        node.visit(callback)
        return children
    
    @staticmethod
    def get_attribute(node, name):
        """获取节点属性"""
        return getattr(node, name, None)
    
    @staticmethod
    def get_kind_name(node):
        """获取节点类型名"""
        return node.kind.name
```

### 3.5 TraversalStrategy 示例

```python
class DFSTraversal:
    """深度优先遍历"""
    def traverse(self, node, accessor, callback):
        stack = [node]
        while stack:
            current = stack.pop()
            callback(current)
            children = accessor.get_children(current)
            stack.extend(reversed(children))  # 反转保持顺序

class BFSTraversal:
    """广度优先遍历"""
    def traverse(self, node, accessor, callback):
        queue = deque([node])
        while queue:
            current = queue.popleft()
            callback(current)
            children = accessor.get_children(current)
            queue.extend(children)

class SelectiveTraversal:
    """选择性遍历 - 只遍历特定类型"""
    def traverse(self, node, accessor, callback, kind_filter):
        stack = [node]
        while stack:
            current = stack.pop()
            if accessor.get_kind_name(current) in kind_filter:
                callback(current)
            children = accessor.get_children(current)
            stack.extend(reversed(children))
```

### 3.6 NodeHandler 示例

```python
class SignalExtractor:
    def __init__(self, traversal: TraversalStrategy, accessor: NodeAccessor):
        self.traversal = traversal
        self.accessor = accessor
        self.handlers = {}
        self._collect_handlers()
    
    def handle(self, node):
        """处理单个节点 - handler 不涉及遍历"""
        kind = self.accessor.get_kind_name(node)
        if kind in self.handlers:
            return self.handlers[kind](node)
        return SignalResult.empty()
    
    @on('IdentifierName')
    def handle_identifier(self, node):
        ident = self.accessor.get_attribute(node, 'identifier')
        if ident:
            val = self.accessor.get_attribute(ident, 'value')
            if val:
                return SignalResult(primary=str(val).strip())
        return SignalResult.empty()
```

### 3.7 组合使用

```python
# 提取信号 - 使用 DFS + Selective
extractor = SignalExtractor(
    traversal=DFSTraversal(),
    accessor=PyslangNodeAccessor()
)
# 只追踪表达式节点
result = extractor.extract(node, kind_filter=EXPRESSION_KINDS)

# 提取所有 Port - 使用 BFS
port_extractor = SignalExtractor(
    traversal=BFSTraversal(),
    accessor=PyslangNodeAccessor()
)
result = port_extractor.extract(node, kind_filter={'AnsiPort', 'PortDeclaration'})

# 追踪数据流 - 使用 DFS + 从特定节点开始
flow_extractor = SignalExtractor(
    traversal=DFSTraversal(),
    accessor=PyslangNodeAccessor()
)
result = flow_extractor.extract_from(node, start_kinds={'AssignmentExpression'})
```

---

## 四、方案对比

### 4.1 架构对比

| 特性 | sv_query 现有 | pyslang.visit | 分离设计 |
|------|---------------|---------------|----------|
| 遍历策略 | 固定 DFS | 固定 DFS | 可切换 |
| 子节点获取 | 硬编码属性 | pyslang 自动 | 抽象层 |
| Handler 复杂度 | 高（含遍历） | 中 | 低（仅逻辑） |
| 新增类型成本 | 中 | 低 | 低 |
| 测试难度 | 高 | 中 | 低 |

### 4.2 复杂度对比

| 方案 | 代码行数估计 | 维护成本 |
|------|-------------|----------|
| sv_query 现有 | ~10000 | 高 |
| pyslang.visit | ~7000 | 中 |
| 分离设计 | ~5000 | 低 |

---

## 五、推荐方案

### 5.1 渐进式迁移

**阶段 1**：保持现有框架，引入 TraversalStrategy 抽象

```python
class SignalExpressionVisitor:
    def __init__(self, traversal=DFSTraversal()):
        self.traversal = traversal
    
    def extract(self, node):
        self.traversal.traverse(node, self._accessor, self._handle_node)
        return self._result
```

**阶段 2**：拆分 NodeAccessor

```python
class PyslangAccessor:
    @staticmethod
    def get_children(node):
        # 使用 pyslang.visit 或反射
        pass
```

**阶段 3**：简化 Handler

```python
@on('IdentifierName')
def handle_identifier(self, node):
    # 只处理当前节点，不涉及遍历
    pass
```

### 5.2 核心价值

| 抽象 | 价值 |
|------|------|
| TraversalStrategy | 遍历策略可切换 |
| NodeAccessor | 与 pyslang 解耦 |
| NodeHandler | 职责单一，易测试 |

### 5.3 风险

| 风险 | 缓解 |
|------|------|
| 过度设计 | 保持简单，渐进增强 |
| 性能损失 | 使用 pyslang 原生 API |
| 复杂度 | 分离后更易理解 |

---

## 六、结论

**底层抽象应该分离**：

1. **NodeAccessor** - 封装 pyslang 节点访问
2. **TraversalStrategy** - 控制遍历策略（DFS/BFS/Selective）
3. **NodeHandler** - 处理单个节点，不涉及遍历

**好处**：
- 遍历策略可切换
- 与 pyslang 解耦
- Handler 简洁易测试
- 便于渐进式迁移