# sv_query 架构文档

> 版本: 1.0
> 更新日期: 2026-05-26
> 项目路径: /Users/fundou/my_dv_proj/sv_query

---

## 一、架构概览

sv_query 是一个基于 **pyslang AST** 的 SystemVerilog 信号追踪查询引擎，采用分层架构设计：

```
┌─────────────────────────────────────────────────────────────┐
│                    Query Layer (API)                       │
│  UnifiedTracer - 统一入口，协调各组件                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Builder Layer                            │
│  GraphBuilder (Module) / ClassGraphBuilder (Class)         │
│  BitSelectHandler / ExpressionBuilder                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Graph Layer                             │
│  SignalGraph (NetworkX) ←─ DataFlowGraph ←─ ModuleInstance │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Visitor Layer                           │
│  SignalExpressionVisitor / StatementCollectorVisitor      │
│  ConstraintVisitor / ConstraintVisitor                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    pyslang AST (Semantic)                  │
│  Compilation + getRoot() - 唯一可信数据源                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、核心组件

### 2.1 入口层 - UnifiedTracer

**文件**: `src/trace/unified_tracer.py`

```python
class UnifiedTracer:
    """统一追踪入口"""
    
    def build_graph(self, ...) -> SignalGraph
    def trace_drivers(self, signal, depth=None) -> SignalChain
    def trace_loads(self, signal, depth=None) -> SignalChain
    def trace_clock_domain(self, signal) -> ClockDomainTrace
    def get_module(self, module_name) -> ModuleTracer
    def analyze_dataflow(self, from_signal, to_signal) -> DataFlowResult
```

**职责**:
- 协调各组件
- 封装 Query API
- 管理编译和图构建生命周期

### 2.2 构建层 - GraphBuilder

**文件**: `src/trace/core/graph_builder.py` (2675 行)

```python
class GraphBuilder:
    """Module 级信号图构建器"""
    
    def build(self, ...) -> ExtractorResult
    
class DriverExtractor:
    """驱动关系提取"""
    
class SubroutineExpander:
    """函数/任务内联展开"""
```

**职责**:
- 遍历 Module/Interface/Program 的 AST
- 提取 Signal 节点 (PORT_IN, PORT_OUT, WIRE, REG, etc.)
- 提取驱动边 (DRIVER, CLOCK, RESET, CONNECTION)
- 处理连续赋值、时序逻辑、组合逻辑
- 处理实例化连接
- **展开函数/任务内的条件分支 (if/else/case/return/三元)**

**核心 Visitor**:
- `SignalExpressionVisitor` - 表达式 → 信号名提取
- `StatementCollectorVisitor` - 语句 → 上下文提取

### 2.3 SubroutineExpander - 函数内联展开

**文件**: `src/trace/core/builder/subroutine_expander.py` (750+ 行)

```python
class SubroutineExpander:
    """函数/任务内联展开器"""
    
    def expand(call_site, ctx) -> ExpansionResult
    def has_conditional_branches(func_def) -> bool
    def _collect_branches(body, func_name, branches)
```

**展开支持**:
- `if/else` 条件分支
- `case/endcase` 多路分支
- `return` 语句
- 三元运算符 `cond ? if_true : if_false`

**参数映射**:
- 实参名 → 形参名 替换
- 条件字符串构造使用映射后的参数名

---

### 2.3 Class 构建层 - ClassGraphBuilder

**文件**: `src/trace/core/class_graph_builder.py` (738 行)

```python
class ClassGraphBuilder:
    """Class & Constraint 子图构建器"""
    
    def build(self, graph: SignalGraph) -> ClassBuilderResult
```

**职责**:
- 遍历所有 ClassDeclaration
- 创建 CLASS、CLASS_PROPERTY 节点
- 创建 CONSTRAINT_BLOCK 及子节点
- 创建 CONSTRAINS、HAS_* 等边
- 建立 ClassHierarchy（extends 链）

**核心 Visitor**:
- `ConstraintVisitor` - 约束表达式解析

---

### 2.4 图层 - SignalGraph

**文件**: `src/trace/core/graph/models.py` (457 行)

```python
class NodeKind(Enum):
    # 信号节点
    SIGNAL, WIRE, REG, PORT_IN, PORT_OUT, PARAM, CONST
    INSTANTIATED_MODULE, GENERATE_BLOCK
    
    # Class 节点
    CLASS, CLASS_INSTANCE, CLASS_PROPERTY
    CONSTRAINT_BLOCK, CONSTRAINT_EXPR, CONSTRAINT_IF, ...
    EXPRESSION, FUNCTION_CALL

class EdgeKind(Enum):
    # 核心边
    DRIVER, CLOCK, RESET, CONNECTION, BIT_SELECT
    
    # Class 边
    CONSTRAINS, HAS_CONDITION, HAS_CONSEQUENT, HAS_LHS, HAS_RHS
    HAS_MEMBER, IS_INSTANCE_OF, SUPER_CALL, CONTAINS_MEMBER
```

**核心数据结构**:

```python
@dataclass
class TraceNode:
    id: str              # "top.clk_i"
    name: str            # "clk_i"
    module: str           # "top"
    kind: NodeKind
    width: Tuple[int, int]  # (31, 0)
    bit_range: Optional[str]  # "[3:0]"
    parent: Optional[str]     # 位选父节点
    parent_bit_start/end: int # 位选范围

@dataclass
class TraceEdge:
    src: str
    dst: str
    kind: EdgeKind
    assign_type: str      # continuous/always_ff/always_comb
    condition: str        # 条件表达式
    clock_domain: str    # 时钟域
    expression: str      # 驱动表达式
    confidence: str      # high/medium/low
```

---

### 2.5 DataFlow 层 - DataFlowGraph

**文件**: `src/trace/core/graph/dataflow.py` (707 行)

```python
class DataFlowGraph:
    """信号间数据流分析"""
    
    def analyze(self, from_signal, to_signal, max_paths=100) -> DataFlowResult
    def get_segment(self, from_signal, to_signal) -> DataFlowSegment
```

**职责**:
- 路径搜索 (nx.all_simple_paths)
- BIT_SELECT 边处理 (byte_data[3:0] → byte_data)
- Struct 成员展开 (pkt1.data → pkt2.data)
- 时钟域分析
- 条件判断提取
- 中间信号收集

**核心数据结构**:

```python
@dataclass
class DataFlowSegment:
    from_signal: str
    to_signal: str
    driver: Optional[str]
    condition: Optional[str]
    timing: Optional[str]
    assign_type: str
    distance: int

@dataclass
class DataFlowPath:
    path_id: int
    segments: List[DataFlowSegment]
    distance: int
    has_conditional: bool

@dataclass
class DataFlowResult:
    from_signal: str
    to_signal: str
    paths: List[DataFlowPath]
    is_reachable: bool
    paths_count: int
    intermediate_signals: Set[str]
    clock_domain: Optional[str]
    timing_risk: str  # safe/low/medium/high/critical
```

---

### 2.6 模块实例层 - ModuleInstanceGraph

**文件**: `src/trace/core/module_instance_graph.py` (1039 行)

```python
class ModuleInstanceGraph:
    """模块实例层级图"""
    
    def build(self, trees) -> None
    def get_instance(self, path) -> ModuleInstanceNode
    def get_internal_signal(self, port_path) -> str
    def get_child_instances(self, parent_id) -> List[ModuleInstanceNode]
```

**职责**:
- 管理模块实例层级 (top.u_tb, top.u_dut)
- 维护端口到内部信号的映射
- 支持跨模块边界追踪

---

### 2.7 Visitor 层

#### SignalExpressionVisitor

**文件**: `src/trace/core/visitors/signal_expression_visitor.py` (7064 行)

```python
class SignalExpressionVisitor:
    """表达式 → 信号名提取"""
    
    def visit(self, node) -> Optional[str]
    def get_all_signals(self, node) -> List[str]
    def extract(self, node) -> SignalResult
```

**特性**:
- 使用 `@on` 装饰器注册 538 个 handler
- 支持双接口 (visit + get_all_signals)
- 覆盖大部分 ExpressionKind

#### StatementCollectorVisitor

**文件**: `src/trace/core/visitors/statement_collector_visitor.py`

```python
class StatementCollectorVisitor:
    """语句收集与上下文提取"""
    
    def collect(self, stmt) -> List[StatementInfo]
```

#### ConstraintVisitor

**文件**: `src/trace/core/visitors/constraint_visitor.py`

```python
class ConstraintVisitor:
    """约束表达式解析"""
    
    def visit_constraint(self, constraint) -> ConstraintResult
```

---

## 三、Visitor 模式详解

### 3.1 Visitor 概览

| Visitor | 文件 | Handler 数 | 主要职责 |
|---------|------|------------|----------|
| `SignalExpressionVisitor` | `visitors/signal_expression_visitor.py` | 538 @on | AST → 信号名 |
| `StatementCollectorVisitor` | `visitors/statement_collector_visitor.py` | ~50 | 语句 + 语义上下文 |
| `ConstraintVisitor` | `visitors/constraint_visitor.py` | - | 约束表达式解析 |
| `BaseVisitor` | `visitors/base_visitor.py` | - | 基类 |

### 3.2 使用模式

#### 模式 1: 在 GraphBuilder 中委托调用

```python
# graph_builder.py
class DriverExtractor:
    def __init__(self, adapter):
        self._signal_visitor = SignalExpressionVisitor(adapter)
        self._stmt_visitor = StatementCollectorVisitor(adapter)

    def _get_signal(self, signal) -> Optional[str]:
        # 委托给 Visitor，不直接解析
        return self._signal_visitor.visit(signal)

    def _get_all_signals(self, signal) -> List[str]:
        return self._signal_visitor.get_all_signals(signal)
```

**职责分离**:
- **GraphBuilder**: 遍历 AST，创建 TraceNode/TraceEdge
- **Visitor**: 解析表达式中的信号名

#### 模式 2: 在 ClassGraphBuilder 中解析约束变量

```python
# class_graph_builder.py
class ClassGraphBuilder:
    def __init__(self, adapter):
        self._cv = ConstraintVisitor()


    def _build_constraint(self, item, ...):
        self._cv.reset()
        self._cv.visit(item)          # 解析约束
        vars = self._cv.variables     # 提取变量
```

### 3.3 SignalExpressionVisitor 工作原理

#### 双接口设计

```python
class SignalExpressionVisitor:
    def visit(self, node) -> Optional[str]:
        """单信号接口 - 返回第一个信号名"""
        ...

    def get_all_signals(self, node) -> List[str]:
        """多信号接口 - 返回所有信号名"""
        ...

    def extract(self, node) -> SignalResult:
        """统一接口 (推荐) - 返回完整结果"""
        return SignalResult(primary=..., all_signals=..., ...)
```

#### @on 装饰器注册机制

```python
@on('IdentifierName')
def visit_identifier_name(self, node):
    """处理信号引用"""
    return self._clean_name(node.symbol.name)

@on('BinaryOp')
def handle_binary_op(self, node):
    """处理二元表达式 a + b"""
    left = self.visit(node.left)
    right = self.visit(node.right)
    return f"{left} {node.op} {right}" if left and right else None
```

**注册表**: `_HANDLERS` 字典，通过 `@on('KindName')` 装饰器自动注册。

#### 示例流程

```systemverilog
assign data = a + b;
```

```python
# GraphBuilder 调用
expr_str = self._signal_visitor.visit(rhs_expr)  # → "a + b"

# 内部流程
visitor.visit(binary_op_node)
  → 获取 kind.name = 'BinaryOp'
  → 查找 _HANDLERS['BinaryOp']
  → 调用 handle_binary_op(self, node)
  → 返回 "a + b"
```

### 3.4 StatementCollectorVisitor 工作原理

#### 语义上下文收集

```python
class StatementCollectorVisitor:
    def collect(self, node, ctx=None) -> List[Tuple[Any, Dict, ItemType]]:
        """收集语句并携带语义上下文"""
        # ctx = {clock: 'clk_i', condition: 'en', reset: 'rst_n'}
```

#### 上下文栈机制

```python
# 进入 always_ff @(posedge clk)
self._ctx_stack.append({clock: 'clk_i', ...})


# 进入 if (en) 块
self._ctx_stack.append({condition: 'en', ...})


# 收集当前语句，使用合并后的上下文
current_ctx = self.current_ctx  # {clock: 'clk_i', condition: 'en', ...}
```


### 3.5 Visitor 与 GraphBuilder 的关系

```
┌─────────────────────────────────────────────────────────────┐
│                    GraphBuilder                          │
│  - 遍历 AST (Module/Interface/Program)                   │
│  - 创建 TraceNode / TraceEdge                            │
│  - 调用 Visitor 解析表达式                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
         ┌─────────────────────────────────┐
         │     SignalExpressionVisitor      │
         │  - visit() → 单信号名             │
         │  - get_all_signals() → 多信号    │
         │  - 538 个 @on handler             │
         └─────────────────────────────────┘
                              │
                              ▼
         ┌─────────────────────────────────┐
         │   StatementCollectorVisitor     │
         │  - collect() → 语句+上下文       │
         │  - 携带 clock/condition/reset    │
         └─────────────────────────────────┘
```

### 3.6 当前架构问题

| 问题 | 说明 |
|------|------|
| **双接口冗余** | visit() 和 get_all_signals() 有重复逻辑 |
| **Handler 未全利用** | 538 个 handler，但 GraphBuilder 只调用了少量 |
| **ExpressionBuilder 独立** | `expression_builder.py` 未接入 Visitor |

### 3.7 建议改进

```python
# 建议: 统一为单接口
class SignalExpressionVisitor:
    def extract(self, node) -> SignalResult:
        """唯一入口，返回完整结果"""
        return SignalResult(
            primary=self.visit(node),
            all_signals=self.get_all_signals(node),
            all_signals_unique=set(...),
            kind_name=kind_name,
            ...
        )
```

---

## 四、数据抽象详解

### 4.1 数据模型总览

| 模型 | 文件 | 类型 | 用途 |
|------|------|------|------|
| `TraceNode` | graph/models.py | @dataclass | 图节点 |
| `TraceEdge` | graph/models.py | @dataclass | 图边 |
| `DriverInfo` | graph/models.py | @dataclass | 驱动信息 |
| `SignalGraph` | graph/models.py | nx.DiGraph | 有向图容器 |
| `PortInfo` | module_instance_graph.py | @dataclass | 端口信息 |
| `ModuleInstanceNode` | module_instance_graph.py | @dataclass | 实例节点 |
| `ModuleInstanceGraph` | module_instance_graph.py | nx.DiGraph | 实例图 |
| `SignalResult` | signal_result.py | @dataclass | 表达式解析结果 |
| `DataFlowSegment` | dataflow.py | @dataclass | 数据流段 |
| `DataFlowPath` | dataflow.py | @dataclass | 数据流路径 |
| `DataFlowResult` | dataflow.py | @dataclass | 数据流结果 |

### 4.2 NodeKind 枚举 (25个)

```python
class NodeKind(Enum):
    # 信号节点 (11个)
    SIGNAL, WIRE, REG, PORT_IN, PORT_OUT, PORT_INOUT, PARAM, CONST
    INSTANTIATED_MODULE, GENERATE_BLOCK
    
    # Class 节点 (12个)
    CLASS, CLASS_INSTANCE, CLASS_PROPERTY
    CONSTRAINT_BLOCK, CONSTRAINT_EXPR, CONSTRAINT_IF, CONSTRAINT_ELSE
    CONSTRAINT_IMPLIES, CONSTRAINT_UNIQUE, CONSTRAINT_SOLVE
    CONSTRAINT_FOREACH, CONSTRAINT_RANGE
    
    # 表达式节点 (2个)
    EXPRESSION, FUNCTION_CALL
```

### 4.3 EdgeKind 枚举 (18个)


```python
class EdgeKind(Enum):
    # 核心边 (5个)
    DRIVER, CLOCK, RESET, CONNECTION, BIT_SELECT
    
    # Class 边 (13个)
    CONSTRAINS, HAS_CONDITION, HAS_CONSEQUENT, HAS_ALTERNATE
    HAS_LHS, HAS_RHS, HAS_MEMBER, HAS_LOOP_VAR
    HAS_BEFORE, HAS_AFTER, CONTAINS_MEMBER, IS_INSTANCE_OF, SUPER_CALL
```

### 4.4 核心 dataclass

#### TraceNode

```python
@dataclass
class TraceNode:
    id: str                    # "top.clk_i"
    name: str                  # "clk_i"
    module: str                 # "top"
    kind: NodeKind
    width: Tuple[int, int]     # (31, 0)
    bit_range: Optional[str]    # "[3:0]"
    parent: Optional[str]       # "top.data"
    parent_bit_start/end: int  # 位选范围
    is_clock/is_reset: bool    # 语义标记
```

#### TraceEdge

```python
@dataclass
class TraceEdge:
    src: str
    dst: str
    kind: EdgeKind
    assign_type: str = ""       # always_ff/always_comb/continuous
    condition: str = ""        # if (en)
    clock_domain: str = ""     # "clk_i"
    expression: str = ""       # "sreg_d"
```

#### DriverInfo

```python
@dataclass
class DriverInfo:
    node: TraceNode
    condition: str = ""
    clock_domain: str = ""
    assign_type: str = ""
    distance: int = 1
    
    @property
    def full_statement(self) -> str:
        """组装完整驱动语句"""
```

#### SignalResult

```python
@dataclass
class SignalResult:
    primary: Optional[str]       # 单信号名 (LHS)
    all_signals: List[str]       # 所有信号 (RHS)
    kind_name: Optional[str]      # 'BinaryOp'
    op_name: Optional[str]        # 'Add'
```

### 4.5 设计模式

| 模式 | 说明 |
|------|------|
| **dataclass** | 简化数据类定义 |
| **Enum + auto()** | 自动分配枚举值 |
| **Optional 默认值** | 避免 None 检查 |
| **field(default_factory=list)** | 避免可变默认值共享 |
| **@property 派生** | 计算属性 (如 full_statement) |
| **@classmethod 工厂** | SignalResult.single/multi/empty |


### 4.6 数据流

```
pyslang AST → GraphBuilder → SignalExpressionVisitor
  → StatementCollectorVisitor → TraceNode/TraceEdge
  → SignalGraph → DataFlowGraph.analyze()
```

### 4.7 设计问题

| 问题 | 建议 |
|------|------|
| TraceNode 过载 | 考虑继承或泛型 |
| DriverInfo 与 TraceEdge 重复 | 考虑合并 |
| BIT_SELECT 复用 (位选+struct.member) | 考虑拆分 |
| SignalResult 未被广泛使用 | 推动 extract() 统一入口 |

### 4.8 SignalResult 使用分析

#### 三接口设计

SignalExpressionVisitor 提供三个接口：

| 接口 | 返回类型 | 状态 |
|------|----------|------|
| `visit(node)` | `Optional[str]` | 旧接口，单信号 |
| `get_all_signals(node)` | `List[str]` | 旧接口，多信号 |
| `extract(node)` | `SignalResult` | **推荐** 统一入口 |

#### 实际使用情况

| 使用位置 | 接口 | 说明 |
|---------|------|------|
| SignalExpressionVisitor 内部 | `extract()` | ✅ 递归合并到父节点 |
| CLI expression 命令 | `extract()` | ✅ 使用 SignalResult |
| GraphBuilder | `visit()` / `get_all_signals()` | ❌ 未迁移到 extract() |

#### SignalResult 数据流

```
SignalExpressionVisitor.extract(node)
    ↓
┌─────────────────────────────────────┐
│ SignalResult                         │
│  - primary: 第一个信号名            │
│  - all_signals: [所有信号]           │
│  - kind_name: 'BinaryOp'             │
│  - op_name: 'Add'                    │
└─────────────────────────────────────┘
    ├─→ CLI expression 命令 ✅
    ├─→ 递归合并 (inside/min_typ_max 等) ✅
    └─→ GraphBuilder ❌ (仍用 visit/get_all)
```

#### 问题分析

| 问题 | 说明 |
|------|------|
| **GraphBuilder 未使用 extract()** | 仍调用旧接口 visit()/get_all_signals() |
| **ExtractorResult 与 SignalResult 重复** | 两个结果容器，设计冗余 |
| **extract() 推广受阻** | CLI expression 使用，但 GraphBuilder 未迁移 |

#### ExtractorResult vs SignalResult

```python
# graph_builder.py - ExtractorResult
class ExtractorResult:
    nodes: List[TraceNode]
    edges: List[TraceEdge]
    errors: List[str]
    port_to_internal: Dict[str, str]

# signal_result.py - SignalResult
class SignalResult:
    primary: Optional[str]
    all_signals: List[str]
    kind_name: Optional[str]
    op_name: Optional[str]
```

**建议统一为 SignalResult**：
```python
class SignalResult:
    nodes: List[TraceNode] = field(default_factory=list)
    edges: List[TraceEdge] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    primary: Optional[str]
    all_signals: List[str]
    kind_name: Optional[str]
    op_name: Optional[str]
```

---

### 4.9 ExtractorResult vs SignalResult 深度对比

#### 定义对比

| 属性 | ExtractorResult | SignalResult |
|------|-----------------|--------------|
| **文件** | `graph_builder.py` | `visitors/signal_result.py` |
| **职责** | Graph 构建结果 | 表达式解析结果 |
| **创建者** | DriverExtractor, LoadExtractor | SignalExpressionVisitor |
| **使用者** | GraphBuilder | GraphBuilder (调用 Visitor) |

#### 字段对比

ExtractorResult:
```python
nodes: List[TraceNode]           # 图节点
edges: List[TraceEdge]          # 图边
errors: List[str]                # 错误信息
port_to_internal: Dict[str, str]  # 端口映射
```

SignalResult:
```python
primary: Optional[str]           # 单信号名 (LHS)
all_signals: List[str]           # 所有信号 (RHS)
kind_name: Optional[str]         # 表达式类型名
op_name: Optional[str]           # 操作符名
signal_info: Dict[str, Any]      # 详细信息
source_range: Optional[tuple]    # 源码位置
```

#### 字段对比表

| 维度 | ExtractorResult | SignalResult |
|------|-----------------|--------------|
| **节点/边** | ✅ nodes, edges | ❌ 无 |
| **错误处理** | ✅ errors | ❌ 无 |
| **端口映射** | ✅ port_to_internal | ❌ 无 |
| **单信号** | ❌ 无 | ✅ primary |
| **多信号** | ❌ 无 | ✅ all_signals |
| **表达式类型** | ❌ 无 | ✅ kind_name |
| **操作符名** | ❌ 无 | ✅ op_name |
| **源码位置** | ❌ 无 | ✅ source_range |

#### 问题分析

| 问题 | 说明 |
|------|------|
| **功能重复** | 两个结果容器，但数据不共享 |
| **双接口冗余** | visit() + get_all_signals() + extract() |
| **推广受阻** | extract() 未被 GraphBuilder 使用 |

#### 重构建议

**方案 A: 扩展 ExtractorResult (推荐)**

```python
class ExtractorResult:
    # 图数据 (已有)
    nodes: List[TraceNode] = field(default_factory=list)
    edges: List[TraceEdge] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    port_to_internal: Dict[str, str] = field(default_factory=dict)
    
    # 信号数据 (新增)
    expression_result: SignalResult = None
```

**理由**:
1. ExtractorResult 是 GraphBuilder 的输出格式，已被广泛使用
2. SignalResult 作为 ExtractorResult 的字段嵌入
3. 保持 GraphBuilder 输出格式不变，易于迁移


## 五、查询 API

### 3.1 SignalTracer - 信号追踪

```python
class SignalTracer:
    def trace_drivers(self, signal_id, depth=None) -> List[DriverChain]
    def trace_loads(self, signal_id, depth=None) -> List[LoadChain]
```

### 3.2 LoadTracer - 负载追踪

```python
class LoadTracer:
    def trace_loads(self, signal_id, max_depth=None) -> List[LoadChain]
```

### 3.3 ClockDomainTracer - 时钟域追踪

```python
class ClockDomainTracer:
    def trace_clock_domain(self, signal_id) -> ClockDomainTrace
```

### 3.4 DataFlowAnalyzer - 数据流分析

```python
class DataFlowGraph:
    def analyze(self, from_signal, to_signal, max_paths=100) -> DataFlowResult
```

---

## 六、CLI 命令行工具

**文件**: `src/cli/main.py`

```bash
# 1. stats - 图统计
run_cli.py stats -f test.sv

# 2. trace - 信号追踪
run_cli.py trace fanin top.clk -f test.sv
run_cli.py trace fanout top.data -f test.sv

# 3. diff - 代码对比
run_cli.py diff old.sv new.sv

# 4. snapshot - 快照管理
run_cli.py snapshot save ...

# 5. dataflow - 数据流分析
run_cli.py dataflow analyze test.data_in test.data_out -f test.sv
```

---

## 七、技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| AST 解析 | pyslang | 语义 AST (Compilation + getRoot()) |
| 图结构 | NetworkX | 有向图 (Digraph) |
| 数据类 | dataclass | 轻量级数据结构 |
| Visitor | @on 装饰器 | 538 个 handler |
| CLI | Typer | 命令行界面 |
| 测试 | pytest | 839 测试用例 |

---

## 八、关键设计原则

| 铁律 | 说明 |
|------|------|
| **Semantic AST 强制** | 必须使用 `Compilation` + `getRoot()` |
| **位精确性** | `data[7:4]` 和 `data[3:0]` 是不同节点 |
| **原子化** | 每种语法节点类型独立处理 |
| **不可信则不输出** | 无法解析时返回 `confidence: "uncertain"` |
| **Visitor 模式** | [铁律15] 使用 Visitor 替代 if-elif 链 |
| **图即契约** | 数据结构变更必须同步更新所有消费者 |

---

## 九、文件结构

```
src/trace/
├── unified_tracer.py          # 统一入口
├── core/
│   ├── graph/
│   │   ├── models.py         # TraceNode, TraceEdge, NodeKind, EdgeKind
│   │   ├── dataflow.py       # DataFlowGraph
│   │   └── diff.py           # 图差异分析
│   ├── graph_builder.py      # Module 图构建 (2675行)
│   ├── class_graph_builder.py # Class 图构建 (738行)
│   ├── module_instance_graph.py # MIG (1039行)
│   ├── bit_select_handler.py # 位选处理
│   ├── base.py               # PyslangAdapter
│   ├── compiler.py            # 编译管理
│   ├── semantic_adapter.py    # 语义适配器
│   ├── builder/
│   │   └── subroutine_expander.py  # 函数/任务内联展开 (750+行)
│   ├── visitors/
│   │   ├── signal_expression_visitor.py  # 7064行
│   │   ├── statement_collector_visitor.py
│   │   ├── constraint_visitor.py
│   │   └── ...
│   └── query/
│       ├── signal.py         # SignalTracer
│       ├── load.py            # LoadTracer
│       ├── clock_domain.py    # ClockDomainTracer
│       └── module.py         # ModuleTracer
└── cli/
    └── commands/
        ├── trace.py
        ├── dataflow.py
        ├── diff.py
        ├── snapshot.py
        └── stats.py
```

---

## 十、测试统计 (2026-05-27)

```
Unit tests:       30 tests
Integration:     125 tests
Regression:      703 tests
─────────────────────────
Total:           996 tests
Skipped:           0 test
Failed:            0 test
```

---

## 十一、版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-26 | 1.0 | 初始架构文档 |
| 2026-05 | 0.1 | 项目启动 |

---

## 十二、相关文档

| 文档 | 说明 |
|------|------|
| `README.md` | 项目整体介绍 |
| `docs/TODO.md` | 待实现功能清单 |
| `docs/PENDING_FEATURES.md` | 待实现功能详细清单 |
| `docs/DATAFLOW_IMPLEMENTATION_PLAN.md` | DataFlow 实现方案 |
| `docs/CONTROL_FLOW_ANALYSIS.md` | ControlFlow 设计方案 |