# 架构设计：边界控制与 Selective 遍历

**日期**: 2026-05-24
**核心需求**: 精确控制 AST 遍历边界

---

## 一、需求场景

### 场景：从指定模块实例提取信号连接图

```
module top;
  uart u_uart (.clk(clk), .rst(rst));  // 需要提取端口连接
  buffer u_buf (.d(d), .q(q));          // 不需要深入
endmodule
```

**目标**：
- 提取 `u_uart` 的端口连接（clk, rst）
- **不深入** `u_uart` 内部（那是另一个 module scope）

**边界条件**：

| 节点类型 | 处理方式 |
|---------|----------|
| `ModuleInstantiation` (目标) | **处理 + 不深入子节点** |
| `PortConnection` | 提取端口信号 |
| 子模块内部节点 | **完全不进入** |

---

## 二、核心设计：Handler 返回 VisitAction

### 2.1 关键洞察

**Handler 返回 VisitAction 来控制遍历边界**

```python
@on('ModuleInstantiation')
def handle_module_instantiation(self, node) -> VisitAction:
    # 1. 处理当前节点（提取端口连接）
    self._process_connections(node)
    
    # 2. 返回 Skip：不深入子节点（子模块内部）
    return VisitAction.Skip
```

### 2.2 边界控制模式

```python
class SignalGraphBuilder:
    
    def __init__(self, target_instance):
        self.target = target_instance
        self.graph = SignalGraph()
    
    def _callback(self, node) -> VisitAction:
        kind = node.kind.name
        
        # ====== 边界控制 ======
        
        if kind == 'ModuleInstantiation':
            if self._is_target_instance(node):
                # 处理，但不深入
                self._process_instantiation(node)
                return VisitAction.Skip  # ← 关键：不深入
            else:
                # 非目标实例：完全不处理也不深入
                return VisitAction.Skip
        
        # ====== 正常处理 ======
        
        if kind in self._handlers:
            self._handlers[kind](node)
        
        return VisitAction.Advance
    
    def extract(self, root):
        root.visit(self._callback)
        return self.graph
```

---

## 三、边界类型

### 类型 1：处理但不深入（最常见）

```python
@on('ModuleInstantiation')
def handle(self, node) -> VisitAction:
    self._process(node)      # 提取端口信息
    return VisitAction.Skip  # 不深入子节点
```

### 类型 2：处理且深入

```python
@on('AssignmentExpression')
def handle(self, node) -> VisitAction:
    self._process_assignment(node)  # 处理赋值
    return VisitAction.Advance      # 继续深入子节点
```

### 类型 3：不处理也不深入

```python
@on('EmptyStatement')
def handle(self, node) -> VisitAction:
    return VisitAction.Skip  # 跳过

@on('SyntaxList')
def handle(self, node) -> VisitAction:
    return VisitAction.Skip  # 列表不需要处理
```

### 类型 4：中断遍历

```python
@on('TargetModuleFound')
def handle(self, node) -> VisitAction:
    self.found_module = node
    return VisitAction.Interrupt  # 找到目标，停止遍历
```

---

## 四、边界控制与 TraversalStrategy 的关系

### 4.1 TraversalStrategy 定义遍历顺序

| Strategy | 说明 |
|----------|------|
| DFS | 深度优先（默认） |
| BFS | 广度优先 |
| Selective | 选择性遍历 |

### 4.2 Handler 返回值定义遍历边界

| 返回值 | 说明 |
|--------|------|
| `Advance` | 继续遍历（进入子节点） |
| `Skip` | 跳过子节点，继续兄弟节点 |
| `Interrupt` | 停止整个遍历 |

### 4.3 组合使用

```
TraversalStrategy (DFS/BFS)
       │
       ▼
pyslang.visit(callback)
       │
       ▼
callback(node) {
    // 1. Handler 处理节点
    handler(node)
    
    // 2. Handler 返回边界控制
    return VisitAction.Advance/Skip/Interrupt
}
```

---

## 五、完整示例

### 5.1 提取指定模块实例的连接图

```python
class SignalGraphExtractor:
    
    def __init__(self, target_instance: str):
        self.target = target_instance
        self.graph = SignalGraph()
        self._handlers = {}
        self._collect_handlers()
    
    def extract(self, root) -> SignalGraph:
        root.visit(self._callback)
        return self.graph
    
    def _callback(self, node) -> VisitAction:
        kind = node.kind.name
        
        # ====== 边界控制 ======
        
        # ModuleInstantiation：处理端口，但不深入内部
        if kind == 'ModuleInstantiation':
            name = self._get_instance_name(node)
            if name == self.target:
                self._process_instantiation(node)
                return VisitAction.Skip  # 不深入
        
        # PortConnection：提取端口信号
        if kind == 'NamedPortConnection':
            self._process_port_connection(node)
            return VisitAction.Skip  # 已处理，跳过子节点
        
        if kind == 'OrderedPortConnection':
            self._process_port_connection(node)
            return VisitAction.Skip
        
        # ====== 正常处理 ======
        
        if kind in self._handlers:
            return self._handlers[kind](node)
        
        return VisitAction.Advance
    
    # ====== Handlers ======
    
    def _is_target_instance(self, node) -> bool:
        name = self._get_instance_name(node)
        return name == self.target
    
    def _get_instance_name(self, node) -> str:
        inst = getattr(node, 'instance', None)
        if inst and hasattr(inst, 'name'):
            return str(inst.name)
        return ''
    
    def _process_instantiation(self, node):
        """处理模块实例：提取端口连接"""
        instance_name = self._get_instance_name(node)
        connections = getattr(node, 'connections', None)
        
        if connections:
            for conn in connections:
                self._process_connection(instance_name, conn)
    
    def _process_connection(self, instance_name, conn):
        """处理单个端口连接"""
        port_name = self._get_port_name(conn)
        signal_name = self._get_signal_name(conn)
        
        self.graph.add_edge(
            signal_name,
            f'{instance_name}.{port_name}',
            edge_type='connection'
        )
    
    # @on handlers...
```

### 5.2 使用方式

```python
# 提取 u_uart 实例的连接
extractor = SignalGraphExtractor('u_uart')
graph = extractor.extract(root)

# 结果：
# clk → u_uart.clk
# rst → u_uart.rst
# d → u_buf.d (如果 u_uart 内部有连接)
```

---

## 六、与 pyslang.visit() 的关系

### 6.1 pyslang.visit() 的局限性

```python
# pyslang.visit() 是单向遍历，无法双向
root.visit(callback)  # 只能从根到叶子
```

### 6.2 边界控制的精确性

| 功能 | pyslang.visit() | 边界控制 |
|------|-----------------|----------|
| 控制深度 | ✗ | ✓ (Skip) |
| 选择路径 | ✗ | ✓ (Skip 非目标) |
| 双向遍历 | ✗ | ✗ (仍单向) |
| 外部控制 | ✗ | ✓ (Handler 逻辑) |

### 6.3 最佳实践

**不是所有遍历都用 pyslang.visit()**：

```python
class ContextAwareExtractor:
    """根据上下文选择遍历方式"""
    
    def extract(self, node, context):
        if context.type == 'module_scope':
            # 模块内：使用 pyslang.visit() + 边界控制
            node.visit(self._callback)
        elif context.type == 'signal_trace':
            # 信号追踪：显式栈控制
            self._stack_traverse(node)
        elif context.type == 'port_collect':
            # 端口收集：BFS
            self._bfs_collect(node)
```

---

## 七、总结

### 7.1 核心设计

```
pyslang.visit(callback)
       │
       ▼
callback(node) {
    kind = node.kind.name
    
    if is_boundary(kind):
        process(node)      // 处理边界节点
        return Skip         // 不深入
    
    if has_handler(kind):
        handler(node)       // 正常处理
    
    return Advance          // 继续遍历
}
```

### 7.2 Handler 返回值语义

| 返回值 | 含义 |
|--------|------|
| `Advance` | 继续遍历子节点 |
| `Skip` | 跳过子节点，继续兄弟节点 |
| `Interrupt` | 停止整个遍历 |

### 7.3 边界类型

1. **处理但不深入** - `ModuleInstantiation`（处理端口，不入内部）
2. **处理且深入** - `AssignmentExpression`（提取信号，继续追踪）
3. **不处理也不深入** - `EmptyStatement`, `SyntaxList`
4. **中断遍历** - 找到目标后停止

### 7.4 优势

- **精确边界控制** - Handler 自己决定是否深入
- **灵活组合** - 可以组合 DFS/BFS + 边界控制
- **与 pyslang.visit() 集成** - 利用原生遍历能力