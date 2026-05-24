# 底层抽象：Signal + Connection

**日期**: 2026-05-24

---

## 一、sv_query 的核心抽象

sv_query 项目从一开始就抽象为两个核心概念：

### 1.1 Signal（信号）

**定义**：代码中的变量、wire、reg、端口等

**相关类**：
```python
@dataclass(frozen=True)
class SignalNode:
    path: str          # 完整路径 "top.clk"
    width: int = 1     # 位宽
    is_port: bool = False
    is_reg: bool = False

@dataclass
class SignalResult:
    """信号提取结果（单个表达式）"""
    primary: Optional[str]       # 主信号名
    all_signals: List[str]       # 所有信号列表
    kind_name: Optional[str]     # 表达式类型
    op_name: Optional[str]      # 操作符名
```

**职责**：
- 识别信号名
- 提取信号属性（宽度、类型）
- 追踪信号来源

### 1.2 Connection（连接）

**定义**：信号之间的关系（驱动、负载、时钟等）

**相关类**：
```python
@dataclass
class ConnectionEdge:
    source: str                    # 驱动端
    sink: str                      # 负载端
    edge_type: str = "driver"      # 连接类型
    timing: Optional[str] = None   # '@posedge clk'
    assign_type: str = ""          # 'blocking', 'nonblocking'
    condition: Optional[str] = None # 条件表达式
```

**职责**：
- 表示信号间的数据流
- 追踪时序（时钟域）
- 追踪条件（if-else）

### 1.3 SignalGraph（信号图）

**定义**：Signal + Connection 构建的有向图

```python
class SignalGraph(nx.DiGraph):
    """信号关系图"""
    
    # 节点：SignalNode
    # 边：ConnectionEdge
```

---

## 二、Signal 和 Connection 的关系

```
┌─────────────────────────────────────────────────────────────┐
│                        SignalGraph                           │
│                                                              │
│   ┌─────────┐          ┌─────────┐          ┌─────────┐     │
│   │ Signal A │ ───────▶│ Signal B │ ───────▶│ Signal C │     │
│   └─────────┘          └─────────┘          └─────────┘     │
│        │                    │                    │          │
│        │      ConnectionEdge │     ConnectionEdge│          │
│        └────────────────────┴────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

| 抽象 | 说明 | 例子 |
|------|------|------|
| Signal | 节点 | `wire clk; input d; reg q;` |
| Connection | 边 | `q <= d;` (d → q) |

---

## 三、Signal 提取 vs Connection 追踪

### 3.1 Signal 提取（已完成）

**任务**：从表达式中提取信号名

**方法**：
```python
visitor.extract(node) -> SignalResult
```

**例子**：
```systemverilog
assign out = a & b | c;
```

**结果**：
```python
SignalResult(
    primary='out',
    all_signals=['a', 'b', 'c', 'out'],
    kind_name='AssignmentExpression'
)
```

### 3.2 Connection 追踪（待完成）

**任务**：追踪信号之间的数据流关系

**方法**：
```python
graph_builder.build(node) -> SignalGraph
```

**例子**：
```systemverilog
always @(posedge clk) q <= d;
```

**结果**：
```python
ConnectionEdge(
    source='d',
    sink='q',
    edge_type='driver',
    timing='@posedge clk',
    assign_type='nonblocking'
)
```

---

## 四、底层抽象设计

### 4.1 当前架构问题

```
SignalExpressionVisitor (7000+ 行)
├── extract() - 主入口
├── @on handlers (536)
│   ├── handler 混入了遍历逻辑
│   └── 子节点处理方式不统一
└── visit_ methods (45 - 死代码)
```

### 4.2 核心问题

**遍历逻辑和业务逻辑混在一起**：
- Handler 既要处理节点逻辑
- 又要控制子节点遍历

### 4.3 新架构：分离关注点

```
┌─────────────────────────────────────────────────────────────┐
│                     Task (业务逻辑)                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              TraversalStrategy                           ││
│  │  - DFS: 追踪数据流 (d → q)                               ││
│  │  - BFS: 收集所有信号                                      ││
│  │  - Selective: 只追踪特定类型                             ││
│  └─────────────────────────────────────────────────────────┘│
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │               NodeAccessor                              ││
│  │  - get_children(node)                                   ││
│  │  - get_attr(node, name)                                  ││
│  └─────────────────────────────────────────────────────────┘│
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                 SignalExtractor                         ││
│  │  - @on handler 只处理 Signal 提取                       ││
│  │  - 返回 SignalResult                                     ││
│  └─────────────────────────────────────────────────────────┘│
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                ConnectionTracker                        ││
│  │  - @on handler 只处理 Connection 追踪                   ││
│  │  - 返回 ConnectionEdge                                   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 4.4 Handler 分离

```python
class SignalExtractor:
    """Signal 提取 - 只关心信号名"""
    
    @on('IdentifierName')
    def handle_identifier(self, node) -> SignalResult:
        name = self._get_name(node)
        return SignalResult(primary=name)


class ConnectionTracker:
    """Connection 追踪 - 只关心数据流"""
    
    @on('AssignmentExpression')
    def handle_assignment(self, node) -> ConnectionEdge:
        lhs = self._get_lhs(node)
        rhs = self._get_rhs(node)
        return ConnectionEdge(source=rhs, sink=lhs)
```

### 4.5 遍历策略分离

```python
class SignalGraphBuilder:
    def __init__(self):
        self.signal_extractor = SignalExtractor()
        self.connection_tracker = ConnectionTracker()
        self.strategy = DFSTraversal()
    
    def build(self, node) -> SignalGraph:
        graph = SignalGraph()
        
        def callback(n):
            # 提取 Signal
            sig_result = self.signal_extractor.extract(n)
            # 追踪 Connection
            conn = self.connection_tracker.track(n)
            if conn:
                graph.add_edge(conn.source, conn.sink, **conn.__dict__)
        
        self.strategy.traverse(node, callback)
        return graph
```

---

## 五、Signal 和 Connection 的遍历策略

### 5.1 Signal 提取

**策略**：Selective DFS

**原因**：
- 只追踪表达式节点
- 跳过声明、注释等
- 沿着表达式树深入

```python
# 只提取表达式相关的节点
EXPRESSION_KINDS = {
    'IdentifierName', 'ElementSelectExpression', 'MemberAccessExpression',
    'BinaryExpression', 'UnaryExpression', 'AssignmentExpression', ...
}
```

### 5.2 Connection 追踪

**策略**：Context-aware DFS

**原因**：
- 需要追踪赋值语句（always, assign）
- 需要区分时钟域
- 需要追踪条件分支

```python
# 需要追踪的节点类型
ASSIGNMENT_KINDS = {
    'NonblockingAssignmentExpression',
    'BlockingAssignmentExpression', 
    'ContinuousAssignStatement',
}
```

### 5.3 Port 收集

**策略**：BFS

**原因**：
- 按层级收集模块端口
- 不需要深入表达式

```python
PORT_KINDS = {'AnsiPort', 'PortDeclaration', 'ImplicitAnsiPort'}
```

---

## 六、结论

### 6.1 现有抽象的价值

sv_query 的 Signal + Connection 抽象是**正确的**：
- Signal 抽象了节点
- Connection 抽象了边
- SignalGraph 构建了关系

### 6.2 需要改进的地方

**遍历逻辑和业务逻辑混在一起**：
- Handler 既处理节点又控制遍历
- 导致代码复杂、难以维护

### 6.3 改进方向

1. **分离 TraversalStrategy**
   - DFS/BFS/Selective 可切换
   - 不影响 Handler 逻辑

2. **分离 NodeAccessor**
   - 封装 pyslang API
   - Handler 不直接访问节点属性

3. **保持 Signal + Connection 抽象**
   - Handler 只返回 SignalResult 或 ConnectionEdge
   - 遍历由框架控制

### 6.4 新架构示例

```python
class SignalExpressionVisitor:
    def __init__(self, adapter, strategy=SelectiveDFS()):
        self.adapter = adapter
        self.strategy = strategy
        self._handlers = {}
        self._collect_handlers()
    
    def extract(self, node) -> SignalResult:
        """使用策略遍历，handler 只处理节点"""
        if node is None:
            return SignalResult.empty()
        
        self._current_result = SignalResult()
        self.strategy.traverse(
            node,
            accessor=PyslangAccessor(),
            callback=self._visit_callback,
            filter=EXPRESSION_KINDS
        )
        return self._current_result
    
    def _visit_callback(self, node):
        """只处理节点，不涉及遍历"""
        kind = node.kind.name
        if kind in self._handlers:
            result = self._handlers[kind](node)
            if result:
                self._current_result.merge(result)
```

**核心变化**：
- Handler **不控制遍历**
- Handler **只返回结果**
- 遍历由 **Strategy** 控制