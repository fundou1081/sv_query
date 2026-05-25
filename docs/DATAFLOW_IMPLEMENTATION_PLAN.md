# DataFlowGraph Implementation Plan

## 目标
实现基于 SignalGraph + MIG 的 DataFlowGraph，支持跨模块的完整数据流分析。

## 文件位置
`src/trace/core/graph/dataflow.py`

## 核心数据结构

### DataFlowSegment
```python
@dataclass
class DataFlowSegment:
    from_signal: str           # 完整 hierarchy path
    to_signal: str             # 完整 hierarchy path
    driver: Optional[str]       # 驱动表达式
    condition: Optional[str]   # 驱动条件
    timing: Optional[str]      # 时钟域
    assign_type: str           # continuous/always_ff/always_comb
    distance: int              # 距离（跳数）
```

### DataFlowPath
```python
@dataclass
class DataFlowPath:
    path_id: int
    segments: List[DataFlowSegment]
    distance: int             # 总跳数
    has_conditional: bool
```

### DataFlowResult
```python
@dataclass
class DataFlowResult:
    from_signal: str
    to_signal: str
    paths: List[DataFlowPath]
    is_reachable: bool
    paths_count: int
    intermediate_signals: Set[str]
    all_conditions: List[str]
    clock_domain: Optional[str]
    timing_risk: str          # safe/low/medium/high/critical
```

## DataFlowGraph 类

```python
class DataFlowGraph:
    def __init__(self, signal_graph: SignalGraph, mig: ModuleInstanceGraph):
        self.signal_graph = signal_graph
        self.mig = mig
        self._segment_cache: Dict[Tuple[str, str], DataFlowSegment] = {}
    
    def analyze(self, from_signal: str, to_signal: str) -> DataFlowResult:
        """分析 from → to 的完整数据流路径"""
        
    def get_segment(self, from_signal: str, to_signal: str) -> DataFlowSegment:
        """获取单步驱动信息（带缓存）"""
        
    def _build_segment(self, from_signal: str, to_signal: str) -> DataFlowSegment:
        """构建段信息"""
        
    def _find_paths(self, from_signal: str, to_signal: str) -> List[List[str]]:
        """使用 networkx 找所有路径（允许循环）"""
        
    def _resolve_cross_module(self, signal: str) -> str:
        """解析跨模块信号，返回内部信号"""
```

## 实现步骤

### Phase 1: 基础结构
1. 创建 `dataflow.py`
2. 实现 `DataFlowSegment`, `DataFlowPath`, `DataFlowResult` 数据类
3. 实现 `DataFlowGraph.__init__`
4. 实现 `_find_paths` 路径搜索

### Phase 2: 段构建
1. 实现 `get_segment` 带缓存
2. 实现 `_build_segment`
3. 从 SignalGraph edge 获取 condition/timing

### Phase 3: 跨模块支持
1. 实现 `_resolve_cross_module`
2. 集成 MIG 的 port_to_internal 映射

### Phase 4: 结果组装
1. 实现 `analyze` 方法
2. 组装 DataFlowResult
3. 收集 intermediate_signals, all_conditions

## 与现有组件的集成

```python
# 在 unified_tracer.py 或新建 dataflow_analyzer.py
from .graph.dataflow import DataFlowGraph

class DataFlowAnalyzer:
    def __init__(self, signal_graph, mig):
        self.dfg = DataFlowGraph(signal_graph, mig)
    
    def analyze(self, from_signal, to_signal):
        return self.dfg.analyze(from_signal, to_signal)
```

## 待实现
- [x] 创建 dataflow.py
- [x] 数据类定义 (DataFlowSegment, DataFlowPath, DataFlowResult)
- [x] DataFlowGraph 基础结构
- [x] 路径搜索 (_find_paths)
- [x] 段构建与缓存 (get_segment, _build_segment)
- [x] 跨模块信号解析 (_resolve_cross_module)
- [x] analyze() 方法
- [x] 时钟域提取 (_extract_clock_domain)
- [x] 路径风险评估 (_evaluate_timing_risk)
- [x] 缓存统计 (get_cache_stats)
- [x] 集成到 graph/__init__.py
- [x] BIT_SELECT 节点处理 (byte_data[3:0] → byte_data 路径扩展)
- [x] Struct 成员展开 (pkt1.data → pkt2.data 成员赋值展开)
- [x] MEMBER_SELECT 边 (struct.member → struct 父节点追踪)

## 测试结果 (2026-05-26)

| 测试用例 | 结果 |
|---------|------|
| `byte_data → byte_low` (位选择) | ✅ |
| `byte_data → byte_high` (位选择) | ✅ |
| `pkt1.data → pkt2.data` (struct 赋值) | ✅ |
| `data_in → data_out` (完整 struct 路径) | ✅ (6条路径) |
| 循环检测 (组合逻辑环) | ✅ |
| 循环检测 (寄存器环) | ✅ |
| 839 tests passed | ✅ |