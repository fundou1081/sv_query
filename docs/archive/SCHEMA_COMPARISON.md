# 现有 Schema vs DataFlow 提案 - 对照分析

> 创建时间: 2026-05-24
> 项目路径: /Users/fundou/my_dv_proj/sv_query

---

## 一、现有 Schema 概览 (data_models.py)

### 1.1 SignalNode (信号节点)

```python
@dataclass(frozen=True)
class SignalNode:
    path: str           # 完整路径
    width: int = 1
    is_port: bool = False
    is_reg: bool = False
```

### 1.2 ConnectionEdge (连接边)

```python
@dataclass
class ConnectionEdge:
    source: str              # 源信号
    sink: str                # 目标信号
    edge_type: str = "driver"   # 连接类型 (字符串)
    source_file: str = ""
    source_line: int = 0
    condition: Optional[str] = None
```

### 1.3 SignalChain (信号链)

```python
@dataclass
class SignalChain:
    root: SignalNode
    
    drivers: List[ConnectionEdge]   # 驱动边 (单跳)
    loads: List[ConnectionEdge]      # 负载边 (单跳)
    data_path: List[str]            # 数据路径
    
    # 分类路径 (硬编码分类)
    via_assignment: List[str]        # assign 路径
    via_sequential: List[str]        # always_ff 路径
    via_combinational: List[str]     # 组合逻辑路径
    
    confidence: str
    caveats: List[str]
```

### 1.4 ClockDomainResult (时钟域结果)

```python
@dataclass
class ClockDomainResult:
    clock_signal: str
    reset_signal: str = ""
    registers: List[str] = field(default_factory=list)
    combinational: List[str] = field(default_factory=list)
    async_crossings: List[ConnectionEdge] = field(default_factory=list)
    risk_level: str = "safe"
    confidence: str
    caveats: List[str]
```

---

## 二、现有 Schema vs DataFlow 提案 对照

### 2.1 节点/信号层

| 现有 (SignalNode) | DataFlow (TraceNode) | 差异 |
|-------------------|---------------------|------|
| path: str | id: str | 同义 |
| width: int | width: Tuple[int, int] | 类型不同 |
| is_port: bool | is_port: bool | 相同 |
| is_reg: bool | kind == NodeKind.REG | 表达方式不同 |
| - | is_clock: bool | **新增** |
| - | is_reset: bool | **新增** |
| - | is_enable: bool | **新增** |
| - | module, name (派生) | **新增** |

### 2.2 连接/边层

| 现有 (ConnectionEdge) | DataFlow (TraceEdge) | 差异 |
|-----------------------|---------------------|------|
| source | src | 同义 |
| sink | dst | 同义 |
| edge_type: str | kind: EdgeKind | 类型安全 |
| condition | condition | 相同 |
| source_file, source_line | (在 TraceNode 中) | 位置不同 |
| - | clock_domain: str | **新增** |
| - | assign_type: str | **新增** |
| - | modport_dir: str | **新增** |

### 2.3 链/路径层

| 现有 (SignalChain) | DataFlow (DataFlowResult) | 差异 |
|--------------------|-------------------------|------|
| root: SignalNode | from_signal, to_signal | 表达方式不同 |
| drivers: List[ConnectionEdge] | paths[0].segments[].driver | 多跳 vs 单跳 |
| loads: List[ConnectionEdge] | (类似) | 相同 |
| data_path: List[str] | paths: List[DataFlowPath] | 结构化程度 |
| via_assignment/sequential/combinational | (由 timing 推导) | 硬编码 vs 自动 |

### 2.4 时钟域层

| 现有 (ClockDomainResult) | DataFlow (TimingAnalysisResult) | 差异 |
|--------------------------|------------------------------|------|
| clock_signal | dominant_clock_domain | 同义 |
| reset_signal | (在 segment 中) | 位置不同 |
| registers | register_stages, registers_in_path | 计数 vs 列表 |
| combinational | (在 path 中) | 分散 vs 集中 |
| async_crossings | cross_clock_domain: True | 边列表 vs 标志 |
| risk_level | path_timing_risk | 同义 |

---

## 三、关键差异分析

### 3.1 edge_type (字符串) vs EdgeKind (枚举)

**现有 ConnectionEdge**:
```python
edge_type: str = "driver"  # 自由字符串，无类型检查
```

**DataFlow TraceEdge**:
```python
kind: EdgeKind  # 枚举，类型安全
    # DRIVER, CLOCK, RESET, CONNECTION, BIT_SELECT
    # CONSTRAINS, HAS_CONDITION, ...
```

**优势**: EdgeKind 枚举更类型安全、可扩展、便于模式匹配

### 3.2 via_* 硬编码 vs timing_analysis 自动推导

**现有 SignalChain**:
```python
via_assignment: List[str]       # 硬编码三种分类
via_sequential: List[str]
via_combinational: List[str]
```

**DataFlow 提案**:
```python
timing_analysis: TimingAnalysisResult
    # 通过 timing_paths 自动推导路径类型
    # 更灵活，可扩展新类型
```

### 3.3 单跳 vs 多跳

**现有 SignalChain**:
```python
drivers: List[ConnectionEdge]  # 只存储直接驱动 (单跳)
# 如果需要多跳，需要自己追踪 data_path
```

**DataFlow 提案**:
```python
paths: List[DataFlowPath]  # 支持多跳完整路径
    # path.segments[0].from_signal → ... → segments[n].to_signal
```

---

## 四、功能缺失对比

### SignalChain 已有
- ✅ 单跳 drivers/loads
- ✅ 基本 data_path
- ✅ 分类路径 (via_*)

### SignalChain 缺失 / DataFlow 新增

| 功能 | SignalChain | DataFlowResult |
|------|:-----------:|:--------------:|
| 多跳完整路径 | ❌ | ✅ |
| 中间信号列表 | ❌ | ✅ |
| 路径条件汇总 | 部分 | ✅ 统一 |
| 延迟周期数 | ❌ | ✅ |
| 跨时钟域标识 | ❌ | ✅ |
| 时序分析融合 | ❌ | ✅ |
| 多路径支持 | ❌ | ✅ |

---

## 五、融合方案

### 方案 A: 扩展现有 Schema (保守)

扩展 SignalChain 添加缺失字段：

```python
@dataclass
class SignalChain:
    # ... 现有字段 ...
    
    # 新增
    paths: List[List[str]] = field(default_factory=list)  # 多跳路径
    intermediate_signals: Set[str] = field(default_factory=set)
    timing_analysis: Optional[TimingAnalysisResult] = None
    register_stages: int = 0
    cross_clock_domain: bool = False
```

**优点**: 改动小，向后兼容
**缺点**: SignalChain 变得臃肿

### 方案 B: 新增 DataFlow Schema (推荐)

新增 `dataflow_models.py`，保持现有 schema 不变：

```python
# dataflow_models.py

@dataclass
class DataFlowSegment:
    from_signal: str
    to_signal: str
    driver: SignalResult
    condition: Optional[ConditionInfo]
    timing: Optional[str]
    is_blocking: bool

@dataclass
class DataFlowPath:
    segments: List[DataFlowSegment]
    distance: int
    has_conditional: bool

@dataclass
class TimingAnalysisResult:
    path_clock_domains: List[str]
    dominant_clock_domain: Optional[str]
    cross_clock_domain: bool
    register_stages: int
    registers_in_path: List[str]
    estimated_latency_cycles: int
    timing_paths: List[List[str]]
    critical_path: Optional[List[str]]
    path_timing_risk: str

@dataclass
class DataFlowResult:
    from_signal: str
    to_signal: str
    paths: List[DataFlowPath]
    is_reachable: bool
    paths_count: int
    intermediate_signals: Set[str]
    all_conditions: List[ConditionInfo]
    timing_analysis: Optional[TimingAnalysisResult]
    clock_domain: Optional[str]
    path_timing_risk: str
```

**优点**:
- 清晰分离，不破坏现有 API
- DataFlow 可独立演进
- 可增量实现

**缺点**:
- 需要新文件

### 方案 C: 重构 data_models.py (激进)

用 DataFlow* 替代 SignalChain/ClockDomainResult：

```python
# data_models.py 重构后
SignalNode → 保留 (小改动)
ConnectionEdge → TraceEdge (字段映射)
SignalChain → DataFlowResult (字段映射)
ClockDomainResult → TimingAnalysisResult (内嵌到 DataFlowResult)
```

**优点**: 架构统一
**缺点**: 破坏现有 API，风险高

---

## 六、推荐方案: 方案 B

**保持现有 data_models.py 不变，新增 dataflow_models.py**

```
src/trace/core/
    data_models.py           # 现有 Schema (保持不变)
    dataflow_models.py       # 新增 DataFlow Schema
    
# 使用方式
chain = tracer.trace(signal)         # 现有 API → SignalChain
flow = analyzer.analyze(from, to)  # 新 API → DataFlowResult
```

### 复用关系

```
data_models.py (现有)
    SignalChain.drivers[0].condition
           ↓ 复用
    DataFlowSegment.condition: ConditionInfo
    
data_models.py (现有)
    ClockDomainResult.registers
           ↓ 复用
    DataFlowSegment.timing / TimingAnalysisResult
```

### 实现优先级

| 优先级 | 组件 | 工作量 |
|--------|------|--------|
| P1 | dataflow_models.py (基础类) | 1-2h |
| P1 | DataFlowSegment | 1h |
| P2 | TimingAnalysisResult | 2h |
| P2 | DataFlowPath / DataFlowResult | 2h |
| P3 | ConditionInfo | 2h |
| P3 | DataFlowAnalyzer | 1-2天 |

---

## 七、文档索引

| 文档 | 内容 |
|------|------|
| `ARCHITECTURE_COMPARISON.md` | 架构层面对照 |
| `DATAFLOW_ANALYSIS_ARCHITECTURE.md` | DataFlow 详细设计 |
| `SCHEMA_COMPARISON.md` | 本文: Schema 对照 |