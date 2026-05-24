# 源代码实现与 ControlFlow 提案的关系

> 创建时间: 2026-05-24
> 状态: 分析完成

---

## 一、ControlFlow 提案的核心需求

| 需求 | 描述 |
|------|------|
| 1. 条件使能分析 | 哪些信号受条件控制，条件为真/假时数据是否流动 |
| 2. 分支覆盖分析 | if/else/case 分支完整性 |
| 3. 状态机状态转换图 | 状态转换条件，当前/下一状态 |
| 4. 控制依赖链传播 | en 信号控制数据流动 |

---

## 二、现有实现分析

### 需求 1: 条件使能分析

**现状**: ⚠️ 部分满足

```python
# graph_builder.py 已提取
TraceEdge.condition = "en"  # 条件表达式 (字符串)

# StatementCollectorVisitor 已收集
statement.condition = "en"
```

**需要**: ConditionInfo 结构化

```python
class ConditionInfo:
    kind: str           # 'if', 'case', 'ternary'
    expr: str           # 'en'
    signals: List[str]  # ['en']  ← SignalExpressionVisitor.extract() 可提供
    branches: List[str]  # ['if分支', 'else分支']  ← 需要从 AST 提取
```

### 需求 2: 分支覆盖分析

**现状**: ❌ 不支持

```python
# graph_builder.py 已处理 if/case 语句
# 但没有收集分支覆盖信息

# 需要新增:
- 从 ConditionalStatementSyntax.conditions 提取分支
- 从 CaseStatementSyntax.when_items 提取分支
```

### 需求 3: 状态机状态转换图

**现状**: ❌ 不支持

```python
# StatementCollectorVisitor 已收集
statement.lhs_signal  # 当前状态信号
statement.rhs_signals # 下一状态表达式

# 但没有构建状态转换图
# 需要新增:
- 状态信号识别 (命名规则: *_state, *_status)
- case 语句中状态转换提取
- StateTransition 图构建
```

### 需求 4: 控制依赖链传播

**现状**: ❌ 不支持

```python
# 现有: TraceEdge.condition = "en"

# 需要:
ControlDependency(
    enable_signal='en',
    data_signals=['d', 'q'],  # 受 en 控制的信号
    condition='if (en)'
)

# 实现: 从 TraceEdge.condition 提取 enable_signal，沿边传播
```

---

## 三、关键差距

| 需求 | 现有 | 状态 | 需要新增 |
|------|------|------|----------|
| condition 字符串 | TraceEdge.condition | ✅ 已有 | - |
| condition 结构化 | SignalExpressionVisitor.extract() | ✅ 已有 | - |
| 分支覆盖 | 无 | ❌ | 分支提取逻辑 |
| 状态转换图 | 无 | ❌ | 状态机识别 + 图构建 |
| 控制依赖链 | 无 | ❌ | 依赖传播算法 |

---

## 四、如何实现 ControlFlow

### 方案: 新增 ControlFlowAnalyzer，复用现有组件

```
┌─────────────────────────────────────────────────────────────────┐
│  ControlFlowAnalyzer                                           │
│  ───────────────────────────────────────────────────────────── │
│  依赖:                                                          │
│    - SignalGraph (edges + TraceEdge.condition)                   │
│    - SignalExpressionVisitor.extract() (结构化 condition)      │
│    - StatementCollectorVisitor.statements                      │
│                                                                   │
│  实现:                                                          │
│    1. 遍历 edges，提取 condition                                 │
│    2. 使用 SignalExpressionVisitor.extract() 结构化           │
│    3. 构建 ConditionInfo                                        │
│    4. 分析分支覆盖 (if/else/case)                              │
│    5. 识别状态机，构建 StateTransition                         │
│    6. 构建控制依赖链                                             │
│    7. 返回 ControlFlowResult                                    │
└─────────────────────────────────────────────────────────────────┘
```

### ConditionInfo 构建伪代码

```python
def _build_condition_info(self, condition_expr, condition_kind) -> ConditionInfo:
    # 1. 使用 SignalExpressionVisitor.extract() 结构化
    result = self._signal_visitor.extract(condition_expr)
    
    # 2. 提取 signals
    signals = result.all_signals if result else []
    
    # 3. 提取 branches (if/else)
    branches = []
    if condition_kind == 'if':
        branches = self._extract_if_branches(condition_expr)
    elif condition_kind == 'case':
        branches = self._extract_case_branches(condition_expr)
    
    return ConditionInfo(
        kind=condition_kind,
        expr=str(condition_expr),
        signals=signals,
        branches=branches
    )
```

### 状态机识别伪代码

```python
def _identify_state_machines(self) -> List[StateTransition]:
    # 1. 识别状态信号 (命名规则)
    state_signals = [
        sig for sig in self.graph.nodes()
        if self._is_state_signal(sig)
    ]
    
    # 2. 提取状态转换 (case 语句)
    transitions = []
    for stmt in self._stmt_visitor.statements:
        if self._is_state_transition_case(stmt):
            transitions.append(StateTransition(
                current_state=stmt.lhs_signal,
                next_state=stmt.rhs_signals,
                condition=stmt.condition
            ))
    
    return transitions
```

---

## 五、ControlFlow 与 DataFlow 的融合

### 融合架构

```
DataFlowResult
├── paths: List[DataFlowPath]
│       └── segments: List[DataFlowSegment]
│               ├── from/to
│               ├── driver: SignalResult
│               ├── condition: ConditionInfo  ← ControlFlow 提供
│               └── timing: str
├── timing_analysis: TimingAnalysisResult
└── control_flow: ControlFlowResult  ← 融合

ControlFlowResult
├── conditions: List[ConditionInfo]
├── path_conditions: Dict[str, List[ConditionInfo]]
├── state_transitions: List[StateTransition]
├── control_dependencies: Dict[str, List[str]]
└── branch_coverage: float
```

### 融合方式

```python
class DataFlowAnalyzer:
    def __init__(self, graph, adapter):
        self.graph = graph
        self._control_flow_analyzer = ControlFlowAnalyzer(graph, adapter)
    
    def analyze(self, from_signal, to_signal) -> DataFlowResult:
        # 1. 获取 DataFlow
        dataflow = self._build_dataflow(from_signal, to_signal)
        
        # 2. 获取 ControlFlow
        control_flow = self._control_flow_analyzer.analyze()
        
        # 3. 融合
        dataflow.control_flow = control_flow
        
        # 4. 为每个 segment 填充 condition
        for segment in dataflow.paths[0].segments:
            segment.condition = control_flow.conditions.get(segment.to_signal)
        
        return dataflow
```

---

## 六、结论

**ControlFlow 需要新增实现**:

| 组件 | 来源 | 状态 |
|------|------|------|
| TraceEdge.condition | graph_builder.py | ✅ 已有 |
| SignalExpressionVisitor.extract() | visitors | ✅ 已有 |
| ConditionInfo 结构 | 新增 | ❌ |
| 分支覆盖分析 | 新增 | ❌ |
| StateTransition 图 | 新增 | ❌ |
| 控制依赖链 | 新增 | ❌ |
| ControlFlowResult | 新增 (dataflow_models.py) | ❌ |
| ControlFlowAnalyzer | 新增 | ❌ |

**可以与 DataFlowAnalyzer 独立实现，也可以融合**:
- 独立: DataFlowAnalyzer 只做路径搜索
- 融合: DataFlowResult.control_flow 包含 ControlFlowResult

---

## 七、文档索引

| 文档 | 内容 |
|------|------|
| `CONTROL_FLOW_ANALYSIS.md` | ControlFlow 详细设计 |
| `FINAL_SCHEMA_DECISION.md` | DataFlow + ControlFlow 架构决定 |
| `IMPLEMENTATION_RELATION.md` | 源代码与 DataFlow 关系 |
| `IMPLEMENTATION_RELATION_CONTROL_FLOW.md` | 本文: 源代码与 ControlFlow 关系 |