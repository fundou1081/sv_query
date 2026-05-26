# ControlFlow 控制流分析功能设计

> 创建时间: 2026-05-26
> 更新日期: 2026-05-26
> 状态: 设计阶段
> 项目路径: /Users/fundou/my_dv_proj/sv_query

---

## 一、设计目标

ControlFlow 分析的核心价值：

| 关注点 | 说明 |
|--------|------|
| **控制条件提取** | 数据在什么条件下流动 |
| **死锁检测** | 状态机是否会卡死（无法到达某状态） |
| **矛盾条件** | 是否有永远无法满足的条件 |
| **优先级符合Spec** | 条件优先级是否符合规格描述 |

---

## 二、核心设计思想

### 2.1 交叉定位

不同于传统的模块级或变量级分析，采用**交叉定位**方式：

> 找到"控制变量操作数据变量"的代码块

```
分析起点: 一对 (控制变量, 数据变量)
    └── "en 控制 q"

目标: 定位同时包含控制变量和数据变量的控制块
    └── if (en) q <= d;  ← 这个块同时有 en 和 q
```

### 2.3 与 DataFlow 的关系

| 层级 | 职责 |
|------|------|
| **DataFlow Graph** | 底层数据，SignalGraph 提供边/节点信息 |
| **ControlFlow** | 上层组装，独立于 DataFlow |

```
┌─────────────────────────────────────────────────────────┐
│                    ControlFlow Layer                    │
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌───────────┐  │
│  │ ControlFlow │    │ ControlFlow │    │ Z3 Solver │  │
│  │    Graph     │ ←→ │   Analyzer  │ ←→ │           │  │
│  └─────────────┘    └─────────────┘    └───────────┘  │
│         ↑                  ↑                            │
│         │                  │                           │
│         └──────────────────┼───────────────────────────┘
│                            │
│                            ↓
│         ┌─────────────────────────────────┐
│         │      SignalGraph (已有)          │
│         │  提供边/节点语义信息              │
│         └─────────────────────────────────┘
```

---

## 三、API 设计

### 3.1 方式 1: 指定控制变量 + 数据变量

```python
class ControlFlowAnalyzer:
    def analyze(
        self,
        control_var: str,      # 控制变量 (en)
        data_var: str,          # 数据变量 (q)
        module: str = None,
    ) -> ControlFlowResult:
        """
        分析 control_var 如何控制 data_var 的数据流
        """
```

**示例**:
```python
# en 如何控制 q 的值
result = analyzer.analyze(control_var="en", data_var="q")
```

### 3.2 方式 2: 批量查找控制块

```python
class ControlFlowAnalyzer:
    def find_control_blocks(
        self,
        control_vars: List[str],    # ["en", "valid"]
        data_vars: List[str],        # ["q", "data_out"]
        module: str = None,
    ) -> List[ControlBlock]:
        """
        找到同时包含控制变量和数据变量的代码块
        """
```

**示例**:
```python
blocks = analyzer.find_control_blocks(
    control_vars=["en", "valid"],
    data_vars=["q", "data_out"],
    module="top"
)
```

### 3.3 DataFlow 集成触发

```python
# DataFlow 分析时自动触发 ControlFlow
df_result = dfg.analyze("data_in", "data_out")
# DataFlow 发现条件变量后，自动提取并触发 ControlFlow
cf_result = df_result.control_flow
```

---

## 四、核心数据结构

### 4.1 ControlBlock

```python
@dataclass
class ControlBlock:
    """控制块 - 同时包含控制变量和数据变量"""
    
    # 位置
    file: str
    line: int
    column: int
    end_line: int
    
    # 控制信息
    condition_expr: str           # "en && valid"
    control_vars: List[str]       # ["en", "valid"]
    
    # 数据信息
    data_vars: List[str]          # ["q", "data_out"]
    data_stmts: List[str]         # ["q <= d", "data_out <= src"]
    
    # 块的 AST 节点
    ast_node: Any
    
    # 块类型
    kind: str                     # 'if', 'case', 'ternary', 'always_ff', 'always_comb'
    
    # 分支信息 (if/case)
    branches: List[Branch] = field(default_factory=list)
    
    # 嵌套的子块
    nested_blocks: List['ControlBlock'] = field(default_factory=list)
```

### 4.2 ControlFlowNodeKind

```python
class ControlFlowNodeKind(Enum):
    """控制流节点类型"""
    
    # 条件节点
    CONDITION = auto()          # if/case/三元条件
    CONDITION_TRUE = auto()     # if 的 then 分支
    CONDITION_FALSE = auto()    # if 的 else 分支
    CONDITION_DEFAULT = auto()  # case 的 default
    
    # 分支节点
    CASE_ITEM = auto()          # case 的某个项
    
    # 状态节点
    STATE = auto()              # 状态机状态
    STATE_ENTRY = auto()        # 进入状态
    STATE_EXIT = auto()         # 退出状态
    
    # 合并节点
    MERGE = auto()              # if/case 后的汇合
    
    # 块节点
    BLOCK = auto()              # 代码块
    SEQUENCE = auto()           # 顺序执行
```

### 4.3 ControlFlowEdgeKind

```python
class ControlFlowEdgeKind(Enum):
    """控制流边类型"""
    
    # 条件分支
    COND_TRUE = auto()          # 条件为真时的边
    COND_FALSE = auto()         # 条件为假时的边
    
    # case 分支
    CASE_MATCH = auto()         # case 匹配某值
    CASE_DEFAULT = auto()        # case default
    
    # 状态转换
    STATE_TRANSITION = auto()   # 状态转换
    
    # 执行顺序
    SEQUENCE = auto()           # 顺序执行
    FALL_THROUGH = auto()        # 穿透执行（无 break）
```

### 4.4 ControlFlowNode

```python
@dataclass
class ControlFlowNode:
    """控制流节点"""
    
    id: str                    # 唯一 ID: "module:line:col:kind"
    kind: ControlFlowNodeKind
    name: str                   # 可读名称: "if (en)", "state=IDLE"
    
    # 位置
    file: str
    line: int
    column: int
    
    # 条件信息（如果是 CONDITION 节点）
    condition_expr: Optional[str] = None    # "en && valid"
    condition_vars: List[str] = field(default_factory=list)  # ["en", "valid"]
    
    # 状态信息（如果是 STATE 节点）
    state_value: Optional[str] = None       # "IDLE"
    
    # case 信息（如果是 CASE_ITEM 节点）
    case_value: Optional[str] = None       # "0", "default"
    
    # 关联的 AST 节点
    ast_node: Optional[Any] = None
```

### 4.5 ControlFlowEdge

```python
@dataclass
class ControlFlowEdge:
    """控制流边"""
    
    id: str
    kind: ControlFlowEdgeKind
    
    # 源节点和目标节点
    from_node: str              # 源节点 ID
    to_node: str                # 目标节点 ID
    
    # 边条件（条件分支边）
    condition_expr: Optional[str] = None   # "en", "sel == 0"
    
    # 优先级（case/if 优先级）
    priority: int = 0
    
    # AST 信息
    ast_node: Optional[Any] = None
```

### 4.6 ControlFlowResult

```python
class ControlFlowResult:
    """控制流分析结果"""
    
    # 输入
    control_var: str              # "en"
    data_var: str                 # "q"
    
    # 控制块信息
    control_block: ControlBlock
    
    # 条件分析
    condition_expr: str           # "en && valid"
    condition_vars: List[str]     # ["en", "valid"]
    condition_sources: Dict[str, str]  # {"en": "top.u_ctrl.en"}
    
    # 分支分析
    branches: List[BranchResult]
    
    # 数据流条件
    data_flow_when: str           # "en == 1"
    
    # Z3 分析 (如果有矛盾条件)
    z3_analysis: Optional[Z3Result]
    
    # 警告
    warnings: List[LintWarning]
    
    # === 死锁/可达性 ===
    state_machine_analysis: Optional[StateMachineAnalysis]
    
    # === 矛盾条件 ===
    contradictions: List[Contradiction]
    
    # === 优先级分析 ===
    priority_analysis: Optional[PriorityAnalysis]
```

### 4.7 BranchResult

```python
@dataclass
class BranchResult:
    """分支结果"""
    
    condition: str               # 分支条件 "en", "sel == 0"
    action: str                  # 执行的动作 "q <= d"
    covered: bool                # 是否覆盖
    signal_sources: List[str]    # 信号的来源
```

### 4.8 StateMachineAnalysis

```python
@dataclass
class StateMachineAnalysis:
    """状态机分析结果"""
    
    name: str                   # "top.state"
    
    # 死锁检测
    has_deadlock: bool
    deadlock_states: List[str]   # 死锁的状态列表
    deadlock_reason: str        # "missing default branch"
    
    # 无法到达的状态
    unreachable_states: List[StateTransition]
    
    # 所有状态
    all_states: List[str]
    reachable_states: List[str]  # 可达的
```

### 4.9 Contradiction

```python
@dataclass
class Contradiction:
    """矛盾条件"""
    
    type: str              # 'impossible_condition', 'duplicate_case'
    expr: str              # "en && !en"
    reason: str            # "en && !en is always false"
    location: Location     # file, line, column
    severity: str          # 'error', 'warning'
    suggestion: str        # "Remove impossible condition"
```

### 4.10 LintWarning

```python
@dataclass
class LintWarning:
    """代码审查警告"""
    
    severity: str               # 'error', 'warning', 'info'
    rule: str                  # 'LATCH_WARNING', 'INCOMPLETE_CASE'
    
    file: str
    line: int
    column: int
    
    message: str               # "if without else may cause latch"
    suggestion: str             # "Add else branch with default value"
```

---

## 五、工作流程

```
analyze(control_var="en", data_var="q")
    │
    ├─→ 1. 在 SignalGraph 中查找 en 的相关边
    │    ├─→ en 作为 DRIVER 边
    │    └─→ en 作为 condition 边
    │
    ├─→ 2. 在 SignalGraph 中查找 q 的相关边
    │    └─→ q 作为 DRIVER/LATCH 边
    │
    ├─→ 3. 交叉定位: 找到 en 和 q 的交集
    │    └─→ if (en) q <= ...; 这条语句
    │
    ├─→ 4. 提取控制流信息
    │    ├─→ 条件表达式: "en"
    │    ├─→ 分支: en=1 → q=d, en=0 → q=保持
    │    └─→ 依赖链: en 的来源
    │
    └─→ 5. 返回 ControlFlowResult
         ├─ control_var: "en"
         ├─ data_var: "q"
         ├─ control_block: if (en) q <= d;
         └─ branches: [BranchResult(cond="en", action="q=d"), ...]
```

---

## 六、Z3 集成

### 6.1 Z3Solver

```python
class Z3Solver:
    """用 Z3 进行条件求解"""
    
    def check_satisfiability(self, conditions: List[str]) -> Z3Result:
        """
        检查条件是否可满足
        
        en && valid  # → satisfiable
        en && !en   # → unsatisfiable (矛盾)
        """
        
    def find_deadlock_states(self, state_var, transitions) -> List[str]:
        """
        找出死锁状态：没有后继的状态
        """
        
    def find_unreachable_states(self, state_var, transitions, init_state) -> List[str]:
        """
        找出不可达状态
        """
```

### 6.2 分析场景

| 场景 | Z3 用途 |
|------|---------|
| 死锁检测 | 检查每个状态是否有后继转换 |
| 矛盾条件 | `en && !en` 永远为 false |
| 不可达状态 | 从初始状态可达的集合 |
| 条件优先级 | spec 优先级 vs code 优先级 |

---

## 七、Spec 驱动分析

### 7.1 Spec 格式

```python
spec = """
Control signals:
- en: enable data flow
- valid: data is valid
- state: FSM state

Transitions:
- IDLE → RUN when en && valid
- RUN → DONE when done

State transition priority:
1. start > stop
2. idle > run
"""
```

### 7.2 PriorityAnalysis

```python
class PriorityAnalysis:
    # 从 spec 解析的优先级
    spec_priorities: List[Tuple[str, str]]
    
    # 代码中的实际优先级
    code_priorities: List[Tuple[str, str]]
    
    # 比对结果
    matches: bool
    mismatches: List[Mismatch]
```

---

## 八、文件结构

```
src/trace/core/
├── graph/
│   ├── __init__.py
│   ├── dataflow.py              # DataFlow 图 (已有)
│   ├── controlflow.py            # ControlFlow 图 (新建)
│   └── controlflow_models.py     # 控制流数据模型 (新建)
│
├── analyzer/
│   ├── __init__.py
│   ├── dataflow_analyzer.py      # DataFlow 分析 (已有)
│   ├── controlflow_analyzer.py   # ControlFlow 分析 (新建)
│   └── z3_analyzer.py            # Z3 求解器 (新建)
│
└── bridge/
    └── flow_bridge.py            # DataFlow ↔ ControlFlow 桥接 (新建)
```

---

## 九、输出示例

### 9.1 分析单个控制-数据对

```python
result = analyzer.analyze(control_var="en", data_var="q")

# 打印
Control Flow Analysis: en → q

Control Block:
  File: top.sv:10
  Code: if (en) q <= d; else q <= 0;
  
Condition: en
  Expression: en
  Source: top.en (from top.u_ctrl)
  
Branches:
  ├─ when en=1: q = d       ✅
  └─ when en=0: q = 0       ⚠️ latch risk (q holds previous value)

Data Flow When: en == 1

Warnings:
  ⚠️ LATCH: q 在 en=0 时保持原值，可能导致 latch
    Suggestion: 明确初始化 q
```

### 9.2 批量查找控制块

```python
blocks = analyzer.find_control_blocks(
    control_vars=["en", "valid"],
    data_vars=["q", "data_out"],
    module="top"
)

# 返回
# [
#   ControlBlock(
#     file="top.sv",
#     line=10,
#     condition="en",
#     data_vars=["q"],
#     stmt="if (en) q <= d;"
#   ),
#   ControlBlock(
#     file="top.sv",
#     line=15,
#     condition="en && valid",
#     data_vars=["data_out"],
#     stmt="if (en && valid) data_out <= src;"
#   ),
# ]
```

---

## 十、实现优先级

### Phase 1: 基础能力

1. [ ] ControlFlow 数据模型 (ControlBlock, ControlFlowResult)
2. [ ] 交叉定位: `find_control_blocks()`
3. [ ] 条件提取和分支分析
4. [ ] Lint 警告 (if without else, case without default)

### Phase 2: 状态机分析

1. [ ] 状态机识别 (case(state) 模式)
2. [ ] 死锁检测
3. [ ] 不可达状态分析
4. [ ] Z3 集成

### Phase 3: Spec 驱动

1. [ ] Spec 解析
2. [ ] 优先级分析
3. [ ] Agent 集成

---

## 十一、相关文档

| 文档 | 说明 |
|------|------|
| `DATAFLOW_ANALYSIS_ARCHITECTURE.md` | DataFlow 分析架构 |
| `ARCHITECTURE.md` | 整体架构文档 |
| `PENDING_FEATURES.md` | 待实现功能清单 |
| `CONTROL_FLOW_ANALYSIS.md` | 旧版控制流架构提案 (参考) |

---

## 更新日志

| 日期 | 操作 |
|------|------|
| 2026-05-26 | 创建文档，基于交叉定位设计思想 |