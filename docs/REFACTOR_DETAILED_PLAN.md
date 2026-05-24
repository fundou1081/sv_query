# SignalExpressionVisitor 单 dispatch 重构 - 细化方案

> 创建时间: 2026-05-24
> 项目路径: /Users/fundou/my_dv_proj/sv_query
> 状态: 细化完成，待实施

---

## 一、目标架构

### 现有 (双接口)

```python
# 两个独立方法，两套 handler
visitor.visit(node) → Optional[str]           # 单信号
visitor.get_all_signals(node) → List[str]     # 多信号

# 每种节点类型需要 2 个 handler
visit_binary_expression(node)           → 'a'
get_all_binary_expression(node)           → ['a', 'b']
```

### 目标 (单接口)

```python
# 单一方法，统一结果
visitor.extract(node) → SignalResult
    ├── primary: Optional[str]      # 赋值目标
    ├── all_signals: List[str]       # 所有信号
    └── all_signals_unique: List[str]  # 去重

# 每种节点类型只需 1 个 handler
@SignalExpressionVisitor.on('BinaryOp')
def handle_binary_op(self, node):
    left = self.extract(node.left)
    right = self.extract(node.right)
    return SignalResult(primary=left.primary, all_signals=left.all_signals + right.all_signals)
```

---

## 二、SignalResult 结构 (已实现 ✅)

```python
@dataclass(frozen=True)
class SignalResult:
    primary: Optional[str] = None
    all_signals: List[str] = field(default_factory=list)
    
    @property
    def all_signals_unique(self) -> List[str]:
        return list(dict.fromkeys(self.all_signals))
    
    @property
    def is_empty(self) -> bool:
        return len(self.all_signals_unique) == 0
    
    def merge(self, other: 'SignalResult') -> 'SignalResult':
        """合并两个结果"""
        return SignalResult(
            primary=self.primary or other.primary,
            all_signals=self.all_signals + other.all_signals
        )
```

文件: `src/trace/core/visitors/signal_result.py` ✅

---

## 三、新增基础设施

### 3.1 注册装饰器

```python
class SignalExpressionVisitor:
    # 注册表
    _HANDLERS: ClassVar[Dict[str, Callable]] = {}
    
    @classmethod
    def on(cls, kind_name: str):
        """@SignalExpressionVisitor.on('BinaryOp')"""
        def decorator(func):
            cls._HANDLERS[kind_name] = func
            return func
        return decorator
```

### 3.2 统一入口方法

```python
def extract(self, node) -> SignalResult:
    """单一入口方法"""
    if node is None:
        return SignalResult()
    
    kind_name = self._get_kind_name(node)
    
    if kind_name in self._HANDLERS:
        return self._HANDLERS[kind_name](self, node)
    
    raise NotImplementedError(
        f"No handler for {kind_name}. "
        f"Supported: {list(self._HANDLERS.keys())}"
    )

def _get_kind_name(self, node) -> str:
    """获取节点类型名"""
    kind = getattr(node, 'kind', None)
    if kind and hasattr(kind, 'name'):
        return kind.name
    return str(kind) if kind else ""
```

### 3.3 双轨判断

```python
def extract(self, node) -> SignalResult:
    kind = self._get_kind_name(node)
    
    # 新路径 (已迁移的 handler)
    if self._dispatch_enabled and kind in self._HANDLERS:
        return self._HANDLERS[kind](self, node)
    
    # 旧路径回退 (迁移期间)
    return self._legacy_extract(node)
```

---

## 四、Handler 迁移示例

### NamedValueExpression (✅ POC 已完成)

**旧方法**:
```python
def visit_named_value_expression(self, n):
    if hasattr(n, 'symbol') and n.symbol:
        return n.symbol.name
    return None

def get_all_named_value_expression(self, n):
    if hasattr(n, 'symbol') and n.symbol:
        return [n.symbol.name]
    return []
```

**新方法**:
```python
@SignalExpressionVisitor.on('NamedValueExpression')
def handle_named_value(self, node):
    if hasattr(node, 'symbol') and node.symbol:
        name = node.symbol.name
        return SignalResult(primary=name, all_signals=[name])
    return SignalResult()
```

### BinaryOp

**旧方法**:
```python
def visit_binary_expression(self, n):
    if n.op == '+' or n.op == '-':
        return self.visit(n.left)
    return None

def get_all_binary_expression(self, n):
    left = self.get_all_signals(n.left)
    right = self.get_all_signals(n.right)
    return left + right
```

**新方法**:
```python
@SignalExpressionVisitor.on('BinaryOp')
def handle_binary_op(self, node):
    left_result = self.extract(node.left)
    right_result = self.extract(node.right)
    return left_result.merge(right_result)
```

### ConditionalOp

**旧方法**:
```python
def visit_conditional_expression(self, n):
    return None

def get_all_conditional_expression(self, n):
    cond = self.get_all_signals(n.condition)
    true_br = self.get_all_signals(n.true_expression)
    false_br = self.get_all_signals(n.false_expression)
    return cond + true_br + false_br
```

**新方法**:
```python
@SignalExpressionVisitor.on('ConditionalOp')
def handle_conditional_op(self, node):
    cond = self.extract(node.condition)
    true_br = self.extract(node.true_expression)
    false_br = self.extract(node.false_expression)
    return cond.merge(true_br).merge(false_br)
```

---

## 五、增量迁移策略

### Phase 1: 基础设施 ✅/⬜

| 步骤 | 状态 | 说明 |
|------|------|------|
| SignalResult 类 | ✅ 完成 | 已有 |
| 注册装饰器 | ⬜ 待实现 | @on 装饰器 |
| extract() 方法 | ⬜ 待实现 | 统一入口 |
| _get_kind_name() | ⬜ 待实现 | 辅助方法 |
| 双轨判断 | ⬜ 待实现 | _dispatch_enabled |

### Phase 2: 双轨运行 (关键)

每次迁移一个 handler 时:

1. 新增 `@on` 装饰的 handler
2. 旧方法保留，加 `USE_NEW_DISPATCH` 判断
3. `extract()` 优先调用新 handler，回退旧方法

```python
# signal_expression_visitor.py

class SignalExpressionVisitor:
    _dispatch_enabled = False  # 默认关闭
    
    def extract(self, node) -> SignalResult:
        if node is None:
            return SignalResult()
        
        kind = self._get_kind_name(node)
        
        # 新路径
        if self._dispatch_enabled and kind in self._HANDLERS:
            return self._HANDLERS[kind](self, node)
        
        # 旧路径回退
        return self._legacy_extract(node)
    
    def _legacy_extract(self, node) -> SignalResult:
        """迁移期间回退到旧方法"""
        name = self.visit(node)
        all_sigs = self.get_all_signals(node)
        return SignalResult(primary=name, all_signals=all_sigs)
```

### Phase 3: 逐个迁移 (40+ handlers)

**迁移顺序** (从简单到复杂):

| 序号 | Handler | 复杂度 | 状态 |
|------|---------|--------|------|
| 1 | NamedValueExpression | 简单 | ✅ POC |
| 2 | BinaryOp | 简单 | ⬜ 待迁移 |
| 3 | UnaryOp | 简单 | ⬜ 待迁移 |
| 4 | ConditionalOp | 中等 | ⬜ 待迁移 |
| 5 | ... | ... | ⬜ |

**迁移步骤**:
```python
for each handler:
    1. 阅读旧方法，理解逻辑
    2. 编写新方法 (使用 extract() 递归)
    3. 设置 _dispatch_enabled = True
    4. 运行测试，验证结果一致
    5. 提交
    6. 移除旧方法 (可选，保留也可)
```

### Phase 4: 切换默认

当所有 handler 都迁移完成后:

1. 设置 `_dispatch_enabled = True` 默认
2. 移除 `_legacy_extract()`
3. 移除旧方法 (`visit_*` 和 `get_all_*`)
4. 移除别名映射 `alias_map`

---

## 六、文件变更计划

| 步骤 | 文件 | 变更 |
|------|------|------|
| 1 | signal_result.py | ✅ 已存在 |
| 2 | signal_expression_visitor.py | 添加 @on 装饰器 + extract() |
| 3 | signal_expression_visitor.py | 迁移每个 handler |
| 4 | signal_expression_visitor.py | 移除旧方法 |

---

## 七、测试策略

| 阶段 | 测试 |
|------|------|
| 增量迁移期间 | 834 现有测试全部通过 |
| 每个 handler 迁移后 | 验证新旧方法结果一致 |
| 最终切换 | 压力测试 + 边界情况 |

**验证方法**:
```python
# 验证新旧方法结果一致
def test_handler_migration(handler_name):
    for node in test_cases:
        old_result = old_method(node)
        new_result = new_method(node)
        assert old_result == new_result
```

---

## 八、风险控制

| 风险 | 缓解措施 |
|------|----------|
| 迁移出错 | 增量迁移，每次只改一个 handler |
| 性能下降 | extract() 缓存结果 (memoization) |
| 遗漏 handler | `_dispatch_enabled` flag 控制回退 |
| 测试失败 | 自动化回归测试 |

---

## 九、提交节奏

每次迁移 5-10 个 handler 提交一次:

```bash
git commit -m "refactor: migrate N handlers to single dispatch

Migrated:
- NamedValueExpression
- BinaryOp
- UnaryOp
- ConditionalOp
- ..."
```

---

## 十、与 DataFlow/ControlFlow 的关系

**独立关系**:
- Visitor 重构 → 可独立进行
- DataFlow 实现 → 可独立进行
- 两者可以并行开发

**依赖关系**:
- DataFlow 只需使用 `extract()` 接口
- 不关心内部是单 dispatch 还是双 dispatch
- `SignalResult` 已有，POC 已完成

**建议**:
1. 先完成 Visitor 重构 (代码质量提升)
2. 再实现 DataFlow (基于更清晰的接口)

---

## 十一、快速开始

如果确定开始，可以按以下顺序执行:

```bash
# Step 1: 添加基础设施
# - @on 装饰器
# - extract() 方法
# - _dispatch_enabled flag

# Step 2: 迁移第一个 handler (NamedValueExpression)
git commit -m "refactor: add single dispatch infrastructure"

# Step 3: 验证测试
cd sim && python -m pytest tests/ -x -q

# Step 4: 继续迁移下一个 handler
# ... 重复直到完成
```