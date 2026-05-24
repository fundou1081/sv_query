# sv_query 现有架构 vs DataFlow 提案 - 对照分析

> 创建时间: 2026-05-24
> 更新时间: 2026-05-24 (整合时序分析)
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
| 4 | ClockDomainTracer | 时钟域追踪 |
| 5 | UnifiedTracer | 统一入口 |

### 1.3 现有架构中的时序/条件信息

**关键发现**: 现有架构已经在 TraceEdge 中存储了条件和时钟域信息！

```python
class TraceEdge:
    src: str
    dst: str
    kind: EdgeKind
    
    # 已有时序/条件字段
    condition: str       # 条件表达式 (if/enable)
    clock_domain: str    # 时钟域
    assign_type: str      # 赋值类型 (blocking/nonblocking/assign)

class TraceNode:
    id: str
    kind: NodeKind
    
    # 已有信号属性
    is_clock: bool       # 是否时钟
    is_reset: bool       # 是否复位
    is_enable: bool      # 是否使能
```

**EdgeKind 枚举**:
```python
class EdgeKind:
    DRIVER = auto()      # 数据驱动 (q <= d)
    CLOCK = auto()       # 时钟触发 (clk → q)
    RESET = auto()       # 异步复位 (rst_n → q)
    CONNECTION = auto()  # 模块端口连接
```

### 1.4 SignalGraph 结构

```python
class SignalGraph(nx.DiGraph):
    """继承自 networkx DiGraph，可直接使用 nx 算法"""
    _node_data: Dict[str, TraceNode]   # {signal_id: TraceNode}
    _edge_data: Dict[Tuple, TraceEdge] # {(src, tgt): TraceEdge}
    _port_to_internal: Dict[str, str]
```

---

## 二、现有 Query 能力

| Tracer | 能力 | 输入 | 输出 |
|--------|------|------|------|
| SignalTracer | 单信号追踪 | signal | drivers/loads (单跳) |
| LoadTracer | 负载追踪 | signal | loads (单跳) |
| ClockDomainTracer | 时钟域分析 | clock | registers, cross-domain paths |
| ModuleTracer | 模块连接 | module | connections |

**缺失能力**: 无多跳路径查询 (from → to 的所有路径)

---

## 三、DataFlow 提案架构

### 3.1 三层架构

```
Layer 1: SignalResult (节点层)
    - 单表达式信号提取
    - 来自 SignalExpressionVisitor.extract()

Layer 2: DataFlowSegment (段层)
    - 单步驱动: from_signal → to_signal
    - driver: SignalResult
    - condition: ConditionInfo
    - timing: str (@posedge clk)

Layer 3: DataFlowPath / DataFlowResult (路径层)
    - 完整路径分析 + 时序分析
    - 算法: nx.all_simple_paths()
    - 复用 ClockDomainTracer
```

### 3.2 时序分析融合

```python
class TimingAnalysisResult:
    # 时钟域
    path_clock_domains: List[str]
    dominant_clock_domain: str
    cross_clock_domain: bool
    
    # 寄存器
    register_stages: int
    registers_in_path: List[str]
    
    # 时序
    estimated_latency_cycles: int
    timing_paths: List[List[str]]
    
    # 风险
    path_timing_risk: str
```

### 3.3 DataFlowAnalyzer API

```python
class DataFlowAnalyzer:
    def __init__(self, graph: SignalGraph, adapter: PyslangAdapter):
        self.graph = graph
        self.adapter = adapter
    
    def analyze(self, from_signal: str, to_signal: str) -> DataFlowResult:
        # 1. 路径搜索 (直接使用 nx.DiGraph)
        paths = list(nx.all_simple_paths(self.graph, from_signal, to_signal, cutoff=20))
        
        # 2. 构建 DataFlowSegments
        segments = self._build_segments(paths[0])
        
        # 3. 时序分析 (复用 ClockDomainTracer)
        timing = self._analyze_timing(segments)
        
        return DataFlowResult(
            from_signal=from_signal,
            to_signal=to_signal,
            paths=[DataFlowPath(segments=segments)],
            timing_analysis=timing,
            ...
        )
```

---

## 四、关键差异对比

| 维度 | 现有架构 | DataFlow 提案 |
|------|----------|---------------|
| 图类型 | SignalGraph (nx.DiGraph) | SignalGraph (不变) |
| 边描述 | TraceEdge (存储层) | DataFlowSegment (视图层) |
| 路径查询 | ❌ 无 | ✅ nx.all_simple_paths() |
| 条件信息 | TraceEdge.condition | ConditionInfo (统一封装) |
| 时序信息 | TraceEdge.clock_domain | TimingAnalysisResult |
| 延迟估算 | ❌ 无 | ✅ register_stages |
| 多路径 | ❌ 不支持 | ✅ 支持 |

---

## 五、融合设计

### 5.1 架构愿景

```
                    UnifiedTracer
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
    SignalTracer      LoadTracer    DataFlowAnalyzer
        │                 │                 │
    trace(signal)    trace_load    analyze(from, to)
        │                 │                 │
    ┌───┴───┐         ┌───┴───┐        ┌────┴────┐
    │drivers│         │loads  │        │paths    │
    │loads  │         │       │        │segments │
    └───────┘         └───────┘        │timing   │
                                       │conditions
                                       └─────────┘
                                            │
                                  ┌────────┴────────┐
                                  │                 │
                              TraceEdge         DataFlowSegment
                              (存储层)           (视图层)
                                  │
                         SignalGraph (nx.DiGraph)
```

### 5.2 DataFlowSegment 作为视图层

**方案B (推荐)**: DataFlowSegment 不替代 TraceEdge，而是作为视图层

```python
class DataFlowSegment:
    """DataFlowSegment 是 TraceEdge 的丰富视图"""
    
    from_signal: str
    to_signal: str
    driver: SignalResult           # 丰富: SignalResult
    condition: ConditionInfo       # 丰富: 统一封装
    timing: Optional[str]          # 丰富: 时序信息
    is_blocking: bool
    
    @classmethod
    def from_edge(cls, edge: TraceEdge, adapter) -> 'DataFlowSegment':
        """从 TraceEdge 构建 DataFlowSegment"""
        # 从 edge 提取基本信息
        # 从 StatementCollectorVisitor 丰富 condition
        # 从 SignalExpressionVisitor 丰富 driver
        ...
```

**优点**:
- 保持 TraceEdge 简洁
- DataFlowSegment 可独立演进
- 与现有系统解耦

### 5.3 复用现有组件

| 组件 | 复用方式 |
|------|----------|
| SignalGraph | 图结构不变，直接调用 nx 算法 |
| TraceEdge | .condition, .clock_domain → DataFlowSegment.timing |
| SignalExpressionVisitor.extract() | → SignalResult.driver |
| StatementCollectorVisitor | → ConditionInfo |
| ClockDomainTracer | → TimingAnalysisResult |
| ClockDomainTracer._build_timing_chain() | → timing_paths |

---

## 六、组件能力矩阵

| 能力 | SignalTracer | ClockDomainTracer | DataFlowAnalyzer |
|------|:------------:|:-----------------:|:-----------------:|
| 单信号查询 | ✅ | ❌ | ❌ |
| 单跳驱动 | ✅ | ❌ | ❌ |
| 域级分析 | ❌ | ✅ | 部分 |
| **多跳路径** | ❌ | ❌ | ✅ |
| **条件统一封装** | ❌ | ❌ | ✅ |
| **时序融合** | ❌ | ✅ | ✅ |
| **延迟估算** | ❌ | ❌ | ✅ |
| **多路径支持** | ❌ | ❌ | ✅ |

---

## 七、与现有系统集成

### 7.1 DataFlowSegment 的信息来源

```python
def _build_segments(self, path: List[str]) -> List[DataFlowSegment]:
    segments = []
    for i in range(len(path) - 1):
        from_sig = path[i]
        to_sig = path[i + 1]
        
        # 1. 从 TraceEdge 获取基本信息
        edge = self.graph.get_edge(from_sig, to_sig)
        
        # 2. SignalResult (从 SignalExpressionVisitor)
        driver_result = self._signal_visitor.extract(edge)  # 使用新的 extract()
        
        # 3. ConditionInfo (从 StatementCollectorVisitor)
        condition = self._get_condition_for_edge(edge)
        
        # 4. Timing (从 TraceEdge.clock_domain 或 _extract_clock)
        timing = edge.clock_domain if edge else None
        
        segments.append(DataFlowSegment(
            from_signal=from_sig,
            to_signal=to_sig,
            driver=driver_result,
            condition=condition,
            timing=timing
        ))
    
    return segments
```

### 7.2 时序分析复用

```python
def _analyze_timing(self, segments: List[DataFlowSegment]) -> TimingAnalysisResult:
    # 复用 ClockDomainTracer 的逻辑
    if self._clock_tracer is None:
        self._clock_tracer = ClockDomainTracer(self.graph)
    
    # 收集路径中的时钟域
    clock_domains = set(s.timing for s in segments if s.timing)
    
    # 收集路径中的寄存器
    registers = [s.to_signal for s in segments 
                 if self.graph.get_node(s.to_signal).kind == NodeKind.REG]
    
    # 计算延迟周期数 = 寄存器级数
    latency = len(registers)
    
    return TimingAnalysisResult(
        path_clock_domains=list(clock_domains),
        register_stages=len(registers),
        registers_in_path=registers,
        estimated_latency_cycles=latency,
        cross_clock_domain=len(clock_domains) > 1,
        ...
    )
```

---

## 八、实现优先级

### P1: 核心框架 (1-2天)

1. DataFlowSegment 数据类
2. DataFlowPath / DataFlowResult 数据类
3. DataFlowAnalyzer._find_all_paths()

**产出**: 可以查询 from→to 的所有路径

### P2: 时序融合 (2-3天)

1. TimingAnalysisResult 数据类
2. DataFlowAnalyzer._analyze_timing()
3. 复用 ClockDomainTracer 逻辑

**产出**: 路径延迟估算

### P3: 上下文丰富 (长期)

1. ConditionInfo 数据类
2. DataFlowSegment.condition 填充
3. DataFlowSegment.timing 填充

---

## 九、文档索引

| 文档 | 内容 |
|------|------|
| `ARCHITECTURE_COMPARISON.md` | 本文: 架构对照分析 |
| `DATAFLOW_ANALYSIS_ARCHITECTURE.md` | DataFlow 详细设计 |
| `ARCHITECTURE_IMPROVEMENT.md` | Visitor 单 dispatch 改进 |