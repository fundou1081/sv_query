# Signal Connection Graph Analysis System

**日期**: 2026-05-24  
**状态**: 需求讨论中  
**负责人**: 方浩

---

## 背景

在 IC 验证环境中，需要一个信号追踪和连接图分析系统，用于：

- 数据流分析
- 控制流分析
- Pipeline 延迟分析
- Agent Debug 接口（给一个信号，返回完整上下文）

现有 `sv_query` 项目基于 pyslang AST 实现了部分能力，现在需要基于 `pyslang.visit()` + `VisitAction.Skip` 的遍历边界控制方案重新设计/优化。

---

## 核心需求

### 1. 信号连接图 (Signal Graph)

| 节点类型 | 说明 |
|---------|------|
| `SignalNode` | 信号节点，包含 path、width、is_register 等 |
| `ConnectionEdge` | 连接边，包含 src、dst、kind、condition、latency |

**边类型**:
- `DRIVER` — 驱动关系 (assign, always_ff)
- `LOAD` — 负载关系
- `CONNECTION` — 物理连接 (wire)
- `CONDITION` — 条件控制 (if/else, generate)

### 2. 数据分析能力

#### 2.1 驱动/负载追踪

```python
# 给定信号，返回其驱动源和负载
query_drivers(signal_path) -> List[(src, edge, path)]
query_loads(signal_path) -> List[(dst, edge, path)]
```

**示例**:
```
输入: "top.u_dut.reg_data"
输出:
  - drivers: [("top.u_dut.comb_logic", DRIVER, "")]
  - loads: [("top.u_dut.out_data", DRIVER, "")]
```

#### 2.2 完整数据流追踪

```python
query_data_flow(signal_path, depth=10) -> DataFlowGraph
```

**示例**:
```
输入: "top.u_dut.data_in", depth=5
输出: "data_in → stage1_reg → stage2_reg → out_data"
```

### 3. 控制流分析

| 能力 | 说明 |
|------|------|
| 条件路径追踪 | 检测 `if/else`、`generate`、`?: ` |
| always_ff/always_comb 区分 | 识别时序逻辑和组合逻辑 |
| 敏感信号列表 | 提取 `always_ff @(posedge clk)` 的时钟 |

### 4. Pipeline 延迟分析

```python
query_register_chain(signal_path) -> List[register, latency]
```

**示例**:
```
输入: "top.u_dut.stage1_out"
输出:
  - stage1_reg (latency=1)
  - stage2_reg (latency=2)
  - stage3_reg (latency=3)
```

**延迟计算**:
- `always_ff` 非阻塞赋值 = 1 cycle
- 连续赋值 = 0 cycle (combinational)
- 多级寄存器链 = N cycle (pipeline stage)

### 5. 时钟域分析

```python
query_clock_domain(signal_path) -> str  # "clk" / "clk2" / None
```

**示例**:
```
always_ff @(posedge clk) reg <= data
→ clock_domain: "clk"
```

---

## 节点属性设计

### SignalNode

```python
@dataclass
class SignalNode:
    path: str                    # "top.u_dut.data[7:0]"
    kind: str                   # wire, reg, port, function_arg
    width: Tuple[int, int]      # (msb, lsb), e.g., (7, 0)
    
    # 语义信息
    is_register: bool           # 是否是寄存器 (always_ff)
    is_combinational: bool      # 是否是组合逻辑 (always_comb)
    clock_domain: Optional[str] # 时钟域, e.g., "clk" or None
    conditions: List[str]       # 触发条件, e.g., ["if(enable)", "generate(gen_idx)"]
    
    # 层级信息
    parent_module: str          # "top.u_dut"
    generate_context: List[str] # ["gen_loop[0]", "gen_block"] or []
    function_context: Optional[str] # "calc_checksum" or None
```

### ConnectionEdge

```python
@dataclass
class ConnectionEdge:
    src: str                     # 源信号 path, e.g., "top.u_dut.data"
    dst: str                     # 目标信号 path, e.g., "top.u_dut.reg"
    kind: str                    # DRIVER | LOAD | CONNECTION | CONDITION
    
    # 语义信息
    condition: Optional[str]     # 触发条件, e.g., "enable" or None
    latency: int                 # 延迟 (0=combinational, 1=flip-flop, N=pipeline)
    
    # 位置信息
    assignment_stmt: str         # 所在语句, e.g., "always_ff @(posedge clk)"
```

---

## Agent Debug 接口

```python
def debug_signal(signal_path: str) -> Dict:
    """
    Agent 查询信号的完整信息
    
    Args:
        signal_path: 信号路径, e.g., "top.u_dut.data[7:0]"
        
    Returns:
        {
            "signal": "top.u_dut.data[7:0]",
            "kind": "reg",
            "width": (7, 0),
            "is_register": True,
            "clock_domain": "clk",
            "conditions": ["always_ff @(posedge clk)"],
            
            "upstream": [       # 谁驱动这个信号
                {"path": "top.u_dut.data_in", "kind": "DRIVER", "condition": None}
            ],
            
            "downstream": [    # 这个信号驱动谁
                {"path": "top.u_sub.data_out", "kind": "DRIVER", "condition": "enable"}
            ],
            
            "register_chain": [  # 寄存器链 (pipeline 分析)
                {"path": "top.u_dut.stage1_reg", "latency": 1},
                {"path": "top.u_dut.stage2_reg", "latency": 2},
            ],
            
            "data_flow": "data_in → stage1_reg → stage2_reg → data_out"
        }
    """
```

---

## 技术方案

### 遍历策略

基于 `pyslang.visit()` + `VisitAction.Skip` 实现：

1. **边界控制**: 指定 module instance，只遍历其内部，不深入嵌套子实例
2. **BFS 模式**: 使用 VisitAction.Skip 跳过不需要的子树
3. **上下文跟踪**: 在遍历过程中维护 generate/function 上下文栈

```python
def _visit_callback(self, node) -> 'VisitAction':
    kind = node.kind.name
    
    # 嵌套实例 → Skip
    if kind == 'Instance' and self._is_nested_instance(hp):
        return VisitAction.Skip
    
    # 目标实例 → 开启收集
    if kind == 'Instance' and hp == self.target_path:
        self._in_target = True
        return VisitAction.Advance
    
    # 收集信号和连接
    if self._in_target:
        self._process_node(node, kind)
    
    return VisitAction.Advance
```

### 图构建流程

```
1. 解析源码 → Compilation (语义分析)
2. 使用 pyslang.visit() 遍历
3. 在目标 module 内收集:
   - SignalNode (Variable, Net, Port, FormalArgument)
   - ConnectionEdge (Assignment, ContinuousAssign)
4. 识别:
   - 寄存器 (always_ff + NonblockingAssignment)
   - 组合逻辑 (always_comb, assign)
   - 条件 (if/else, generate)
5. 构建 NetworkX 图
6. 提供查询 API
```

---

## 分层抽象设计

### 核心概念

跳过的 instance 也要解析，只是做边界抽象。Instance 作为图的边界节点，通过 Port Interface 与外部连接，可以逐层展开深入分析。

| 层级 | 节点 | 边 |
|------|------|-----|
| MIG (Module Instance Graph) | Module Instance, Port | CONNECTION (port-to-port) |
| Signal Graph | Signal, Port, Internal Register | DRIVER, LOAD, CONDITION |

### Instance 边界抽象

```python
@dataclass
class InstanceBoundary:
    """Instance 边界抽象"""
    path: str              # "top.u_sub"
    module_type: str       # "sub"
    
    # Port 接口（外部视图）
    ports: List[PortInterface]
    
    # 内部视图（可选展开）
    internal_graph: Optional['SignalGraph'] = None
    
    def expand(self):
        """展开内部细节"""
        self.internal_graph = self._build_internal_graph()
    
    def collapse(self):
        """收起内部细节"""
        self.internal_graph = None

@dataclass
class PortInterface:
    """Port 接口抽象"""
    name: str              # "data"
    direction: str          # "input" / "output"
    width: Tuple[int,int]   # (7, 0)
    
    # 外部连接（跨 instance）
    external_connection: Optional[str] = None  # "top.data"
    
    # 内部连接（instance 内部）
    internal_signal: Optional[str] = None      # "sub.data"
```

### 分层结构示意

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Module Instance Graph (MIG)                        │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  top                                                 │     │
│  │    ├── Port: clk, data                              │     │
│  │    └── Instance: u_sub (边界节点)                    │     │
│  │         ├── Port Interface: .data, .clk             │     │
│  │         └── 连接关系: clk↔u_sub.clk, data↔u_sub.data│     │
│  └─────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              ↓ expand(depth=2)
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Signal Graph (u_sub 内部展开)                     │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  u_sub                                                 │     │
│  │    ├── Port: data(input), clk(input)                 │     │
│  │    ├── Internal: internal_reg                        │     │
│  │    ├── AlwaysFF: internal_reg <= data (posedge clk) │     │
│  │    └── Instance: u_child (边界节点)                   │     │
│  │         └── Port Interface: .data, .clk, .out       │     │
│  └─────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 连接关系分层

```
                    层级 1: Instance 连接 (MIG)
                    
    top.clk ──────────────→ top.u_sub.clk
    top.data ──────────────→ top.u_sub.data
    
                    层级 2: Signal 连接 (展开后)
                    
    top.u_sub.clk ──DRIVER──→ sub.clk ──DRIVER──→ sub.u_child.clk
    top.u_sub.data ──DRIVER──→ sub.data ──DRIVER──→ sub.u_child.out
```

### 逐层分析 API

```python
class SignalGraphAnalyzer:
    
    def query_connection(self, signal_path: str, depth=1):
        """
        查询信号连接，支持逐层展开
        
        Args:
            signal_path: 信号路径
            depth: 展开深度
                   1 = 只看 port 连接
                   2 = 展开一层 instance
                   N = 展开 N 层
        """
        # Level 1: 获取连接
        connections = self._get_immediate_connections(signal_path)
        
        if depth > 1:
            # Level 2+: 展开下一层
            for conn in connections:
                if conn.is_instance_boundary:
                    conn.expanded = self.query_connection(
                        conn.internal_path, 
                        depth=depth-1
                    )
        
        return connections
    
    def expand_instance(self, instance_path: str) -> 'SignalGraph':
        """展开 instance 边界，进入其内部"""
        return self._build_signal_graph(instance_path)
    
    def collapse_instance(self, instance_path: str):
        """收起 instance 边界，回到外部视图"""
        pass
```

### 遍历控制与抽象的关系

| 操作 | 行为 |
|------|------|
| `VisitAction.Skip` | 跳过 instance 内部细节，将其作为边界节点 |
| `expand_instance()` | 展开边界节点，显示内部 Signal Graph |
| `collapse_instance()` | 收起内部细节，回到 MIG 视图 |

**遍历流程**:
```
1. 遍历到 Instance [top.u_sub]
   → 创建 InstanceBoundary 节点
   → 解析 Port Interface
   → 记录外部连接

2. 遍历到 Instance [top.u_sub.u_child]
   → Skip (边界控制)
   → 但仍解析其 Port Interface
   → 添加到 u_child 的 Port 列表

3. 构建 MIG: top.u_sub 与 top.u_sub.u_child 通过 Port 连接

4. 可选: expand_instance("top.u_sub") → 展开内部 Signal Graph
```

## 现有 Schema 评估

### 已有数据结构覆盖情况

| 需求 | 现有 Schema | 状态 | 说明 |
|------|------------|------|------|
| SignalNode | `TraceNode` (graph/models.py) | ✅ 已有 | 包含 path, kind, width, is_clock, is_reset, is_enable, parent 等 |
| ConnectionEdge | `TraceEdge` (graph/models.py) | ✅ 已有 | 包含 src, dst, kind, condition, clock_domain |
| Instance 边界抽象 | `ModuleInstanceNode` + `PortInfo` (module_instance_graph.py) | ✅ 已有 | 包含 ports 映射, parent, module_type |
| 分层连接 (port-to-port) | `EdgeKind.CONNECTION` | ✅ 已有 | Instance 间通过 Port 连接 |
| 寄存器识别 | `TraceNode.is_clock/is_reset/is_enable` | ✅ 已有 | 配合 `EdgeKind.CLOCK/RESET` |
| 条件追踪 | `ConditionInfo` (data_models.py) | ✅ 已有 | 支持 if/case/conditional_op |
| Pipeline 延迟 | `TimingAnalysisResult.register_stages` (data_models.py) | ✅ 已有 | 寄存器级数 + latency 计算 |
| 时钟域分析 | `TraceEdge.clock_domain` | ✅ 已有 | 支持跨时钟域检测 |
| Agent Debug 接口 | `SignalTracer.trace()` (query/signal.py) | ✅ 已有 | trace_fanin/trace_fanout |
| **遍历方式** | 手动递归 + if-elif | ❌ 待升级 | 需要迁移到 `pyslang.visit()` |

### 详细 Schema 映射

#### 1. TraceNode (graph/models.py) ✅

```python
@dataclass
class TraceNode:
    id: str                    # "top.u_dut.data[7:0]"
    name: str
    module: str
    kind: NodeKind            # SIGNAL, REG, WIRE, PORT_IN, PORT_OUT, INSTANTIATED_MODULE
    width: Tuple[int, int]     # (7, 0)
    
    # 语义标记
    is_clock: bool            # 时钟信号
    is_reset: bool            # 复位信号
    is_enable: bool           # 使能信号
    is_port: bool             # 端口信号
    
    # 位选信息
    bit_range: Optional[str]   # "[7:4]"
    parent: Optional[str]       # 父节点 ID
    parent_bit_start/end        # 位选范围
```

#### 2. TraceEdge (graph/models.py) ✅

```python
@dataclass
class TraceEdge:
    src: str
    dst: str
    kind: EdgeKind            # DRIVER, CLOCK, RESET, CONNECTION, BIT_SELECT
    assign_type: str           # '', 'blocking', 'nonblocking'
    condition: str             # 触发条件
    clock_domain: str          # 时钟域
    confidence: str            # high/medium/uncertain
```

#### 3. PortInfo + ModuleInstanceNode (module_instance_graph.py) ✅

```python
@dataclass
class PortInfo:
    name: str                  # "clk"
    direction: str             # "input" / "output" / "inout"
    width: Tuple[int, int]     # (7, 0)
    internal_signal: str       # "dut.clk"
    module_type: str           # "dut"

@dataclass
class ModuleInstanceNode:
    id: str                    # "top.u_dut"
    module_type: str           # "dut"
    parent: Optional[str]       # "top"
    ports: Dict[str, PortInfo]  # port_name → PortInfo
```

#### 4. 增强模型 (data_models.py) ✅

```python
@dataclass
class ConnectionEdge:
    timing: str                # '@posedge clk'
    assign_type: str          # 'blocking', 'nonblocking', 'assign'
    condition_signals: List[str]
    is_conditional: bool

@dataclass
class ConditionInfo:
    kind: str                  # 'if', 'case', 'conditional_op'
    expr: str                  # 条件表达式原文
    signals: List[str]         # 条件涉及的信号
    true_branch: str
    false_branch: Optional[str]

@dataclass
class TimingAnalysisResult:
    register_stages: int       # 寄存器级数
    registers_in_path: List[str]
    estimated_latency_cycles: int
    cross_clock_domain: bool

@dataclass
class SignalChain:
    drivers: List[ConnectionEdge]
    loads: List[ConnectionEdge]
    timing_analysis: Optional[TimingAnalysisResult]
    conditions: List[ConditionInfo]
    data_flow_when: str        # 数据流成立条件
```

### 结论

**概念和方案已有**，只是**遍历实现需要升级**：

1. ✅ 数据结构 (TraceNode, TraceEdge, SignalChain) 已完备
2. ✅ 分层抽象 (MIG + SignalGraph) 已实现
3. ✅ 查询 API (SignalTracer, ClockDomainTracer) 已实现
4. ❌ **遍历方式**: 从手动递归 → `pyslang.visit()`

**下一步**: 将现有遍历逻辑迁移到 `pyslang.visit()` 框架，同时复用现有的数据结构。

---

## 开放讨论点

1. **图结构**: 使用 NetworkX 还是自定义？
2. **信号标识**: 如何处理位选 `data[7:4]`？
3. **跨模块**: 是否需要支持跨模块边界追踪？
4. **实时更新**: 图是否需要支持增量更新？
5. **性能**: 大型 design (10000+ signals) 的性能考虑？

---

## 遍历框架设计

### 外层控制 vs Handler 分工

```
┌─────────────────────────────────────────────────────────┐
│  遍历层 (Outer Layer) - 控制边界                         │
│                                                         │
│  1. 判断是否 Skip (边界控制)                            │
│  2. 维护上下文 (_in_target, _current_module, etc.)       │
│  3. 决定 VisitAction                                    │
│  4. 调用 Handler 提取数据                                │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Handler 层 (@on) - 只做提取和转换                        │
│                                                         │
│  1. 提取原始数据                                         │
│  2. 转换为抽象 (TraceNode, TraceEdge, etc.)              │
│  3. 不控制遍历，只负责 transformation                   │
└─────────────────────────────────────────────────────────┘
```

### 外层控制示例

```python
def _visit_callback(self, node) -> 'VisitAction':
    """遍历层 - 只做边界控制和状态维护"""
    kind = node.kind.name
    hp = getattr(node, 'hierarchicalPath', None)
    hp_str = str(hp) if hp else ""
    
    # ===== 边界控制在最外层 =====
    
    if kind == 'Instance':
        if self._is_nested_instance(hp_str):
            self._collect_instance_boundary(node)  # 收集 Port 信息
            return VisitAction.Skip
        if hp_str == self.target_path:
            self._in_target = True
            return VisitAction.Advance
    
    # 时钟域检测
    if kind == 'AlwaysFFStatement' and self._in_target:
        self._current_clock = self._extract_clock(node)
    
    # 调用 Handler（Handler 只做提取，不返回 VisitAction）
    if kind in self._HANDLERS and self._in_target:
        self._HANDLERS[kind](node)
    
    return VisitAction.Advance
```

### Handler 只做转换

```python
@on('Variable')
def handle_variable(self, node):
    """提取变量 → 转换为 TraceNode"""
    hp = getattr(node, 'hierarchicalPath', None)
    if not hp:
        return
    
    path = str(hp)
    node_data = TraceNode(
        id=path,
        name=path.split('.')[-1],
        module=self._current_module.id,
        kind=NodeKind.REG if self._current_clock else NodeKind.SIGNAL,
        width=self._extract_width(node),
        clock_domain=str(self._current_clock) if self._current_clock else ""
    )
    self._current_module.add_node(node_data)

@on('Assignment')
def handle_assignment(self, node):
    """提取赋值 → 转换为 TraceEdge"""
    edge = TraceEdge(
        src=self._extract_lhs(node),
        dst=self._extract_rhs(node),
        kind=EdgeKind.DRIVER,
        condition=self._current_condition,
        clock_domain=str(self._current_clock) if self._current_clock else ""
    )
    self._current_module.add_edge(edge)
```

---

## 连接模式表示

### 1. 基础连接模式

| 模式 | 表示方式 |
|------|----------|
| 一对一 | `Edge(src, dst, DRIVER)` |
| 一对多 (Fan-out) | 多条 `Edge(a, b)` + `Edge(a, c)` |
| 多对一 (Multi-Driver) | `Edge(b, a, DRIVER_CONDITIONAL, condition="en")` |

### 2. 多对多连接

#### 2.1 连接组合 (Concat)

```systemverilog
assign {upper, lower} = {data[15:8], data[7:0]};
```

```python
ConnectionGroup(id="concat_1", kind="concat")
Edge(data[15:8], upper, CONCAT_PART, group_id="concat_1", src_bit_range="[15:8]", dst_bit_range="[7:0]")
Edge(data[7:0], lower, CONCAT_PART, group_id="concat_1", src_bit_range="[7:0]", dst_bit_range="[7:0]")
```

#### 2.2 广播 (Broadcast)

```systemverilog
assign {3{duplicate}} = data;
```

```python
ConnectionGroup(id="broadcast_1", kind="broadcast")
Edge(data, duplicate[2], BROADCAST, group_id="broadcast_1")
Edge(data, duplicate[1], BROADCAST, group_id="broadcast_1")
Edge(data, duplicate[0], BROADCAST, group_id="broadcast_1")
```

#### 2.3 分裂 (Split)

```systemverilog
assign {a, b, c} = data;
```

```python
ConnectionGroup(id="split_1", kind="split")
Edge(data[15:12], a, SPLIT, group_id="split_1")
Edge(data[11:8], b, SPLIT, group_id="split_1")
Edge(data[7:4], c, SPLIT, group_id="split_1")
```

### 3. 多驱动冲突检测

```python
# 无需 EdgeKind，用方法检测
class SignalGraph:
    def has_conflict(self, signal_id: str) -> bool:
        """检测多驱动冲突：两个或多个无条件驱动"""
        unconditional = [
            e for e in self.get_incoming_edges(signal_id)
            if e.kind == EdgeKind.DRIVER and e.condition == ""
        ]
        return len(unconditional) > 1
```

---

## EdgeKind 扩展原则

### 设计原则

| 原则 | 说明 |
|------|------|
| **EdgeKind 表示语义类型差异** | 语义类型不同 → 新 EdgeKind |
| **属性表示数值差异** | 只是值不同 → 用属性 |
| **算法检测表示复杂语义** | 可计算 → 不用 EdgeKind |
| **配对关系显式表示** | group_id + member_index 确定配对 |

### 确认的 EdgeKind 扩展

| EdgeKind | 用途 | 状态 |
|---------------|------|------|
| DRIVER | 驱动关系 | ✅ 保留 |
| CLOCK | 时钟触发 | ✅ 保留 |
| RESET | 复位触发 | ✅ 保留 |
| CONNECTION | 模块端口连接 | ✅ 保留 |
| BIT_SELECT | 位选聚合 | ✅ 保留 |
| CONCAT_PART | 连接组合成员 | ✅ 确认需要 |
| BROADCAST | 广播复制 | ✅ 确认需要 |
| SPLIT | 分裂 | ✅ 确认需要 |

---

## 多对多连接表示方案

### 核心设计

**多条边 + group_id + member_index**：
- 每条边表示一个具体的位级映射（二元关系）
- `group_id` 关联同一组的所有边
- `member_index` 显式表示配对关系

```python
# {a, b} = {c, d} 表示 a=c, b=d

Edge(c, a, CONCAT_PART, group_id="concat_1", member_index=0,
     src_bit_range="[7:0]", dst_bit_range="[7:0]")
Edge(d, b, CONCAT_PART, group_id="concat_1", member_index=1,
     src_bit_range="[7:0]", dst_bit_range="[7:0]")
```

### 配对关系

| 字段 | 作用 |
|------|------|
| `group_id` | 关联同组 |
| `member_index` | 配对索引，相同 index 表示配对 |

**配对示例**：
```
member_index=0: c → a
member_index=1: d → b
```

### 多对多连接类型

#### Concat 连接组合

```systemverilog
assign {upper, lower} = {data[15:8], data[7:0]};
```

```python
Edge(data[15:8], upper, CONCAT_PART, group_id="concat_1", member_index=0,
     src_bit_range="[15:8]", dst_bit_range="[7:0]")
Edge(data[7:0], lower, CONCAT_PART, group_id="concat_1", member_index=1,
     src_bit_range="[7:0]", dst_bit_range="[7:0]")
```

#### Broadcast 广播

```systemverilog
assign {3{duplicate}} = data;
```

```python
Edge(data, duplicate[2], BROADCAST, group_id="broadcast_1", member_index=0)
Edge(data, duplicate[1], BROADCAST, group_id="broadcast_1", member_index=1)
Edge(data, duplicate[0], BROADCAST, group_id="broadcast_1", member_index=2)
```

#### Split 分裂

```systemverilog
assign {a, b, c} = data;
```

```python
Edge(data[15:12], a, SPLIT, group_id="split_1", member_index=0)
Edge(data[11:8], b, SPLIT, group_id="split_1", member_index=1)
Edge(data[7:4], c, SPLIT, group_id="split_1", member_index=2)
```

### 优势

| 优势 | 说明 |
|------|------|
| 图论一致性 | 边是二元关系，不需要改变 Graph API |
| 查询简单 | 现有 API `find_drivers/loads` 可用 |
| 语义清晰 | 每条边表示一个具体的位级驱动 |
| 扩展性好 | 任意数量的映射 |

---

## 扩展的 TraceEdge

```python
@dataclass
class TraceEdge:
    # 基础
    src: str
    dst: str
    kind: EdgeKind
    assign_type: str = ""
    condition: str = ""
    clock_domain: str = ""
    confidence: str = "high"
    
    # 多对多支持
    group_id: Optional[str] = None      # "concat_1", "broadcast_1", "split_1"
    member_index: Optional[int] = None  # 配对索引，相同 index 表示配对
    
    # 位精确性
    src_bit_range: Optional[str] = None  # "[7:4]"
    dst_bit_range: Optional[str] = None  # "[3:0]"
    
    # 原始信息
    raw_assignment: Optional[str] = None  # "{a, b} = {c, d}"
```

### group_id 使用规则

| 值 | 说明 |
|----------|------|
| `None` | 普通边，非多对多 |
| `"concat_N"` | Concat 连接组合 |
| `"broadcast_N"` | Broadcast 广播 |
| `"split_N"` | Split 分裂 |

### member_index 使用规则

| 场景 | 值 |
|------|------|
| 普通边 | `None` |
| 多对多边 | `0, 1, 2, ...` |

---

## 多驱动冲突检测

### 冲突定义

**多驱动冲突**：两个或多个无条件的 DRIVER 边指向同一信号

```systemverilog
// 冲突
assign data = a;  // 无条件
assign data = b;  // 无条件 → 冲突
```

### 检测方法

```python
class SignalGraph:
    def has_multi_driver_conflict(self, signal_id: str) -> bool:
        unconditional = [
            e for e in self.get_incoming_edges(signal_id)
            if e.kind == EdgeKind.DRIVER and e.condition == ""
        ]
        return len(unconditional) > 1
```

---

## 扩展的 NodeKind

```python
class NodeKind:
    SIGNAL = auto()
    WIRE = auto()
    REG = auto()
    PORT_IN = auto()
    PORT_OUT = auto()
    PORT_INOUT = auto()
    PARAM = auto()
    CONST = auto()
    INSTANTIATED_MODULE = auto()
    GENERATE_BLOCK = auto()
    BIT_SELECT = auto()      # 位选节点
```

---

## 查询接口设计

### 1. 宏观查询 (Macro) — 所有驱动

```python
def find_all_drivers(signal_id: str) -> List[TraceEdge]:
    """找所有驱动这个信号的边（不考虑类型）"""
    return [e for e in self.get_incoming_edges(signal_id) 
            if e.kind in (DRIVER, CONCAT_PART, BROADCAST, SPLIT)]
```

### 2. 微观查询 (Micro) — 指定类型

```python
def find_drivers(signal_id: str, kind: EdgeKind = None) -> List[TraceEdge]:
    """找指定类型的驱动"""
    if kind is None:
        return self.find_all_drivers(signal_id)
    return [e for e in self.get_incoming_edges(signal_id) if e.kind == kind]
```

**用法**：
```python
find_drivers("data")              # 所有驱动
find_drivers("data", DRIVER)      # 只有 DRIVER
find_drivers("data", CONCAT_PART) # 只有 CONCAT_PART
```

### 3. 组合查询

```python
def find_drivers_by_kinds(signal_id: str, kinds: List[EdgeKind]) -> List[TraceEdge]:
    """按多种类型查询"""
    return [e for e in self.get_incoming_edges(signal_id) if e.kind in kinds]

# 用例
find_drivers_by_kinds("data", [DRIVER, CONCAT_PART])
```

### 4. 多对多查询

```python
def get_connection_group(group_id: str) -> List[TraceEdge]:
    """获取同一组的所有边"""
    return [e for e in self.edges() if e.group_id == group_id]

def get_paired_signal(signal_id: str, group_id: str, member_index: int) -> Optional[str]:
    """获取 member_index 相同的配对信号"""
    for e in self.edges():
        if e.group_id == group_id and e.member_index == member_index and e.dst == signal_id:
            for src_edge in self.edges():
                if src_edge.group_id == group_id and src_edge.member_index == member_index:
                    return src_edge.src
    return None
```

---

## Agent 查询接口

### debug_signal()

```python
def debug_signal(signal_path: str, level: str = "all") -> Dict:
    """
    level: "all" | "macro" | "micro"
    
    all: 返回所有驱动类型
    macro: 只返回普通 DRIVER
    micro: 只返回位级驱动 (CONCAT_PART, BROADCAST, SPLIT)
    """
    if level == "all":
        all_edges = self.find_all_drivers(signal_path)
    elif level == "macro":
        all_edges = self.find_drivers(signal_path, DRIVER)
    elif level == "micro":
        all_edges = self.find_drivers_by_kinds(signal_path, 
                                               [CONCAT_PART, BROADCAST, SPLIT])
    
    return {
        "signal": signal_path,
        "kind": "REG",
        "width": (7, 0),
        "bit_range": "[7:4]" or None,
        "parent": "top.u_dut.data" or None,
        
        "upstream": [
            {
                "path": e.src, 
                "kind": e.kind.name, 
                "condition": e.condition, 
                "group_id": e.group_id
            }
            for e in all_edges
        ],
        
        "downstream": [...],
        
        "multi_driver_analysis": {
            "has_conflict": False,
            "unconditional_drivers": [],
            "conditional_drivers": [{"source": "a", "condition": "en"}]
        },
        
        "connection_groups": [
            {
                "group_id": "concat_1",
                "kind": "CONCAT",
                "members": [
                    {"src": "data[15:8]", "dst": "upper", "index": 0},
                    {"src": "data[7:0]", "dst": "lower", "index": 1}
                ]
            }
        ]
    }
```

### query_connection_group()

```python
def query_connection_group(group_id: str) -> List[TraceEdge]:
    """查询指定 group_id 的所有连接"""
    edges = [e for e in graph.edges() if e.group_id == group_id]
    
    # 按 member_index 分组
    members = defaultdict(list)
    for edge in edges:
        members[edge.member_index].append(edge)
    
    return [ConnectionGroup(group_id=group_id, members=members[i]) 
            for i in sorted(members.keys())]
```

## 复杂表达式处理

### 表达式复杂度分类

| 类型 | 示例 | 说明 |
|------|------|------|
| 简单表达式 | `data = a + b` | 直接信号 |
| 函数调用 | `data = func(a, b)` | 函数返回值 |
| 条件表达式 | `data = sel ? a : b` | 三元运算符 |
| 嵌套多元 | `data = (a + b) * (c + d) << 2` | 多层嵌套 |
| 混合场景 | `data = enable ? func(a, b) : c + d` | 组合 |

### 核心原则

1. **边表示驱动关系**（可能带 condition）
2. **expression 字段存储原始表达式**
3. **operands 提取顶层操作数**
4. **signals 提取所有信号引用**

---

### 简单表达式

```python
# data = a + b
Edge(a, data, DRIVER, 
     expression="a + b",
     operands=["a", "b"],
     signals=["a", "b"])
```

---

### 函数调用

#### 抽象模式

```python
# Function 作为节点
NodeKind.FUNCTION = auto()

# 图结构
a ──DRIVER──→ calc.a
b ──DRIVER──→ calc.b
calc ──DRIVER──→ data

# 边属性
Edge(calc, data).expression = "calc(a, b)"
Edge(calc, data).function_return = True
```

#### 示例

```systemverilog
function [7:0] calc(input [7:0] a, input [7:0] b);
    logic [7:0] tmp;
    tmp = a ^ b;
    calc = tmp + 1'b1;
endfunction

data = calc(a, b);
```

```python
# 函数节点
Node(calc, kind=FUNCTION)

# 函数输入连接
Edge(a, calc.a, DRIVER)
Edge(b, calc.b, DRIVER)

# 函数输出连接
Edge(calc, data, DRIVER, expression="calc(a, b)")
```

---

### 条件表达式 (?:)

#### 三元运算符

```systemverilog
data = sel ? a : b;
```

```python
# 两条边，分别表示条件分支
Edge(a, data, DRIVER, condition="sel")
Edge(b, data, DRIVER, condition="!sel")
```

#### If 语句

```systemverilog
always_comb begin
    if (en) begin
        data = a;
    end else begin
        data = b;
    end
end
```

```python
Edge(a, data, DRIVER, condition="en")
Edge(b, data, DRIVER, condition="!en")
```

---

### Case 语句

```systemverilog
always_comb begin
    case (sel)
        2'b00: data = a;
        2'b01: data = b;
        2'b10: data = c;
        default: data = d;
    endcase
end
```

```python
Edge(a, data, DRIVER, condition="sel == 2'b00")
Edge(b, data, DRIVER, condition="sel == 2'b01")
Edge(c, data, DRIVER, condition="sel == 2'b10")
Edge(d, data, DRIVER, condition="default")
```

#### 多输出 Case + group_id

```systemverilog
case (sel)
    2'b00: {a, b} = {x, y};
    2'b01: {a, b} = {z, w};
endcase
```

```python
Edge(x, a, DRIVER_CONDITIONAL, condition="sel == 2'b00", group_id="case_1", member_index=0)
Edge(y, b, DRIVER_CONDITIONAL, condition="sel == 2'b00", group_id="case_1", member_index=1)
Edge(z, a, DRIVER_CONDITIONAL, condition="sel == 2'b01", group_id="case_1", member_index=0)
Edge(w, b, DRIVER_CONDITIONAL, condition="sel == 2'b01", group_id="case_1", member_index=1)
```

---

### 嵌套表达式递归提取

```python
@dataclass
class ExprInfo:
    raw: str                  # 原始表达式 "(a + b) * c"
    operands: List[str]       # 顶层操作数 ["(a + b)", "c"]
    signals: List[str]        # 所有信号引用 ["a", "b", "c"]
    has_condition: bool = False

def extract_expression(node) -> ExprInfo:
    """递归提取表达式中的所有信号"""
    kind = node.kind.name
    
    if kind == 'IdentifierName':
        return ExprInfo(raw=str(node), operands=[str(node)], signals=[str(node)])
    
    elif kind == 'BinaryExpression':
        left = extract_expression(node.left)
        right = extract_expression(node.right)
        op = get_operator(node.operator)
        return ExprInfo(
            raw=f"({left.raw} {op} {right.raw})",
            operands=left.operands + right.operands,
            signals=left.signals + right.signals
        )
    
    elif kind == 'FunctionCall':
        args = [extract_expression(arg) for arg in node.arguments]
        func_name = get_function_name(node)
        return ExprInfo(
            raw=f"{func_name}({', '.join(a.raw for a in args)})",
            operands=[func_name] + [a for arg in args for a in arg.operands],
            signals=[s for arg in args for s in arg.signals]
        )
    
    elif kind == 'ConditionalExpression':
        cond = extract_expression(node.condition)
        true_val = extract_expression(node.true_value)
        false_val = extract_expression(node.false_value)
        return ExprInfo(
            raw=f"({cond.raw} ? {true_val.raw} : {false_val.raw})",
            operands=[cond.raw] + true_val.operands + false_val.operands,
            signals=cond.signals + true_val.signals + false_val.signals,
            has_condition=True
        )
    
    elif kind == 'MemberAccessExpression':
        obj = extract_expression(node.value)
        member = str(node.member)
        return ExprInfo(raw=f"{obj.raw}.{member}", operands=obj.operands, signals=obj.signals)
    
    elif kind == 'ElementSelectExpression':
        obj = extract_expression(node.value)
        selector = extract_expression(node.selector)
        return ExprInfo(raw=f"{obj.raw}[{selector.raw}]", operands=obj.operands, signals=obj.signals)
```

---

### 示例：复杂嵌套表达式

```systemverilog
data = (a + b) * (c + d) << 2;
```

#### 提取结果

```python
ExprInfo(
    raw="((a + b) * (c + d)) << 2",
    operands=["(a + b)", "(c + d)", "2"],
    signals=["a", "b", "c", "d"]
)
```

#### 边表示

```python
Edge("(a + b)", data, DRIVER, 
     expression="((a + b) * (c + d)) << 2",
     operands=["(a + b)", "(c + d)", "2"],
     signals=["a", "b", "c", "d"])
```

---

### 扩展的 TraceEdge

```python
@dataclass
class TraceEdge:
    # 基础
    src: str
    dst: str
    kind: EdgeKind
    assign_type: str = ""
    condition: str = ""
    clock_domain: str = ""
    confidence: str = "high"
    
    # 多对多支持
    group_id: Optional[str] = None
    member_index: Optional[int] = None
    
    # 位精确性
    src_bit_range: Optional[str] = None
    dst_bit_range: Optional[str] = None
    
    # 表达式支持
    expression: Optional[str] = None    # 原始表达式 "func(a, b) + c"
    operands: List[str] = []            # 顶层操作数
    signals: List[str] = []             # 所有信号引用
    
    # 函数支持
    function_return: bool = False        # 是否是函数返回值
```

---

## 表达式节点设计

### 核心思想

**表达式直接拆分为多个 TraceNode 去表达**：
- 每个表达式创建一个 Expression 节点
- 表达式组成部分连接到该节点
- 表达式节点连接到结果信号

### NodeKind 扩展

```python
class NodeKind:
    # ... 现有
    SIGNAL = auto()
    REG = auto()
    WIRE = auto()
    PORT_IN = auto()
    PORT_OUT = auto()
    
    # 新增表达式节点
    EXPRESSION = auto()     # 表达式节点 (a + b, a ? b : c)
    FUNCTION_CALL = auto()  # 函数调用节点
```

### 简单表达式

```systemverilog
data = a + b;
```

```python
# 创建表达式节点
expr_node = TraceNode(
    id="expr_add_1",
    name="a + b",
    kind=NodeKind.EXPRESSION,
    expression="a + b",
    operands=["a", "b"]
)

# 连接
a ──DRIVER──→ expr_add_1
b ──DRIVER──→ expr_add_1
expr_add_1 ──DRIVER──→ data
```

### 函数调用

```systemverilog
data = calc(a, b);
```

```python
# 创建函数调用节点
func_node = TraceNode(
    id="func_calc_1",
    name="calc(a, b)",
    kind=NodeKind.FUNCTION_CALL,
    function_name="calc",
    arguments=["a", "b"]
)

# 连接
a ──DRIVER──→ func_calc_1
b ──DRIVER──→ func_calc_1
func_calc_1 ──DRIVER──→ data
```

### 条件表达式 (三元)

```systemverilog
data = sel ? a : b;
```

```python
# 创建条件表达式节点
cond_node = TraceNode(
    id="cond_ternary_1",
    name="sel ? a : b",
    kind=NodeKind.EXPRESSION,
    expression="sel ? a : b",
    condition="sel",
    true_branch="a",
    false_branch="b"
)

# 连接
sel ──DRIVER──→ cond_ternary_1
a ──DRIVER──→ cond_ternary_1
b ──DRIVER──→ cond_ternary_1
cond_ternary_1 ──DRIVER_CONDITIONAL──→ data
```

### 嵌套表达式

```systemverilog
data = (a + b) * (c + d) << 2;
```

```python
# 创建层级表达式节点
# Level 1: 加法
add_1 = TraceNode(id="expr_add_1", name="a + b", kind=NodeKind.EXPRESSION, expression="a + b")
add_2 = TraceNode(id="expr_add_2", name="c + d", kind=NodeKind.EXPRESSION, expression="c + d")

# Level 2: 乘法
mul = TraceNode(id="expr_mul", name="(a+b) * (c+d)", kind=NodeKind.EXPRESSION, expression="(a+b) * (c+d)")

# Level 3: 移位
shift = TraceNode(id="expr_shift", name="(a+b) * (c+d) << 2", kind=NodeKind.EXPRESSION, expression="(a+b) * (c+d) << 2")

# 连接
a ──DRIVER──→ expr_add_1
b ──DRIVER──→ expr_add_1
c ──DRIVER──→ expr_add_2
d ──DRIVER──→ expr_add_2

expr_add_1 ──DRIVER──→ expr_mul
expr_add_2 ──DRIVER──→ expr_mul

expr_mul ──DRIVER──→ expr_shift
expr_shift ──DRIVER──→ data
```

### 函数展开 (后续)

```python
def expand_function(func_node: TraceNode):
    """展开函数内部逻辑"""
    func_name = func_node.function_name
    func_body = semantic_adapter.get_function_body(func_name)
    
    # 展开为实际逻辑
    # 例如: calc = a ^ b; calc = calc + 1;
    # → 创建展开后的节点和边
    # → 替换 FUNCTION_CALL 节点
```

### TraceNode 扩展

```python
@dataclass
class TraceNode:
    id: str
    name: str
    module: str
    kind: NodeKind
    width: Tuple[int, int] = (0, 0)
    
    # 表达式相关 (新增)
    expression: Optional[str] = None    # "a + b", "sel ? a : b"
    operands: List[str] = []            # ["a", "b"]
    signals: List[str] = []              # 所有信号引用
    
    # 函数相关 (新增)
    function_name: Optional[str] = None
    function_return: bool = False
    
    # 条件相关
    condition: Optional[str] = None     # "sel"
    true_branch: Optional[str] = None
    false_branch: Optional[str] = None
```

---

## 语义 AST 处理

### 语义 AST 不展开函数

测试结果显示，语义 AST 中的 Function 调用保持为 `Call` 节点，不展开内部逻辑：

```
Call node:
   subroutine = Symbol(SymbolKind.Subroutine, "calc")  ← 函数符号
   subroutineKind = SubroutineKind.Function           ← 区分 function/task
   arguments = [Expression(NamedValue), ...]          ← 参数
   effectiveWidth = 8                                  ← 返回值宽度
```

### 处理策略

| 语义 AST 行为 | 处理方式 |
|--------------|----------|
| 不展开函数 | 创建 FUNCTION_CALL 节点，记录函数调用 |
| 不展开函数 | 记录 arguments 作为 operands |
| 后续需要 | 提供 expand_function() 展开函数内部 |

---

## 待讨论清单

1. ✅ **EdgeKind 扩展** - CONCAT_PART / BROADCAST / SPLIT 已确认
2. ✅ **配对关系** - group_id + member_index 已确认
3. ✅ **多驱动冲突** - 用方法检测，不需要 EdgeKind
4. ❓ **ExpressionNode** - 是否需要独立的表达式节点？
5. ❓ **raw_assignment** - 是否需要存储原始赋值语句？
6. ❓ **遍历与抽象的边界** - 外层控制 vs Handler 职责是否清晰？