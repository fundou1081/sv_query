# Req-8: SignalTracer 信号追踪 - 技术方案评估

## 现状分析

### 已有框架

| 组件 | 位置 | 状态 |
|------|------|------|
| `SignalTracer` 类 | `src/trace/core/query/signal.py` | ✅ 存在 |
| `UnifiedTracer.trace_signal()` | `src/trace/unified_tracer.py` | ✅ 存在 |
| `SignalGraph` 类 | `src/trace/core/graph/models.py` | ✅ 存在 |
| `GraphBuilder` 类 | `src/trace/core/graph_builder.py` | ⚠️ 部分实现 |

### 当前问题

测试结果显示：
```
SignalTracer 未实现
```

这意味着 `GraphBuilder` 只构建了部分节点和边。

---

## 技术架构

### 数据流

```
Pyslang AST
    ↓
GraphBuilder.build()
    ↓
SignalGraph (NetworkX DiGraph)
    ↓
SignalTracer.trace(signal)
    ↓
SignalChain (drivers, loads, confidence)
```

### 节点结构 (`TraceNode`)

```python
@dataclass
class TraceNode:
    id: str           # 唯一标识 (module.signal 或 module.signal[bit])
    name: str         # 信号名
    module: str       # 所属模块
    kind: NodeKind    # INPUT/OUTPUT/WIRE/REG/INSTANCE
    width: (msb, lsb) # 位宽
    is_port: bool
    is_clock: bool
    ...
```

### 边结构 (`TraceEdge`)

```python
@dataclass
class TraceEdge:
    src: str          # 源节点ID
    dst: str          # 目标节点ID
    kind: EdgeKind    # DRIVER/CONNECTION/CLOCK/RESET
    assign_type: str  # "continuous" / "nonblocking"
    condition: str   # 条件 (if/enable)
    confidence: str
```

### 边类型 (`EdgeKind`)

```python
class EdgeKind(Enum):
    DRIVER = auto()      # 数据驱动 (q <= d)
    CLOCK = auto()       # 时钟触发
    RESET = auto()       # 异步复位
    CONNECTION = auto()  # 模块端口连接
    BIT_SELECT = auto()  # 位选择聚合
```

---

## 需要实现的功能

### 1. 基础信号追踪

```python
def trace(signal: str, module: str = None) -> SignalChain:
    """追踪信号的驱动源和负载"""
```

**工作流程**:
1. 在 `SignalGraph` 中查找信号节点
2. 沿 `DRIVER` 边追溯驱动源
3. 沿连接边查找负载
4. 返回 `SignalChain(root, drivers, loads, confidence)`

### 2. 驱动追溯 (`_collect_all_drivers`)

```python
def _collect_all_drivers(self, signal_id: str) -> List[TraceNode]:
    """递归收集所有驱动"""
```

**需要**:
- 识别 `ContinuousAssign` (assign)
- 识别 `NonBlockingAssign` (always block 中的 `<=`)
- 识别实例端口连接 `CONNECTION` 边

### 3. 负载查找 (`_find_loads`)

```python
def _find_loads(self, signal_id: str) -> List[TraceNode]:
    """查找信号的所有负载"""
```

**需要**:
- 在 `SignalGraph` 中反向查找以该信号为源的边

### 4. 跨模块追踪

```python
def trace_cross_module(self, signal: str) -> SignalChain:
    """跨模块追踪信号"""
```

**需要**:
- `ModuleInstanceGraph` 支持
- 通过 `CONNECTION` 边跨越实例边界

---

## 实现方案

### 方案 A: 增强 GraphBuilder (推荐)

**思路**: 完善 `GraphBuilder` 使其能从 AST 构建完整的信号图

**步骤**:

1. **完善节点创建**
   - 处理 `DataDeclaration` (wire/reg/logic)
   - 处理 `PortDeclaration` (input/output/inout)
   - 处理 `NetDeclaration` (wand/wor)
   - 提取信号位宽信息

2. **完善边创建**
   - `ContinuousAssign` → `DRIVER` 边 (assign 语句)
   - `NonBlockingAssign` → `DRIVER` 边 (<= 赋值)
   - `HierarchyInstantiation` → `CONNECTION` 边 (实例连接)
   - 时钟检测 → `CLOCK` 边

3. **SignalTracer 集成**
   - 确保 `UnifiedTracer.build_graph()` 调用后 `SignalGraph` 包含完整数据
   - 实现递归追溯

### 方案 B: 独立追踪器

**思路**: 不依赖 `GraphBuilder`，直接从 AST 追踪

**实现**:
```python
def trace(self, signal: str) -> SignalChain:
    # 1. 在当前模块中查找信号定义
    # 2. 分析驱动表达式
    # 3. 递归追踪子表达式中的信号
    # 4. 跨越实例边界
```

**优点**: 不依赖 GraphBuilder，可渐进实现
**缺点**: 重复解析逻辑，效率较低

---

## 技术挑战

### 挑战 1: always block 内的信号追踪

```verilog
always @(posedge clk) begin
    q <= d;  // d 的驱动追溯
end
```

需要识别:
- 时钟事件 `@(posedge clk)`
- 非阻塞赋值 `q <= d`
- 条件语句 `if (en) q <= d`

### 挑战 2: 位选信号

```verilog
assign out = in[7:0];
assign out2 = in[15:8];
```

`in` 有两个不同的驱动，需要:
- 按位选拆分成多个节点
- 或保留位选信息在边上

### 挑战 3: 跨时钟域

```verilog
always @(posedge clk) begin
    q2 <= q1;  // 跨时钟域，需要识别
end
```

需要:
- 检测时钟事件
- 识别跨时钟域传递

### 挑战 4: 函数/任务调用

```verilog
always @(posedge clk)
    out = func(in);
```

需要追踪 `func` 内部对 `in` 的使用。

---

## 优先级排序

| 阶段 | 功能 | 优先级 | 说明 |
|------|------|--------|------|
| 1 | 基础 ContinuousAssign 追踪 | P0 | assign 语句 |
| 2 | 实例端口连接追踪 | P1 | CONNECTION 边 |
| 3 | always block 非阻塞赋值 | P2 | 时序逻辑 |
| 4 | 位选信号处理 | P2 | bit select |
| 5 | 跨模块追踪 | P2 | ModuleInstanceGraph |
| 6 | 跨时钟域识别 | P3 | 时钟检测 |

---

## 建议实现路径

### Phase 1: 基础追踪 (1-2天)

1. 完善 `GraphBuilder` 处理 `ContinuousAssign`
2. 实现 `_collect_all_drivers` 递归追溯
3. 测试 `trace()` 对 assign 语句的追踪

### Phase 2: 端口连接 (1天)

1. 完善实例连接的边创建
2. 实现跨模块端口追踪

### Phase 3: 时序逻辑 (2-3天)

1. 处理 always block
2. 实现条件赋值追踪
3. 时钟识别

---

## 参考实现

已有的集成测试可作为参考:
- `sim/tests/integration/test_assign_chain.py`
- `sim/tests/integration/test_instance_connection.py`

---

## 评估结论

**可行性**: ✅ 高

**理由**:
1. 框架已存在，只需完善 `GraphBuilder`
2. 已有参考测试用例
3. 需求明确，渐进实现可行

**预计工时**:
- Phase 1 (基础追踪): 1-2 天
- Phase 2 (端口连接): 1 天
- Phase 3 (时序逻辑): 2-3 天
- **总计**: 4-6 天

**风险**:
- always block 内部逻辑复杂 (挑战 1)
- 跨时钟域边界检测需要时钟分析 (挑战 3)