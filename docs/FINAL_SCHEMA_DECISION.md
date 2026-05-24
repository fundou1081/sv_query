# 架构重新评估: DataFlow 与现有 Schema 的关系

> 创建时间: 2026-05-24
> 状态: 分析完成
> 更新: SCHEMA_COMPARISON_V2.md

---

## 一、项目现有两层 Schema 架构

### Layer 1: graph/models.py (存储层)

```python
class TraceNode:
    id: str                           # 完整路径
    name: str
    module: str
    kind: NodeKind                    # SIGNAL, WIRE, REG, PORT_IN, ...
    width: Tuple[int, int]
    bit_range: Optional[str]
    is_clock: bool
    is_reset: bool
    is_enable: bool
    is_port: bool

class TraceEdge:
    src: str                          # 源信号
    dst: str                          # 目标信号
    kind: EdgeKind                    # DRIVER, CLOCK, RESET, CONNECTION, ...
    condition: str = ""               # 条件表达式
    clock_domain: str = ""            # 时钟域
    assign_type: str = ""             # blocking/nonblocking/assign
    confidence: str = "high"

class SignalGraph(nx.DiGraph):
    """继承自 networkx DiGraph，直接使用 nx 算法"""
    _node_data: Dict[str, TraceNode]
    _edge_data: Dict[Tuple[str, str], TraceEdge]
```

### Layer 2: data_models.py (结果层)

```python
class SignalNode:                     # 简化版 TraceNode
    path: str
    width: int = 1
    is_port: bool = False
    is_reg: bool = False

class ConnectionEdge:                 # 类似 TraceEdge
    source: str
    sink: str
    edge_type: str = "driver"
    condition: Optional[str] = None
    timing: Optional[str] = None      # 新增
    assign_type: str = ""            # 新增
    condition_signals: List[str]     # 新增
    is_conditional: bool = False     # 新增

class SignalChain:
    root: SignalNode
    drivers: List[ConnectionEdge]
    loads: List[ConnectionEdge]
    paths: List[List[str]]           # 新增
    intermediate_signals: Set[str]   # 新增
    timing_analysis: Optional[TimingAnalysisResult]  # 新增
    conditions: List[ConditionInfo]  # 新增
    data_flow_when: str = "always"   # 新增
```

---

## 二、关键发现: 两层 Schema 的问题

### 问题 1: 重复设计

TraceEdge 和 ConnectionEdge 有大量重复字段:

| 字段 | TraceEdge | ConnectionEdge | 重复 |
|------|-----------|-----------------|------|
| 源 | src | source | ✅ |
| 目标 | dst | sink | ✅ |
| 条件 | condition | condition | ✅ |
| 时序 | clock_domain | timing | 类似 |
| 赋值类型 | assign_type | assign_type | ✅ |

### 问题 2: SignalChain 与 SignalGraph 没有直接映射

SignalGraph 存储:
```python
edges: [('a', 'b'), ('b', 'c'), ('c', 'd')]
_edge_data: {
    ('a', 'b'): TraceEdge(...),
    ('b', 'c'): TraceEdge(condition='en', ...),
    ('c', 'd'): TraceEdge(...),
}
```

SignalChain 存储:
```python
data_path: ['a', 'b', 'c', 'd']
# 问题: data_path 没有与 TraceEdge 关联
# 问题: 丢失每段的 condition/timing 信息
```

---

## 三、重新发现: DataFlow 可以基于 SignalGraph 构建

### SignalGraph 已提供 DataFlow 需要的核心信息

```python
# SignalGraph.edges (或 _edge_data) 包含路径信息
graph.edges: [('a', 'b'), ('b', 'c'), ('c', 'd')]

# TraceEdge 包含每段的上下文
_edge_data[('b', 'c')]:
    TraceEdge(
        src='b', dst='c',
        condition='en',        # ✅ 条件
        clock_domain='clk',    # ✅ 时序
        assign_type='nonblocking'
    )
```

### DataFlow 只需要增强，不需要重构

DataFlow 需要的信息:

| 信息 | 来源 | 状态 |
|------|------|------|
| from/to | SignalGraph.edges | ✅ 已有 |
| condition | TraceEdge.condition | ✅ 已有 |
| timing | TraceEdge.clock_domain | ✅ 已有 |
| driver (SignalResult) | StatementCollectorVisitor | ✅ 已有 extract() |
| condition_signals | SignalExpressionVisitor.extract() | ✅ 已有 |

---

## 四、正确做法: 新增 dataflow_models.py

### 不需要修改任何现有代码

```
现有系统 (不变)
├── graph/models.py (存储层) ← 不变
├── data_models.py (结果层) ← 不变
└── SignalGraph ← 直接使用

新增系统 (独立)
└── dataflow_models.py
    ├── DataFlowSegment
    ├── DataFlowPath
    └── DataFlowResult
```

### DataFlowSegment 设计 (基于 SignalGraph)

```python
@dataclass
class DataFlowSegment:
    """单步驱动关系: from_signal → to_signal"""
    
    from_signal: str                  # ← SignalGraph.edges
    to_signal: str                    # ← SignalGraph.edges
    
    # driver 信息 (从 StatementCollectorVisitor 获取)
    driver: SignalResult              # ← 新增 (ConnectionEdge 没有)
    
    # 条件/时序 (从 TraceEdge 获取)
    condition: Optional[ConditionInfo] = None  # ← TraceEdge.condition 扩展
    timing: Optional[str] = None       # ← TraceEdge.clock_domain
    
    # 赋值类型
    is_blocking: bool = False        # ← TraceEdge.assign_type

@dataclass
class DataFlowResult:
    from_signal: str
    to_signal: str
    paths: List[DataFlowPath]         # 多条路径
    is_reachable: bool
    paths_count: int
    intermediate_signals: Set[str]
    timing_analysis: Optional[TimingAnalysisResult] = None
    control_flow: Optional[ControlFlowResult] = None
```

### DataFlowAnalyzer 实现 (伪代码)

```python
class DataFlowAnalyzer:
    def __init__(self, graph: SignalGraph, adapter: PyslangAdapter):
        self.graph = graph
        self.adapter = adapter
        self._signal_visitor = SignalExpressionVisitor(adapter)
        self._stmt_visitor = StatementCollectorVisitor(adapter)
    
    def analyze(self, from_signal: str, to_signal: str) -> DataFlowResult:
        # 1. 使用 SignalGraph (已继承 nx.DiGraph) 找路径
        paths = list(nx.all_simple_paths(self.graph, from_signal, to_signal))
        
        # 2. 构建 DataFlowPath (包含 DataFlowSegment)
        dataflow_paths = []
        for path in paths:
            segments = self._build_segments(path)
            dataflow_paths.append(DataFlowPath(segments=segments))
        
        # 3. 构建 DataFlowResult
        return DataFlowResult(
            from_signal=from_signal,
            to_signal=to_signal,
            paths=dataflow_paths,
            is_reachable=len(paths) > 0,
            paths_count=len(paths),
            ...
        )
    
    def _build_segments(self, path: List[str]) -> List[DataFlowSegment]:
        segments = []
        for i in range(len(path) - 1):
            from_sig = path[i]
            to_sig = path[i + 1]
            
            # 从 SignalGraph 获取 TraceEdge
            edge = self.graph._edge_data.get((from_sig, to_sig))
            
            # driver 信息 (从 StatementCollectorVisitor 获取)
            driver_result = self._signal_visitor.extract(edge)
            
            # condition/timing (从 TraceEdge 获取)
            condition = None
            timing = None
            if edge:
                if edge.condition:
                    condition = ConditionInfo(expr=edge.condition, ...)
                timing = edge.clock_domain
            
            segments.append(DataFlowSegment(
                from_signal=from_sig,
                to_signal=to_sig,
                driver=driver_result,
                condition=condition,
                timing=timing
            ))
        
        return segments
```

---

## 五、重构代价对比 (更新)

| 方案 | 工时 | 破坏性 | 结论 |
|------|------|--------|------|
| 重构 graph/models.py | 极高 | 极高 | ❌ 不建议 |
| 重构 data_models.py | 高 | 高 | ❌ 不建议 |
| **新增 dataflow_models.py** | **低** | **无** | ✅ **正确做法** |

### 原因

1. **graph/models.py 的 TraceEdge 已经包含关键信息**
   - condition, clock_domain, assign_type
   - 不需要新增存储

2. **SignalGraph 继承 nx.DiGraph**
   - 直接使用 `nx.all_simple_paths()`
   - 不需要新增路径算法

3. **SignalExpressionVisitor.extract() 已有**
   - 可以直接用于 driver 信息

4. **只需要新增类 + DataFlowAnalyzer**
   - DataFlowSegment
   - DataFlowPath
   - DataFlowResult
   - DataFlowAnalyzer

---

## 六、最终架构愿景

```
┌─────────────────────────────────────────────────────────────────┐
│  新增: DataFlow 层                                                │
├─────────────────────────────────────────────────────────────────┤
│  DataFlowResult                                                  │
│      └── paths: List[DataFlowPath]                               │
│              └── segments: List[DataFlowSegment]                │
│                      ├── from/to                                 │
│                      ├── driver: SignalResult                    │
│                      ├── condition: ConditionInfo                 │
│                      └── timing                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  现有: SignalGraph (存储层)                                      │
├─────────────────────────────────────────────────────────────────┤
│  SignalGraph (nx.DiGraph)                                        │
│      ├── edges: [('a', 'b'), ('b', 'c'), ...]                     │
│      ├── _edge_data: {('b','c'): TraceEdge(condition, timing)}   │
│      └── _node_data: {signal_id: TraceNode}                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 七、实施建议

### 步骤 1: 新增 dataflow_models.py

```bash
src/trace/core/
    dataflow_models.py    # 新增
```

### 步骤 2: 实现 DataFlowSegment (基于 TraceEdge)

- from/to ← SignalGraph.edges
- driver ← SignalExpressionVisitor.extract()
- condition ← TraceEdge.condition → ConditionInfo
- timing ← TraceEdge.clock_domain

### 步骤 3: 实现 DataFlowAnalyzer

- 使用 nx.all_simple_paths() 找路径
- 构建 DataFlowSegment
- 返回 DataFlowResult

### 步骤 4: (可选) 控制流分析

- ConditionInfo 填充
- StateTransition 识别

---

## 八、文档索引

| 文档 | 内容 |
|------|------|
| `DATAFLOW_ANALYSIS_ARCHITECTURE.md` | DataFlow 详细设计 |
| `CONTROL_FLOW_ANALYSIS.md` | 控制流分析设计 |
| `ARCHITECTURE_COMPARISON.md` | 架构对照分析 |
| `SCHEMA_COMPARISON.md` | 原有 Schema 对照 |
| `SCHEMA_COMPARISON_V2.md` | Schema V2 对照 |
| `FINAL_SCHEMA_DECISION.md` | 本文: 最终架构决定 |