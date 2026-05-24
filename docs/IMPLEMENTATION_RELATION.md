# 源代码实现与 DataFlow 提案的关系

> 创建时间: 2026-05-24
> 状态: 分析完成

---

## 一、数据流架构

```
┌─────────────────────────────────────────────────────────────────┐
│  graph_builder.py (DriverExtractor)                              │
│  ─────────────────────────────────────────────────────────────  │
│  输入: SystemVerilog 源码                                         │
│  处理: 遍历 AST，提取 nodes + edges                                │
│  输出: ExtractorResult (nodes, edges)                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  graph/models.py (SignalGraph)                                    │
│  ─────────────────────────────────────────────────────────────  │
│  存储: _node_data: Dict[str, TraceNode]                           │
│        _edge_data: Dict[Tuple, TraceEdge]                        │
│  图结构: 继承 nx.DiGraph                                          │
│  核心字段: TraceEdge.condition, clock_domain, assign_type        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  query/signal.py (SignalTracer)                                  │
│  ─────────────────────────────────────────────────────────────  │
│  输入: signal_id                                                  │
│  处理: trace_drivers_recursive() 追溯驱动                        │
│  输出: SignalChain (drivers, loads)                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  unified_tracer.py                                               │
│  ─────────────────────────────────────────────────────────────  │
│  对外 API: trace(), trace_clock_domain()                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、DataFlow 提案的核心需求

| 需求 | 描述 |
|------|------|
| 1. 路径搜索 | from → to 完整路径 (多跳) |
| 2. driver 信息 | 每段的驱动表达式 (SignalResult) |
| 3. condition 信息 | 每段的条件使能 (ConditionInfo) |
| 4. timing 信息 | 每段的时钟域 (TraceEdge.clock_domain) |

---

## 三、现有实现分析

### 需求 1: from → to 路径搜索

**现状**: ✅ 已满足，但没有被使用

```python
# SignalGraph 继承 nx.DiGraph
graph = SignalGraph()
paths = list(nx.all_simple_paths(graph, 'a', 'd'))
# [['a', 'b', 'c', 'd']]

# 问题: SignalTracer 只追溯直接驱动，不做完整路径搜索
```

### 需求 2: 每段的 driver 信息

**现状**: ⚠️ 部分满足

```python
# StatementCollectorVisitor 已收集 statements
class StatementCollectorVisitor:
    statements: List[StatementInfo]  # 每条赋值的信息

class StatementInfo:
    stmt: Any
    lhs_signal: str
    rhs_signals: List[str]
    clock: str
    condition: str

# 问题: drivers/loads 只返回 TraceNode，没有 StatementInfo
```

### 需求 3: 每段的 condition 信息

**现状**: ⚠️ 需要转换

```python
# TraceEdge.condition 是字符串
TraceEdge.condition = "en"  # 字符串，没有结构化

# 需要 ConditionInfo 结构化
class ConditionInfo:
    kind: str           # 'if', 'case', 'ternary'
    expr: str           # 'en'
    signals: List[str]  # ['en']
    branches: List[str]  # ['if分支', 'else分支']
```

### 需求 4: 每段的 timing 信息

**现状**: ✅ 已满足

```python
# TraceEdge.clock_domain
TraceEdge.clock_domain = "clk"  # 时钟域
```

---

## 四、关键差距

### SignalTracer 返回 vs DataFlow 提案返回

**SignalTracer (当前)**:
```python
SignalChain(
    root='q',
    drivers=[TraceNode('d'), TraceNode('a')],  # 只返回直接驱动 (单跳)
    loads=[TraceNode('y')],
    confidence='high'
)
```

**DataFlow (提案)**:
```python
DataFlowResult(
    from_signal='a',
    to_signal='q',
    paths=[DataFlowPath(segments=[
        DataFlowSegment(from_signal='a', to_signal='b', 
                       driver=SignalResult(...), 
                       condition=ConditionInfo(...),
                       timing='@posedge clk'),
        DataFlowSegment(from_signal='b', to_signal='q', ...),
    ])]
)
```

### 差距总结

| 差距 | 说明 |
|------|------|
| 1. 完整路径 | SignalChain 只有直接驱动，DataFlow 有完整路径 |
| 2. driver 表达式 | SignalChain.drivers 只有 TraceNode，没有表达式 |
| 3. 每段上下文 | DataFlow 每段有 condition/timing/driver |

---

## 五、如何实现 DataFlow (基于现有代码)

### 方案: 新增 DataFlowAnalyzer，复用现有组件

```
┌─────────────────────────────────────────────────────────────────┐
│  DataFlowAnalyzer                                                 │
│  ─────────────────────────────────────────────────────────────  │
│  依赖:                                                             │
│    - SignalGraph (提供 edges 和 TraceEdge)                       │
│    - StatementCollectorVisitor (提供 driver 表达式)               │
│    - SignalExpressionVisitor.extract() (提供 SignalResult)        │
│                                                                  │
│  实现:                                                             │
│    1. nx.all_simple_paths() 找所有路径                            │
│    2. 对每段 edge，查询 TraceEdge.condition/clock_domain         │
│    3. 对每段 edge，使用 StatementCollectorVisitor 获取 driver      │
│    4. 构建 DataFlowSegment                                       │
│    5. 返回 DataFlowResult                                        │
└─────────────────────────────────────────────────────────────────┘
```

### DataFlowAnalyzer 伪代码

```python
class DataFlowAnalyzer:
    def __init__(self, graph: SignalGraph, adapter: PyslangAdapter):
        self.graph = graph
        self.adapter = adapter
        self._stmt_visitor = StatementCollectorVisitor(adapter)
    
    def analyze(self, from_signal: str, to_signal: str) -> DataFlowResult:
        # 1. 找所有路径
        paths = list(nx.all_simple_paths(self.graph, from_signal, to_signal))
        
        # 2. 构建 DataFlowSegment
        dataflow_paths = []
        for path in paths:
            segments = []
            for i in range(len(path) - 1):
                from_sig = path[i]
                to_sig = path[i + 1]
                
                # 3. 获取 TraceEdge 信息
                edge = self.graph._edge_data.get((from_sig, to_sig))
                
                # 4. 获取 driver 信息
                driver_result = self._get_driver_for_edge(from_sig, to_sig)
                
                # 5. 构建 ConditionInfo
                condition = None
                if edge and edge.condition:
                    condition = ConditionInfo(
                        expr=edge.condition,
                        signals=self._extract_signals(edge.condition)
                    )
                
                segments.append(DataFlowSegment(
                    from_signal=from_sig,
                    to_signal=to_sig,
                    driver=driver_result,
                    condition=condition,
                    timing=edge.clock_domain if edge else None
                ))
            
            dataflow_paths.append(DataFlowPath(segments=segments))
        
        return DataFlowResult(
            from_signal=from_signal,
            to_signal=to_signal,
            paths=dataflow_paths,
            is_reachable=len(paths) > 0,
            paths_count=len(paths)
        )
```

---

## 六、现有组件复用情况

| 组件 | 可否复用 | 说明 |
|------|---------|------|
| graph_builder.py | ✅ 直接复用 | ExtractorResult 已包含 edges |
| graph/models.py | ✅ 直接复用 | TraceEdge 有 condition, clock_domain |
| SignalGraph | ✅ 直接复用 | nx.DiGraph，提供路径搜索 |
| StatementCollectorVisitor | ✅ 直接复用 | statements 有 driver 信息 |
| SignalExpressionVisitor | ✅ 直接复用 | extract() 提供 SignalResult |
| query/signal.py | ⚠️ 独立实现 | DataFlowAnalyzer 是新类 |
| data_models.py | ⚠️ 独立实现 | DataFlowResult 是新类 |

---

## 七、结论

**现有代码可以支持 DataFlow，但需要新增 DataFlowAnalyzer**

不需要修改:
- ❌ graph_builder.py
- ❌ graph/models.py
- ❌ query/signal.py (SignalTracer)
- ❌ StatementCollectorVisitor
- ❌ SignalExpressionVisitor

需要新增:
- ✅ dataflow_models.py (DataFlowSegment, DataFlowPath, DataFlowResult)
- ✅ DataFlowAnalyzer (使用 nx.all_simple_paths() + 复用现有组件)

---

## 八、文档索引

| 文档 | 内容 |
|------|------|
| `FINAL_SCHEMA_DECISION.md` | DataFlow 架构决定 |
| `DATAFLOW_ANALYSIS_ARCHITECTURE.md` | DataFlow 详细设计 |
| `SCHEMA_COMPARISON_V2.md` | Schema 对照 |
| `IMPLEMENTATION_RELATION.md` | 本文: 源代码与 DataFlow 关系 |