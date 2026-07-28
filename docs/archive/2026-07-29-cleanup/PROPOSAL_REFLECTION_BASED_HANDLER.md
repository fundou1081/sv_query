# 新架构提案：基于反射的 @on Handler Visitor 模式

**日期**: 2026-05-24
**状态**: 提案中
**提出者**: 方浩博

---

## 背景

当前 `signal_expression_visitor.py` 存在两套并存的架构：

| 架构 | 数量 | 状态 |
|------|------|------|
| `visit_` 方法 | 45 | 旧架构，死代码 |
| `@on` handlers | 536 | 新架构，部分实现 |

问题：
- visitor 模式太杂，逻辑和遍历混在一起
- @on handler 需要手动处理子节点
- 两套系统做类似的事，冗余

---

## 提案：反射自动发现子节点

### 核心思路

**handler 只处理当前节点的逻辑，框架自动处理子节点遍历**

```
┌─────────────────────────────────────────────────────┐
│  extract(node)                                       │
│    │                                                 │
│    ├── 1. 找到 @on handler (根据 node.kind)         │
│    │                                                 │
│    ├── 2. 调用 handler(node)                         │
│    │     handler 只处理当前节点的逻辑                │
│    │                                                 │
│    └── 3. 框架自动反射发现子节点                     │
│          递归调用 extract(child) for each child     │
│          合并所有结果                                 │
└─────────────────────────────────────────────────────┘
```

### 对比

**之前** (handler 自己处理子节点):
```python
@on('AssignmentExpression')
def extract_assignment_expression(self, node) -> SignalResult:
    left = getattr(node, 'left', None)
    right = getattr(node, 'right', None)
    left_result = self.extract(left) if left else SignalResult()
    right_result = self.extract(right) if right else SignalResult()
    return left_result.merge(right_result)
```

**之后** (handler 只管自己，框架处理子节点):
```python
@on('AssignmentExpression')
def extract_assignment_expression(self, node) -> SignalResult:
    """只返回左操作数作为主信号"""
    left = getattr(node, 'left', None)
    if left:
        return SignalResult(primary=self._get_signal_name(left))
    return SignalResult()
    # 子节点遍历交给框架自动处理
```

---

## 需要实现

### 1. `_extract_children(node)` - 反射发现子节点

```python
def _extract_children(self, node) -> SignalResult:
    """自动发现并递归处理所有子节点"""
    result = SignalResult()
    
    for attr_name in dir(node):
        if attr_name.startswith('_'):
            continue
        
        try:
            attr = getattr(node, attr_name, None)
            if attr is None:
                continue
                
            # 跳过非 AST 节点
            if not hasattr(attr, 'kind'):
                continue
                
            # 跳过简单值
            if isinstance(attr, (str, int, float, bool)):
                continue
            
            # 递归处理子节点
            child_result = self.extract(attr)
            result.merge(child_result)
            
        except Exception:
            continue
    
    return result
```

### 2. `_get_signal_name(node)` - 从节点提取信号名

```python
def _get_signal_name(self, node) -> Optional[str]:
    """从节点提取信号名（纯逻辑，不递归）"""
    # 实现节点特定的信号提取逻辑
    pass
```

### 3. 简化所有 536 个 handlers

移除所有 handler 中的手动子节点处理代码：
- 删除 `self.extract(left)`, `self.extract(right)` 等
- 只保留当前节点的信号提取逻辑
- 框架自动处理子节点遍历

---

## 优点

1. **Handler 职责单一** - 只处理当前节点，不关心子节点
2. **代码量减少** - 536 个 handler 简化
3. **一致性** - 统一由框架处理遍历
4. **可维护性** - 新增 SyntaxKind 只需添加简单 handler
5. **符合 visitor 模式** - 逻辑和遍历分离

## 风险

1. **反射开销** - 需要扫描所有属性
2. **属性过滤** - 需要正确识别 AST 节点 vs 普通属性
3. **循环引用** - 需要处理可能的环形 AST
4. **性能测试** - 需要验证性能不下降

---

## 实现步骤

1. [ ] 实现 `_extract_children()` 方法
2. [ ] 实现 `_get_signal_name()` 辅助方法
3. [ ] 修改 `extract()` 集成自动子节点遍历
4. [ ] 选择几个 handler 进行简化试点
5. [ ] 运行测试验证功能不变
6. [ ] 批量简化其他 handlers
7. [ ] 删除废弃的 `visit_` 方法
8. [ ] 性能测试和优化

---

## 备选方案

### 方案 B：显式声明子节点

```python
@on('AssignmentExpression', children=['left', 'right'])
def extract_assignment_expression(self, node) -> SignalResult:
    return SignalResult(primary=...)
```

**缺点**：需要额外注解，增加了维护负担

### 方案 C：混合模式

- 简单节点：handler 返回信号，框架自动处理子节点
- 复杂节点：handler 手动控制子节点处理

**缺点**：两种模式，增加复杂度

---

## 结论

**推荐方案 A**：基于反射的自动子节点发现

- 最符合 visitor 模式原意
- Handler 职责最单一
- 长期维护成本最低
---

## 附录：pyslang 原生 visitor API

### pyslang.SyntaxNode.visit()

pyslang 内置的 AST 遍历方法：

```python
node.visit(callback) -> None
```

**参数**：
- `callback(node)`: 回调函数，接收当前节点

**返回值（VisitAction）**：
| Action | 行为 |
|--------|------|
| `Advance` | 继续遍历（默认） |
| `Skip` | 跳过当前节点的子节点 |
| `Interrupt` | 中断遍历 |

### 示例

```python
import pyslang

tree = pyslang.SyntaxTree.fromText(sv_code)
root = tree.root

# 基本遍历
def visitor(node):
    print(f'{node.kind.name}')
    return pyslang.VisitAction.Advance

root.visit(visitor)

# 选择性遍历 - 只处理特定类型
def visitor(node):
    if 'Expression' in node.kind.name:
        # 处理表达式
        return pyslang.VisitAction.Advance
    return pyslang.VisitAction.Skip  # 跳过无关节点

# 中断遍历
def visitor(node):
    if node.kind.name == 'TargetModule':
        return pyslang.VisitAction.Interrupt  # 找到目标后停止
    return pyslang.VisitAction.Advance
```

### 与 @on handler 的关系

| pyslang.visit() | @on handler |
|-----------------|-------------|
| 回调函数 | handler 方法 |
| 手动 switch case | 自动分派 |
| 返回 VisitAction | 不需要返回值 |

### 新方案：基于 pyslang.visit() 的 handler

```python
class SignalVisitor:
    def visit(self, node):
        """主入口 - 对应 pyslang.visit()"""
        kind_name = node.kind.name
        handler = self._get_handler(kind_name)
        if handler:
            handler(node)
        return pyslang.VisitAction.Advance
    
    def _get_handler(self, kind_name):
        """获取对应的 handler"""
        method_name = f'handle_{kind_name}'
        return getattr(self, method_name, None)
    
    @handle('IdentifierName')
    def handle_identifier_name(self, node):
        """只处理当前节点，框架自动遍历"""
        # 处理逻辑
        pass
```

### 优势

1. **利用 pyslang 原生 API** - 不需要自己实现遍历
2. **VisitAction 控制** - 可以 Skip/Interrupt
3. **一致性** - 与 pyslang 设计一致
