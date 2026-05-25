# 控制流分析架构提案

> 创建时间: 2026-05-24
> 状态: 提案阶段 (DataFlow 已实现，ControlFlow 待实现)
> 相关文档: `DATAFLOW_ANALYSIS_ARCHITECTURE.md`, `ARCHITECTURE_COMPARISON.md`

---

## 一、控制流 vs 数据流 - 基本区别

| 维度 | 数据流 (Data Flow) | 控制流 (Control Flow) |
|------|-------------------|---------------------|
| 关注点 | 信号如何传递 | 逻辑执行顺序和条件 |
| 核心问题 | A → B → C 的路径是什么？ | 在什么条件下数据流动？ |
| 答案 | 管道深度、延迟、驱动关系 | if/case 条件、分支覆盖、状态机 |
| 典型输出 | DataFlowResult | ControlFlowResult |

```
数据流:  data_in → stage1 → stage2 → data_out
控制流:  if (en) stage1 <= data_in; if (valid) stage2 <= stage1;
完整分析: en && valid 时数据才流动
```

---

## 二、典型场景

### 2.1 条件使能分析

```systemverilog
always_ff @(posedge clk) begin
    if (en) q <= d;
end
```

**控制流问题**:
- en 为真时数据流动
- en 为假时 q 保持
- en 的来源是什么？

### 2.2 多路选择分析

```systemverilog
always_comb begin
    case (sel)
        0: out = a;
        1: out = b;
        default: out = 0;
    endcase
end
```

**控制流问题**:
- sel=0/1/default 时的数据路径
- 条件覆盖是否完整？
- default 是否必要？

### 2.3 状态机分析

```systemverilog
always_ff @(posedge clk) begin
    case (state)
        IDLE: if (start) state <= RUN;
        RUN: if (done) state <= IDLE;
        default: state <= IDLE;
    endcase
end
```

**控制流问题**:
- 状态转换条件
- 状态覆盖路径
- default 状态是否必要？

### 2.4 控制依赖链

```systemverilog
if (a && b) q <= d;
```

**控制流问题**:
- a 和 b 的控制关系
- 哪个是主要使能信号？
- 控制依赖链: a → en, b → en, en → q

---

## 三、现有系统支持

### 3.1 已有能力

| 组件 | 支持的控制流功能 |
|------|-----------------|
| SignalExpressionVisitor | 条件表达式信号提取 |
| StatementCollectorVisitor | if/case/conditional 语句收集 |
| TraceEdge.condition | 边的条件信息 |

### 3.2 缺失能力

| 缺失 | 影响 |
|------|------|
| 条件分支完整路径 (if → else) | 无法分析完整条件覆盖 |
| 条件覆盖分析 | 无法知道哪些分支没覆盖 |
| 状态机状态转换图 | 无法分析状态机控制流 |
| 控制流与数据流关联 | 数据流不知道执行条件 |

---

## 四、控制流分析的数据结构

### 4.1 ConditionInfo (条件信息)

```python
@dataclass
class ConditionInfo:
    """条件信息"""
    
    # 基本信息
    kind: str               # 'if', 'case', 'conditional_op'
    expr: str               # 条件表达式原文
    signals: List[str]       # 条件涉及的信号
    
    # 分支信息
    true_branch: str        # 为真时的值/语句
    false_branch: Optional[str]  # 为假时的值/语句 (if)
    branches: Optional[List[str]]  # case 分支列表
    
    # 覆盖信息
    is_covered: bool = False
    coverage_percentage: float = 0.0
    
    # 来源信息
    source_file: str = ""
    source_line: int = 0
    block_kind: str = ""     # 'always_ff', 'always_comb', 'assign'
```

### 4.2 StateTransition (状态转换)

```python
@dataclass
class StateTransition:
    """状态机状态转换"""
    
    from_state: str          # 源状态
    to_state: str            # 目标状态
    condition: str           # 转换条件
    signals: List[str]      # 条件涉及的信号
    
    # 覆盖信息
    is_covered: bool = False
    transition_probability: float = 0.0
```

### 4.3 ControlFlowResult (控制流结果)

```python
@dataclass
class ControlFlowResult:
    """控制流分析结果"""
    
    from_signal: str
    to_signal: str
    
    # 控制条件
    conditions: List[ConditionInfo]  # 路径中的所有条件
    
    # 路径条件
    path_conditions: List[str]  # 路径条件表达式列表
    combined_condition: Optional[str]  # 组合条件 (A && B && ...)
    
    # 分支分析
    branches_analyzed: List[str]   # 已分析的分支
    branches_missing: List[str]   # 未覆盖的分支
    branch_coverage: float = 0.0  # 分支覆盖率
    
    # 状态机 (如果有)
    state_transitions: List[StateTransition] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    
    # 控制依赖
    control_dependencies: Dict[str, List[str]] = field(default_factory=dict)
    # {信号: [控制它的条件信号]}
    
    # 便捷属性
    @property
    def is_fully_covered(self) -> bool:
        return self.branch_coverage >= 1.0
    
    @property
    def has_state_machine(self) -> bool:
        return len(self.states) > 0
```

### 4.4 DataFlowResult 扩展 (融合控制流)

```python
@dataclass
class DataFlowResult:
    # ... 现有字段 ...
    
    # 控制流融合 (新增)
    control_flow: Optional[ControlFlowResult] = None
    
    # 便捷属性
    @property
    def all_conditions(self) -> List[ConditionInfo]:
        """所有条件 (从 control_flow 或 all_conditions)"""
        if self.control_flow:
            return self.control_flow.conditions
        return self._all_conditions
    
    @property
    def enable_conditions(self) -> List[str]:
        """使能条件列表"""
        return [c.expr for c in self.all_conditions if c.kind == 'if']
    
    @property
    def data_flow_when(self) -> str:
        """数据流成立的条件"""
        conditions = self.enable_conditions
        if not conditions:
            return "always"
        return " && ".join(f"({c})" for c in conditions)
```

---

## 五、与数据流分析的融合

### 5.1 完整分析 = 数据流 + 控制流

```
完整分析报告:
    ├── 数据流
    │   ├── path: data_in → stage1 → stage2 → data_out
    │   ├── latency: 2 cycles
    │   └── timing: @posedge clk
    │
    └── 控制流
        ├── conditions: [en, valid]
        ├── data_flow_when: (en) && (valid)
        ├── branch_coverage: 75%
        └── control_dependencies: {en: [], valid: [], stage1: [en], stage2: [valid]}
```

### 5.2 使用示例

```python
class DataFlowAnalyzer:
    def analyze(self, from_signal: str, to_signal: str) -> DataFlowResult:
        # 1. 数据流分析
        result = self._analyze_data_flow(from_signal, to_signal)
        
        # 2. 控制流分析 (融合)
        result.control_flow = self._analyze_control_flow(result.paths)
        
        # 3. 关联分析
        result.data_flow_when = self._compute_enable_conditions(result)
        
        return result

# 使用
analyzer = DataFlowAnalyzer(graph, adapter)
result = analyzer.analyze('data_in', 'data_out')

print(f"Path: {result.paths[0]}")
print(f"Latency: {result.latency_cycles} cycles")
print(f"Data flows when: {result.data_flow_when}")
# 输出: Data flows when: (en) && (valid)
```

---

## 六、实现优先级

### P1: 基础控制流

1. **ConditionInfo 数据类**
2. **ControlFlowResult 数据类**
3. **条件提取** (从 StatementCollectorVisitor)
4. **条件信号提取** (复用 SignalExpressionVisitor)

### P2: 分支分析

1. **分支覆盖分析**
2. **if/else 分支配对**
3. **case 分支完整性**

### P3: 状态机分析

1. **StateTransition 数据类**
2. **状态机识别** (从 case(state) 模式)
3. **状态转换图构建**

### P4: 控制依赖链

1. **控制依赖关系图**
2. **enable 条件传播**
3. **关键控制信号识别**

---

## 七、与现有组件的关系

| 组件 | 控制流分析中的角色 |
|------|-------------------|
| StatementCollectorVisitor | 条件语句来源 |
| SignalExpressionVisitor.extract() | 条件信号提取 |
| TraceEdge.condition | 边条件信息 |
| ClockDomainTracer | 状态机状态分析复用 |
| DataFlowResult | 融合控制流结果 |

---

## 八、文档索引

| 文档 | 内容 |
|------|------|
| `DATAFLOW_ANALYSIS_ARCHITECTURE.md` | 数据流分析架构 |
| `ARCHITECTURE_COMPARISON.md` | 架构对照分析 |
| `SCHEMA_COMPARISON.md` | Schema 对照分析 |
| `CONTROL_FLOW_ANALYSIS.md` | 本文: 控制流分析架构 |

---

## 九、瑞通系统价值

| 场景 | 价值 |
|------|------|
| 验证问题生成 | "当 en=0 时数据是否保持？" |
| 覆盖分析 | "哪些分支没覆盖？" |
| 故障诊断 | "数据流断点的控制原因" |
| 状态机分析 | "状态转换条件和路径" |
| 条件传播 | "关键使能信号识别" |