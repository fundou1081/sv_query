# DataFlow 分析架构方案

> 创建时间: 2026-05-24
> 状态: ✅ 已实现 (见 DATAFLOW_IMPLEMENTATION_PLAN.md)

---

## 核心洞察

**数据流分析本质上是 GRAPH 问题，不是 Visitor 问题。**

| 层次 | 解决的问题 | 技术手段 |
|------|-----------|----------|
| Visitor | AST 遍历 → 信号提取 | 遍历模式 |
| Graph 算法 | 路径搜索 → 数据流分析 | networkx |

---

## 三层架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: 路径层 (Path Level)                               │
│  DataFlowResult → DataFlowPath → DataFlowSegment            │
│  算法: nx.all_simple_paths()                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: 段层 (Segment Level)                               │
│  DataFlowSegment = from + to + driver + condition + timing  │
│  来源: StatementCollectorVisitor                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: 节点层 (Node Level)                                │
│  SignalResult = primary + all_signals + kind + op + ...    │
│  来源: SignalExpressionVisitor.extract()                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心数据结构

### Layer 1: SignalResult (已实现)

```python
@dataclass
class SignalResult:
    # 核心结果
    primary: Optional[str]              # 单信号名
    all_signals: List[str]              # 所有信号（去重）
    
    # 表达式元信息
    kind_name: Optional[str]            # 'BinaryOp', 'NamedValue'
    op_name: Optional[str]              # 'Add', 'Subtract'
    
    # 位置信息
    source_range: Optional[tuple]        # ((line, col), (line, col))
    
    # 未来扩展（数据流相关）
    condition_signals: List[str]        # 条件信号
    timing: Optional[str]               # '@posedge clk'
    condition_expr: Optional[str]       # 条件表达式原文
```

### Layer 2: DataFlowSegment (NEW)

```python
@dataclass
class DataFlowSegment:
    """单步驱动关系: from_signal → to_signal"""
    
    from_signal: str                    # 起点信号
    to_signal: str                      # 终点信号
    
    driver: SignalResult                 # 驱动表达式结果
    condition: Optional[ConditionInfo]   # 条件信息
    timing: Optional[str]               # '@posedge clk'
    is_blocking: bool                   # 是否阻塞赋值
```

### ConditionInfo (NEW)

```python
@dataclass
class ConditionInfo:
    """条件信息"""
    
    kind: str                           # 'if', 'case', 'conditional_op'
    expr: str                           # 条件表达式原文
    signals: List[str]                  # 条件涉及的信号
    true_branch: str                    # 真分支值
    false_branch: Optional[str]         # 假分支值
```

### Layer 3: DataFlowPath / DataFlowResult (NEW)

```python
@dataclass
class DataFlowPath:
    """单条完整路径"""
    
    path_id: int
    segments: List[DataFlowSegment]
    distance: int                      # 跳数
    has_conditional: bool

class TimingAnalysisResult:
    """路径时序分析结果"""
    
    # 时钟域信息
    path_clock_domains: List[str] = field(default_factory=list)  # 路径经过的时钟域
    dominant_clock_domain: Optional[str] = None  # 主时钟域
    cross_clock_domain: bool = False  # 是否跨时钟域
    
    # 寄存器信息
    register_stages: int = 0  # 寄存器级数
    registers_in_path: List[str] = field(default_factory=list)  # 路径中的寄存器
    
    # 时序路径
    timing_paths: List[List[str]] = field(default_factory=list)  # 寄存器→寄存器路径
    estimated_latency_cycles: int = 0  # 估计延迟（周期数）
    
    # 关键路径
    critical_path: Optional[List[str]] = None  # 关键路径（最长路径）
    
    # 风险评估
    path_timing_risk: str = "safe"  # 路径风险级别: safe/low/medium/high/critical


@dataclass
class DataFlowResult:
    """数据流分析完整结果"""
    
    from_signal: str
    to_signal: str
    
    # 数据流
    paths: List[DataFlowPath] = field(default_factory=list)
    is_reachable: bool = False
    paths_count: int = 0
    
    # 中间信号
    intermediate_signals: Set[str] = field(default_factory=set)
    
    # 条件信息
    all_conditions: List[ConditionInfo] = field(default_factory=list)
    
    # 时序分析 (融合时序分析结果)
    timing_analysis: Optional[TimingAnalysisResult] = None
    clock_domain: Optional[str] = None
    path_timing_risk: str = "safe"
    
    # 便捷属性
    @property
    def cross_clock_domain(self) -> bool:
        """是否跨时钟域"""
        return self.timing_analysis.cross_clock_domain if self.timing_analysis else False
    
    @property
    def register_stages(self) -> int:
        """路径寄存器级数"""
        return self.timing_analysis.register_stages if self.timing_analysis else 0
    
    @property
    def latency_cycles(self) -> int:
        """路径延迟周期数"""
        return self.timing_analysis.estimated_latency_cycles if self.timing_analysis else 0
```

---

## API 设计

```python
class DataFlowAnalyzer:
    """数据流分析器"""
    
    def __init__(self, graph: SignalGraph, adapter: PyslangAdapter):
        self.graph = graph
        self.adapter = adapter
    
    def analyze(self, from_signal: str, to_signal: str) -> DataFlowResult:
        """
        主入口: 分析 from → to 的数据流
        
        步骤:
        1. Path finding (networkx)
        2. Build DataFlowSegment for each hop
        3. Enrich with condition/timing info
        4. Return DataFlowResult
        """
        # 1. 路径搜索
        paths = self._find_all_paths(from_signal, to_signal)
        
        # 2. 构建路径
        data_flow_paths = []
        for path_id, path in enumerate(paths):
            segments = self._build_segments(path)
            df_path = DataFlowPath(
                path_id=path_id,
                segments=segments,
                distance=len(path) - 1,
                has_conditional=any(s.condition for s in segments)
            )
            data_flow_paths.append(df_path)
        
        # 3. 汇总信息
        return DataFlowResult(
            from_signal=from_signal,
            to_signal=to_signal,
            paths=data_flow_paths,
            is_reachable=len(paths) > 0,
            paths_count=len(paths),
            intermediate_signals=self._collect_intermediate(paths),
            all_conditions=self._collect_conditions(data_flow_paths),
            all_timings=self._collect_timings(data_flow_paths)
        )
    
    def _find_all_paths(self, from_signal, to_signal) -> List[List[str]]:
        """使用 networkx 找所有路径"""
        G = self.graph.to_networkx()
        return list(nx.all_simple_paths(G, from_signal, to_signal, cutoff=20))
    
    def _build_segments(self, path: List[str]) -> List[DataFlowSegment]:
        """构建路径段列表"""
        segments = []
        for i in range(len(path) - 1):
            from_sig = path[i]
            to_sig = path[i + 1]
            
            # 查找驱动信息
            driver_stmt = self._get_driver_statement(from_sig, to_sig)
            timing = self._get_timing(driver_stmt)
            condition = self._get_condition(driver_stmt)
            
            segment = DataFlowSegment(
                from_signal=from_sig,
                to_signal=to_sig,
                driver=driver_stmt,
                condition=condition,
                timing=timing
            )
            segments.append(segment)
        
        return segments
```

---

## 与现有系统的集成

```
现有系统                              集成点
────────                            ────────
SignalGraph                         DataFlowAnalyzer.graph
DriverExtractor                     DataFlowSegment 查找
SignalExpressionVisitor.extract()  SignalResult
StatementCollectorVisitor           ConditionInfo 提取
```

### 现有组件

| 组件 | 已有功能 | 数据流分析中的角色 |
|------|----------|-------------------|
| `SignalGraph` | nodes + edges | 路径搜索基础 |
| `DriverExtractor` | get_drivers() | 查找 from→to 驱动源 |
| `SignalExpressionVisitor` | extract() | 生成 SignalResult |
| `StatementCollectorVisitor` | 收集语句上下文 | 生成 ConditionInfo |

### 新增组件

| 组件 | 职责 |
|------|------|
| `DataFlowAnalyzer` | 主分析器，路径搜索 |
| `DataFlowResult` | 结果封装 |
| `DataFlowPath` | 单条路径封装 |
| `DataFlowSegment` | 单步驱动封装 |
| `ConditionInfo` | 条件信息封装 |

---

## 实现优先级

### P1: 核心功能

1. **DataFlowSegment** - 单步驱动数据结构
2. **DataFlowAnalyzer._find_all_paths()** - 路径搜索
3. **DataFlowAnalyzer.analyze()** - 主入口

### P2: 上下文丰富

1. **ConditionInfo** - 条件信息
2. **DataFlowSegment.condition** - 填充条件
3. **DataFlowSegment.timing** - 填充时序

### P3: 高级功能

1. 多路径分析
2. 循环检测
3. 条件覆盖分析

---

## 示例

### 输入

```
module pipeline(input clk, input [7:0] data_in, output [7:0] data_out);
    logic [7:0] stage1, stage2;
    
    always_ff @(posedge clk) begin
        stage1 <= data_in;
        stage2 <= stage1;
    end
    
    assign data_out = stage2;
endmodule
```

### 调用

```python
analyzer = DataFlowAnalyzer(graph, adapter)
result = analyzer.analyze('data_in', 'data_out')
```

### 输出

```python
DataFlowResult:
  from_signal: 'data_in'
  to_signal: 'data_out'
  paths_count: 1
  
  # 数据流
  paths: [
    DataFlowPath:
      path_id: 0
      distance: 3
      segments: [
        DataFlowSegment(from='data_in', to='stage1', timing='@posedge clk'),
        DataFlowSegment(from='stage1', to='stage2', timing='@posedge clk'),
        DataFlowSegment(from='stage2', to='data_out', timing=None)
      ]
  ]
  intermediate_signals: {'stage1', 'stage2'}
  
  # 时序分析 (新增)
  timing_analysis:
    path_clock_domains: ['clk']
    dominant_clock_domain: 'clk'
    cross_clock_domain: False
    register_stages: 2
    registers_in_path: ['stage1', 'stage2']
    estimated_latency_cycles: 2
    critical_path: ['data_in', 'stage1', 'stage2', 'data_out']
    path_timing_risk: 'safe'
  
  clock_domain: 'clk'
  path_timing_risk: 'safe'
```

## 与现有组件的关系

| 组件 | 关系 |
|------|------|
| ClockDomainTracer | 被 DataFlowAnalyzer 复用，复用其 _build_timing_chain 等逻辑 |
| SignalTracer | SignalTracer 是单信号查询，DataFlow 是信号对查询 |
| EdgeKind.CLOCK | 被用于识别时钟驱动的边 |
| NodeKind.REG | 被用于识别路径中的寄存器 |