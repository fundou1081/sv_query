# 增强后 data_models.py vs DataFlowAnalyzer Schema 对比

> 创建时间: 2026-05-24
> 状态: 分析完成

---

## 一、方案选择回顾

| 时间 | 建议 | 说明 |
|------|------|------|
| 最初 | 方案B | 新增 dataflow_models.py，保持现有 schema 不变 |
| 后来 | 方案A | 增强 data_models.py，向后兼容 |

现在重新评估: **增强后的 data_models.py 是否足够？**

---

## 二、增强后 data_models.py 能力

### SignalChain 增强字段

```python
@dataclass
class SignalChain:
    # 原有字段 (保持兼容)
    root: SignalNode
    drivers: List[ConnectionEdge]
    loads: List[ConnectionEdge]
    ...
    
    # 增强: DataFlow 支持
    paths: List[List[str]]                    # 多跳路径
    intermediate_signals: Set[str]           # 中间信号
    timing_analysis: Optional[TimingAnalysisResult]  # 时序分析
    conditions: List[ConditionInfo]            # 条件列表
    data_flow_when: str                       # 数据流成立条件
    
    # 增强: ControlFlow 支持
    control_dependencies: Dict[str, List[str]]  # 控制依赖
    state_transitions: List[StateTransition]   # 状态转换
    branch_coverage: float                    # 分支覆盖
```

### 新增便捷属性

```python
@property
def latency_cycles(self) -> int:
    return self.timing_analysis.register_stages if self.timing_analysis else 0

@property
def is_conditional(self) -> bool:
    return len(self.conditions) > 0

@property
def enable_conditions(self) -> List[str]:
    return [c.expr for c in self.conditions if c.kind == 'if']

@property
def has_state_machine(self) -> bool:
    return len(self.state_transitions) > 0
```

---

## 三、DataFlowAnalyzer 提案 Schema

### DataFlowResult

```python
@dataclass
class DataFlowResult:
    from_signal: str
    to_signal: str
    
    paths: List[DataFlowPath]              # 多条路径
    is_reachable: bool
    paths_count: int
    
    intermediate_signals: Set[str]         # 中间信号
    all_conditions: List[ConditionInfo]     # 路径所有条件
    
    timing_analysis: Optional[TimingAnalysisResult]  # 时序分析
    clock_domain: Optional[str]
    path_timing_risk: str
```

### DataFlowPath

```python
@dataclass
class DataFlowPath:
    path_id: int
    segments: List[DataFlowSegment]       # 路径段
    distance: int                          # 跳数
    has_conditional: bool
```

### DataFlowSegment (关键差异)

```python
@dataclass
class DataFlowSegment:
    """每段路径的完整上下文"""
    
    from_signal: str                       # 起点
    to_signal: str                         # 终点
    
    driver: SignalResult                   # 驱动表达式 (丰富)
    condition: Optional[ConditionInfo]     # 条件 (关联到本段)
    timing: Optional[str]                  # 时序 (关联到本段)
    is_blocking: bool
```

---

## 四、关键差异对比

| 维度 | 增强 data_models.py | DataFlowAnalyzer Schema |
|------|---------------------|------------------------|
| **路径结构** | `List[List[str]]` | `List[DataFlowPath]` |
| **段信息** | `ConnectionEdge` (基础) | `DataFlowSegment` (丰富) |
| **Driver 信息** | `source: str` | `driver: SignalResult` |
| **条件信息** | `conditions: List[...]` (全局) | 每个 `segment.condition` (段级) |
| **时序信息** | `timing_analysis` (全局) | 每个 `segment.timing` (段级) |
| **上下文关联** | conditions 与路径段分离 | 每个 segment 独立关联 |
| **向后兼容** | ✅ 完全兼容 | ❌ 新类 |

---

## 五、核心差异分析

### 差异 1: 路径 vs 段

**增强 data_models.py**:
```python
paths: [['a', 'b', 'c', 'd']]

# 问题: 'b' → 'c' 这一段的 condition/timing 丢失
# 无法知道哪段有条件，哪段有 clock
```

**DataFlowAnalyzer**:
```python
paths[0].segments[0]: 'a' → 'b'  timing='@posedge clk'
paths[0].segments[1]: 'b' → 'c'  condition='if(en)'
paths[0].segments[2]: 'c' → 'd'  timing=None
# ✅ 每段都有完整上下文
```

### 差异 2: Driver 信息

**增强 data_models.py**:
```python
ConnectionEdge(source='b')
# 问题: 不知道 b 是如何计算的，是 a+d 还是 a&d？
```

**DataFlowAnalyzer**:
```python
DataFlowSegment(
    to_signal='b',
    driver=SignalResult(
        primary='b',
        all_signals=['a', 'd'],
        kind_name='BinaryOp',
        op_name='Add'  # ✅ 知道是加法
    )
)
```

### 差异 3: 条件上下文

**增强 data_models.py**:
```python
conditions: [ConditionInfo(kind='if', expr='en')]
# 问题: 不知道 en 条件应用于哪一段
```

**DataFlowAnalyzer**:
```python
segments[1].condition: ConditionInfo(kind='if', expr='en')
# ✅ 条件明确关联到 'b' → 'c' 段
```

---

## 六、结论

### 方案 A: 增强 data_models.py

| 优点 | 缺点 |
|------|------|
| ✅ 向后兼容 | ❌ paths 是简单列表，段上下文丢失 |
| ✅ 改动最小 | ❌ 每段的条件/timing 无法关联 |
| ✅ 现有代码不变 | ❌ Driver 信息不完整 |
| | ❌ 无法满足完整 DataFlow 需求 |

**结论**: 适合简单场景，作为临时方案

### 方案 B: DataFlowAnalyzer Schema (新增)

| 优点 | 缺点 |
|------|------|
| ✅ 每段有完整上下文 | ❌ 需要新文件/新类 |
| ✅ 路径和段分离，结构清晰 | ❌ 与现有 API 不同 |
| ✅ API 原生设计，无历史包袱 | |
| ✅ 支持并行化 | |

**结论**: 适合完整 DataFlow/ControlFlow 功能，长期方案

---

## 七、最终建议

### 两阶段方案

```
阶段 1: 使用增强的 data_models.py (当前)
    - 用于简单查询 (现有功能)
    - paths 字段支持基本多跳
    - 时序/条件信息作为参考
    ↓
    SignalChain.paths = [['a', 'b', 'c', 'd']]
    SignalChain.conditions = [ConditionInfo(...)]
    
阶段 2: 如果需要完整 DataFlow 功能
    - 新增 dataflow_models.py
    - DataFlowAnalyzer 返回 DataFlowResult
    - 保持现有 API 不变，新增专用查询
    ↓
    DataFlowResult.paths[0].segments[0].condition = ConditionInfo(...)
```

### 关键: 两者可以共存

```python
# 现有 API (SignalChain)
chain = tracer.trace(signal) → SignalChain

# 新 API (DataFlowResult)
flow = analyzer.analyze(from, to) → DataFlowResult
```

### 架构分层

```
SignalChain (现有 API)
    └── 简单场景: "信号 X 的驱动源是什么？"

DataFlowResult (新 API)
    └── 复杂场景: "信号 A 到 B 的完整路径，每段的时钟域和条件是什么？"
```

---

## 八、下一步建议

1. **短期**: 使用增强的 data_models.py 满足基本需求
2. **中期**: 如果 DataFlow 功能需要完整上下文，再新增 dataflow_models.py
3. **不冲突**: 两者可以共存，根据场景选择使用