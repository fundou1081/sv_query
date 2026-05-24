# SignalExpressionVisitor 架构改善提案

> 创建时间: 2026-05-23/24
> 项目路径: /Users/fundou/my_dv_proj/sv_query
> 状态: 待实施

---

## 1. 当前架构问题

### 1.1 双接口重复
- `visit()` 返回 `Optional[str]` (单信号)
- `get_all_signals()` 返回 `List[str]` (多信号)
- 每个节点类型需要两个 handler (如 `visit_binary_expression` + `get_all_binary_expression`)
- 代码重复度高，维护成本大

### 1.2 别名映射分散
```python
# visit() 中的 alias_map
alias_map = {
    'BinaryOp': 'binary_expression',
    'UnaryOp': 'unary',
}

# get_all_signals() 中的 alias_map (内容可能不同!)
alias_map = {
    'BinaryOp': 'binary_expression',
    'UnaryOp': 'unary',
    'ConditionalExpression': 'ConditionalOp',
}
```
- 别名在多处定义，易不同步
- 添加新类型时需要更新多处

### 1.3 回退方法 = 技术债务
- `generic_visit()` 静默处理未知节点
- `get_all_signals_fallback()` 存在
- 表明覆盖不完整，但测试仍会通过

### 1.4 无类型安全
```python
left = getattr(node, 'left', None)
right = getattr(node, 'right', None)
```
- 拼写错误 (`getatrr`) 运行时才暴露
- 节点类型不同，属性可能不同

### 1.5 耦合问题
```python
def __init__(self, adapter: PyslangAdapter):
    self.adapter = adapter  # 用于参数映射、符号解析等
```
- 信号提取与语义分析耦合
- 无法独立测试

### 1.6 分派复杂
- visit() 中混合了: 别名映射、snake_case 转换、Expression 后缀处理
- 新增 handler 需要理解整个分派系统

---

## 2. 理想架构方案

### 2.1 单一结果类型
```python
@dataclass(frozen=True)
class SignalResult:
    primary: Optional[str]           # LHS 赋值目标
    all_signals: List[str]         # 所有信号（含重复）
    all_signals_unique: List[str]  # 去重后信号
    
    def __post_init__(self):
        object.__setattr__(self, 'all_signals_unique', 
            list(dict.fromkeys(self.all_signals)))
    
    @property
    def is_empty(self) -> bool:
        return len(self.all_signals_unique) == 0
```

### 2.2 注册式分派
```python
class SignalVisitor:
    HANDLERS: ClassVar[Dict[str, Callable]] = {}
    
    @classmethod
    def on(cls, kind: str):
        """@SignalVisitor.on('BinaryOp')"""
        def decorator(func):
            cls.HANDLERS[kind] = func
            return func
        return decorator
    
    def extract(self, node) -> SignalResult:
        """单一入口方法"""
        if node is None:
            return SignalResult()
        
        kind_name = getattr(node, 'kind', None)
        if kind_name:
            kind_name = kind_name.name
        
        if kind_name in self.HANDLERS:
            return self.HANDLERS[kind_name](self, node)
        
        raise NotImplementedError(
            f"No handler for {kind_name}. "
            "This node type is not yet supported."
        )
```

### 2.3 单个 Handler 示例
```python
@SignalVisitor.on('BinaryOp')
def handle_binary_op(self, node):
    left_result = self.extract(node.left)
    right_result = self.extract(node.right)
    return SignalResult(
        primary=left_result.primary,
        all_signals=left_result.all_signals + right_result.all_signals
    )

@SignalVisitor.on('ConditionalOp')
def handle_conditional_op(self, node):
    cond = self.extract(node.condition)
    true_br = self.extract(node.true_branch)
    false_br = self.extract(node.false_branch)
    return SignalResult(
        primary=None,
        all_signals=cond.all_signals + true_br.all_signals + false_br.all_signals
    )
```

### 2.4 组合模式 (可选)
```python
class SignalExtractor:
    def extract(self, node) -> SignalResult: ...

class ClockExtractor:
    def extract(self, node) -> Optional[str]: ...

class ContextExtractor:
    def extract(self, node) -> Dict[str, str]: ...

class CompositeVisitor:
    def __init__(self, extractors):
        self.extractors = extractors
    
    def visit(self, node):
        return {type(ext).__name__: ext.extract(node) 
                for ext in self.extractors}
```

---

## 3. 收益对比

| 指标 | 当前 | 改善后 | 改进 |
|------|------|--------|------|
| 每个类型的 handler | 2 个 | 1 个 | -50% 代码 |
| 别名定义位置 | 2+ 处 | 1 处 | -75% |
| 未知节点处理 | 静默通过 | 抛异常 | +安全性 |
| 测试隔离 | 困难 | 容易 | +可测试性 |
| API 清晰度 | 模糊 | 明确 | +可读性 |

---

## 4. 迁移路径

### Step 1: 添加 SignalResult 类
```python
# src/trace/core/visitors/signal_result.py
```
- 新文件，不影响现有代码
- 可独立测试

### Step 2: 添加注册装饰器
```python
class SignalVisitor:
    HANDLERS: dict = {}
    
    @classmethod
    def on(cls, kind: str):
        def decorator(func):
            cls.HANDLERS[kind] = func
            return func
        return decorator
```

### Step 3: 逐步迁移 Handler
- 逐个将 `visit_binary_expression` + `get_all_binary_expression` 合并为 `@SignalVisitor.on('BinaryOp')`
- 每迁移一个，运行测试验证

### Step 4: 双轨运行
```python
USE_NEW_DISPATCH = False  # 增量迁移期间

def visit(self, node) -> Optional[str]:
    if USE_NEW_DISPATCH:
        return self.extract(node).primary
    # 旧路径，保留向后兼容
```
- 新旧两条路径可切换
- 可随时回滚

### Step 5: 切换默认，移除旧代码
```python
USE_NEW_DISPATCH = True
```
- 移除 visit()/get_all_signals() 旧方法
- 移除 alias_map
- 移除 generic_visit() fallback

### Step 6: 重构为组合 (可选)
- SignalExtractor / ContextExtractor 分离
- 更彻底的单一职责

---

## 5. 实施建议

**当前状态**: 系统工作正常，834 测试通过
**建议**: 等有明确需求时再做重构:
- 需要支持更多 SV 类型
- 发现当前架构扩展困难
- 有额外开发时间

**重构风险**: 中等 (需 60+ handlers 迁移)
**收益**: 长期可维护性提升

---

## 6. 相关文件

- `src/trace/core/visitors/signal_expression_visitor.py` - 当前实现
- `src/trace/core/visitors/statement_collector_visitor.py` - 语句收集
- `src/trace/core/graph_builder.py` - 调用 visitor 的主要消费者

---

## 7. 铁律29 回顾

| 版本 | 描述 |
|------|------|
| v1 | 全部用 Legacy |
| v2 | 添加 [FALLBACK] 日志 |
| v3 | Visitor 作为 primary，Legacy 作为 fallback |
| v4 | 验证 Visitor 完全覆盖，移除 fallback |
| v5 | 废弃 Legacy 方法，抛出 NotImplementedError |

**新目标 (v6)**: 单dispatch架构，移除双接口