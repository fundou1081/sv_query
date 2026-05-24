# sv_query 现有架构 vs DataFlow 提案 - 对照分析

> 创建时间: 2026-05-24
> 项目路径: /Users/fundou/my_dv_proj/sv_query

---

## 一、现有架构总览

### 1.1 核心流程 (自底向上)

```
RTL 源码
    ↓
SVCompiler (pyslang 编译)
    ↓
SemanticAdapter (语义分析)
    ↓
GraphBuilder (构建 SignalGraph)
    ↓
SignalGraph (networkx 图)
    ↓
Query Layer (SignalTracer, LoadTracer, etc.)
    ↓
UnifiedTracer (统一入口)
```

### 1.2 各层职责

| Layer | 组件 | 职责 |
|-------|------|------|
| 0 | SVCompiler | 编译 SV → Compilation AST |
| 1 | SemanticAdapter | 语义分析，提供 get_modules() 等 |
| 2 | GraphBuilder | 模块 → SignalGraph |
| 2 | DriverExtractor | 驱动提取 |
| 2 | SignalExpressionVisitor | 信号提取 (双接口) |
| 2 | StatementCollectorVisitor | 语句收集 |
| 3 | SignalGraph | 信号图 (nodes + edges) |
| 4 | SignalTracer/LoadTracer | 信号/负载追踪 |
| 5 | UnifiedTracer | 统一入口 |

### 1.3 现有 Visitor 架构

```
SignalExpressionVisitor (双接口):
    visit(node) → Optional[str]       # 单信号
    get_all_signals(node) → List[str] # 多信号
    extract(node) → SignalResult      # 新增统一入口
    
StatementCollectorVisitor (单接口):
    visit(node) → None (收集到 statements)
    收集结果: self.statements: List[StatementContext]

DriverExtractor:
    组合使用上述两个 Visitor
    负责构建 edges
```

### 1.4 SignalGraph 结构

```python
class SignalGraph(nx.DiGraph):
    """继承自 networkx DiGraph"""
    _node_data: Dict[str, TraceNode]   # {signal_id: TraceNode}
    _edge_data: Dict[Tuple, TraceEdge] # {(src, tgt): TraceEdge}
    _port_to_internal: Dict[str, str]
```

**关键**: SignalGraph 已经继承自 `nx.DiGraph`，可直接使用 networkx 算法！

---

## 二、DataFlow 提案架构

### 2.1 三层架构

```
Layer 1: SignalResult (节点层)
    - 单表达式信号提取
    - primary + all_signals + metadata
    - 来自 SignalExpressionVisitor.extract()

Layer 2: DataFlowSegment (段层)
    - 单步驱动: from_signal → to_signal
    - driver + condition + timing
    - 来自 StatementCollectorVisitor 上下文

Layer 3: DataFlowPath / DataFlowResult (路径层)
    - 完整路径分析
    - 算法: nx.all_simple_paths()
```

### 2.2 DataFlowAnalyzer API

```python
class DataFlowAnalyzer:
    def analyze(self, from_signal: str, to_signal: str) -> DataFlowResult:
        # 1. Path finding (networkx)
        paths = self._find_all_paths(from_signal, to_signal)
        
        # 2. Build segments with context
        for path in paths:
            segments = self._build_segments(path)
            
        # 3. Return DataFlowResult
        return DataFlowResult(from, to, paths, ...)
```

---

## 三、关键差异对比

| 维度 | 现有架构 | DataFlow 提案 |
|------|----------|---------------|
| 图类型 | SignalGraph (nx.DiGraph) | SignalGraph (不变) |
| 边描述 | (source, target) tuple | DataFlowSegment (丰富) |
| 路径查询 | 无 (只有单跳 drivers) | nx.all_simple_paths() |
| 条件信息 | 分散在各处 | ConditionInfo 统一封装 |
| 时序信息 | _extract_clock 等方法 | DataFlowSegment.timing |
| 结果封装 | 无统一结构 | DataFlowResult 统一封装 |
| 多路径 | 不支持 | 支持 (all_simple_paths) |

---

## 四、融合方案设计

### 4.1 SignalGraph 保持不变

```
现有: edges 只存 (source, target) tuple
提案: edges 结构不变，保持向后兼容
      新增 DataFlowSegment 作为边的"属性视图"
```

### 4.2 复用现有组件

| 组件 | 状态 | 角色 |
|------|------|------|
| SignalGraph | 已有 | 图结构不变 |
| DriverExtractor | 已有 | 查找 from→to 驱动源 |
| SignalExpressionVisitor.extract() | 已有 | 生成 SignalResult |
| StatementCollectorVisitor | 已有 | 生成 ConditionInfo |
| DataFlowAnalyzer | **新增** | 主分析器 |
| DataFlowSegment | **新增** | 段数据结构 |
| DataFlowResult | **新增** | 结果封装 |

### 4.3 增量实现路径

```
Step 1: DataFlowSegment 数据类
        - from_signal, to_signal
        - driver: SignalResult
        - condition: ConditionInfo
        - timing: str

Step 2: DataFlowPath / DataFlowResult 数据类

Step 3: DataFlowAnalyzer.analyze()
        - 利用 SignalGraph 已继承 nx.DiGraph
        - 直接调用 simple_paths 算法

Step 4: 上下文丰富
        - _build_segments() 填充 condition/timing
```

### 4.4 关键优势: SignalGraph 已继承 nx.DiGraph

```python
class SignalGraph(nx.DiGraph):
    """继承自 networkx，直接使用 nx 算法"""
    pass

# 直接使用 networkx 算法！
G = graph  # SignalGraph instance
paths = list(nx.all_simple_paths(G, from_signal, to_signal, cutoff=20))
shortest = nx.shortest_path(G, from_signal, to_signal)
```

---

## 五、与现有架构的接口

### 5.1 SignalGraph (现有)

```python
class SignalGraph(nx.DiGraph):
    # 已有方法
    .nodes          # NodeView (dict-like)
    .edges          # EdgeView (list of tuples)
    .get_node(id)   # 获取 TraceNode
    .get_edge(src, tgt) # 获取 TraceEdge
    
    # 新增 (因为已继承 nx.DiGraph)
    .to_networkx()  # 已有，直接返回 self
    .successors(id) # 获取后继节点
    .predecessors(id) # 获取前驱节点
```

### 5.2 DriverExtractor (现有)

```python
class DriverExtractor:
    .get_drivers(signal) → List[str]  # 单跳驱动源
    ._get_signal(node) → str          # 调用 sev.visit()
    ._get_all_signals(node) → List[str] # 调用 sev.get_all_signals()
```

### 5.3 SignalExpressionVisitor (现有)

```python
class SignalExpressionVisitor:
    .extract(node) → SignalResult  # 统一入口 (POC 已完成)
```

### 5.4 DataFlowAnalyzer (新增)

```python
class DataFlowAnalyzer:
    def __init__(self, graph: SignalGraph, adapter: PyslangAdapter):
        self.graph = graph
        self.adapter = adapter
        self._signal_visitor = SignalExpressionVisitor(adapter)
        self._stmt_visitor = StatementCollectorVisitor(adapter)
    
    def analyze(self, from_signal: str, to_signal: str) → DataFlowResult
    def _find_all_paths(self, from_signal, to_signal) → List[List[str]]
    def _build_segments(self, path: List[str]) → List[DataFlowSegment]
    def _get_segment(self, from_signal, to_signal) → DataFlowSegment
```

---

## 六、实现优先级建议

### P1: 核心框架 (1-2天)

1. DataFlowSegment 数据类
2. DataFlowPath / DataFlowResult 数据类
3. DataFlowAnalyzer._find_all_paths()

**产出**: 可以查询 from→to 的所有路径

### P2: 上下文丰富 (2-3天)

1. ConditionInfo 数据类
2. DataFlowSegment.condition 填充
3. DataFlowSegment.timing 填充

**产出**: 每段路径包含条件/时序信息

### P3: 高级功能 (长期)

1. 多路径分析 (all paths vs shortest)
2. 条件覆盖分析
3. 时序路径排序

---

## 七、架构补充说明

### 7.1 为什么 SignalGraph 继承 nx.DiGraph

这是一个**明智的设计决策**：
- 直接复用 networkx 算法 (simple_paths, cycles, etc.)
- 无需转换，直接 `graph.successors(node)`
- 新增 DataFlow 功能无需修改图结构

### 7.2 DataFlowSegment 的定位

DataFlowSegment **不是**替代 edges，而是作为边的**属性视图**：

```
edges: List[Tuple[str, str]] = [
    ('a', 'b'),
    ('b', 'c'),
    ('c', 'd'),
]

# DataFlowSegment 是 edges 的"丰富版本"
segments = analyzer.get_segments_for_path(['a', 'b', 'c', 'd'])
# 返回: [Segment(a→b, cond=None, timing=@posedge clk),
#        Segment(b→c, cond=if(sel), timing=@posedge clk),
#        ...]
```

### 7.3 与 SignalTracer 的关系

```
SignalTracer (现有)          DataFlowAnalyzer (新增)
└── trace(signal)            └── analyze(from, to)
    ├── drivers (单跳)           ├── paths (多跳)
    ├── loads (单跳)             ├── segments (每跳详情)
    └── confidence               ├── conditions (路径条件)
                                 └── timings (路径时序)
```

SignalTracer 是 **单信号查询**，DataFlowAnalyzer 是 **信号对查询**。