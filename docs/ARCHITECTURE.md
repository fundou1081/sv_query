# sv_query 架构文档 v2.0

> 更新日期: 2026-07-29
> 项目路径: ~/my_dv_proj/sv_query

---

## 一、架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Layer (27 commands)                  │
│  trace / arch / visualize / dataflow / cdc / timing / ...   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Query Layer (API)                       │
│  UnifiedTracer — 统一入口, trace_fanin/trace_fanout/...    │
│  SignalTracer / LoadTracer / ClockDomainTracer             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│             Graph Layer (核心数据模型)                       │
│  SignalGraph ←─ DataFlowGraph ←─ ModuleInstanceGraph (MIG) │
│  VizData — 统一可视化中间层 (V6.7)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Extractor Layer (5 extractors)                │
│  Driver / Load / Connection / Clock / Module               │
│  SVA / Covergroup / UVM                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Visitor Layer (10+ visitors)               │
│  SignalExpression / StatementCollector / Constraint / ...  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                pyslang AST (Semantic)                      │
│  Compilation + getRoot() — 唯一可信数据源 [铁律1]           │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、核心数据模型

### 2.1 SignalGraph — 信号关系图

**文件**: `src/trace/core/graph/models.py` (663 行)

```python
class NodeKind(Enum):
    # ═══ 核心: 硬件信号 (≈80% 引用) ═══
    SIGNAL, WIRE, REG, PORT_IN, PORT_OUT, PORT_INOUT, CONST
    # ═══ 核心: 架构 ═══
    PARAM, INSTANTIATED_MODULE, GENERATE_BLOCK
    # ═══ 扩展: Class / Constraint ═══
    CLASS, CLASS_INSTANCE, CLASS_PROPERTY, CONSTRAINT_*, ...
    # ═══ 实验: 表达式 ═══
    EXPRESSION, FUNCTION_CALL

class EdgeKind(Enum):  # V6.6 重新分区
    # ═══ 核心: 硬件信号边 (≈90% 引用) ═══
    DRIVER, CLOCK, RESET, CONNECTION, BIT_SELECT
    # ═══ 扩展: Class / Constraint ═══
    CONSTRAINS, HAS_CONDITION, HAS_CONSEQUENT, HAS_ALTERNATE,
    HAS_LHS, HAS_RHS, HAS_MEMBER, IS_INSTANCE_OF, ...
```

```python
@dataclass
class TraceNode:
    id: str              # "picorv32.cpuregs"
    name: str            # "cpuregs"
    module: str          # "picorv32"
    kind: NodeKind
    width: tuple[int, int]  # (31, 0)
    bit_range: str | None
    parent: str | None        # 位选父节点
    is_clock/is_reset: bool

@dataclass  
class TraceEdge:
    src: str
    dst: str
    kind: EdgeKind
    assign_type: str       # continuous / nonblocking / blocking
    condition: str         # "state == FETCH" — 显示在边上
    clock_domain: str
    expression: str        # "a + b" — 驱动表达式
    bit_slice: str         # "[7:0]"
    source: SignalSource | None  # V6.5/V6.6 位精确结构化源
    confidence: str        # high / medium / low
```

### 2.2 SignalSource — 位精确信号源 (V6.5/V6.6)

**driver 和 load 共享**。替代纯字符串的 expression/bit_slice。

```python
@dataclass
class SignalSource:
    signal: str             # "a"
    bit_start: int | None   # 7 (MSB)
    bit_end: int | None     # 0 (LSB)
    full_expression: str    # "a[7:0] + b[3:0]"
    op: str                 # "Add" / "ArithmeticShiftRight"
    operand_side: str       # "left" / "right"
    casts: list[str]        # ["$signed"]
    is_decomposed: bool     # True = 从 binary op 分解
```

### 2.3 DriverInfo — 驱动详情 (V6.6)

```python
@dataclass
class DriverInfo:
    node: TraceNode
    source: SignalSource | None  # V6.6 替代 expression/bit_slice
    condition: str         # "state == FETCH"
    reset_condition: str   # "!rst_n"
    clock_domain: str      # "clk"
    assign_type: str       # nonblocking / continuous / blocking
    distance: int
    target_signal: str
    
    @property
    def expression(self) -> str:  # 从 source 派生
    @property
    def bit_slice(self) -> str:   # 从 source 派生
```

### 2.4 VizData — 统一可视化中间层 (V6.7)

**数据和渲染彻底解耦**。所有画图功能的输入。

```python
@dataclass
class VizNode:
    id, label, full_path, module, kind           # 必需
    class_: str          # DATA/CONTROL/CLOCK/RESET  (可选)
    stage_id: int | None # pipeline 阶段 (可选)
    risk_level: str      # LOW/MEDIUM/HIGH/CRITICAL (可选)
    is_critical: bool    # chain critical path (可选)

@dataclass
class VizEdge:
    id, src, dst, kind                           # 必需
    expression: str      # 驱动表达式
    condition: str       # "state == FETCH" — 显示在边上!
    source_signal: str   # 位精确信号名
    source_op: str       # 操作符
    is_control_edge: bool # 控制边 → 虚线
    edge_cycle_delta: int # chain cycle 计数 (可选)
```

**渲染管线**: `SignalGraph → build_viz_data(options) → VizData → render_dot(config) → DOT`

---

## 三、Extractor 层 (5 + 3)

| Extractor | 文件 | 职责 |
|-----------|------|------|
| **DriverExtractor** | `driver_extractor.py` (2639行) | DRIVER/CLOCK/RESET 边 + SignalSource |
| **LoadExtractor** | `load_extractor.py` (423行) | 模块端口节点 |
| **ConnectionExtractor** | `connection_extractor.py` (503行) | CONNECTION 边 (port mapping) |
| **ClockDomainExtractor** | `clock_domain_extractor.py` | 时钟域推断 |
| **ModuleExtractor** | `module_extractor.py` (467行) | 模块实例信息 |
| SVAExtractor | `sva_extractor.py` | SVA assertion 提取 |
| CovergroupExtractor | `covergroup_extractor.py` | 覆盖率提取 |
| UVMTestbenchExtractor | `uvm_testbench_extractor.py` | UVM 结构提取 |

所有 extractor 返回 `ExtractorResult(nodes, edges, errors, port_to_internal)`.

---

## 四、VizData 渲染管线 (V6.7)

### 4.1 设计原则

- **数据和渲染彻底解耦** — VizData 是纯数据，不包含渲染逻辑
- **一个格式，所有画图功能** — graph/dataflow/pipeline/chain 共用
- **可选字段** — 每条命令只取自己需要的 5-10 个字段
- **统一渲染器** — `render_dot(viz, config)` 约 200 行

### 4.2 迁移状态

| 命令 | 状态 | 备注 |
|------|------|------|
| `visualize graph` | ✅ 已迁移 | 用户命令 |
| `visualize dataflow` | ✅ 已迁移 | 用户命令 |
| `visualize pipeline` | ✅ 已迁移 | 用户命令 |
| `visualize chain` | ⏸ 保留 | 不同数据源 (路径遍历器) |
| `visualize module` | ⏸ 保留 | 不同数据源 (InstanceResult) |
| `arch show` | ⏸ 保留 | 不同数据源 (实例图) |
| `visualize teach` | ⏸ 保留 | 自定义 HTML |

### 4.3 文件结构

```
src/trace/core/graph/viz/
├── __init__.py            # 公开 API
├── viz_data_models.py     # VizNode / VizEdge / VizData
├── viz_data_builder.py    # build_viz_data(graph, options)
└── viz_dot_renderer.py    # render_dot(viz, config) — 统一 DOT 生成
```

### 4.4 旧渲染器状态

| 文件 | 状态 |
|------|------|
| `signal_graph_viewer.py::render_html` | ⛔ 内部 helper 仍在使用 |
| `signal_graph_viewer.py::render_mermaid` | ⛔ 内部 helper 仍在使用 |
| `dataflow_viz.py::generate_dataflow_dot` | ⛔ `_emit_split_by_module` 仍在使用 |
| `pipeline_viz.py::generate_pipeline_dot` | 🗑 deprecated [V6.7] |
| `pipeline_viz.py::generate_pipeline_timing_dot` | 🗑 deprecated [V6.7] |
| `pipeline_viz.py::generate_pipeline_load_dot` | 🗑 deprecated [V6.6] |
| `viz_legend.py` | ⛔ CLI 层仍在使用 |

---

## 五、Query API

| 类 | 文件 | 职责 |
|----|------|------|
| **SignalTracer** | `query/signal.py` | trace_fanin / trace_fanout / trace_fanin_detailed |
| **LoadTracer** | `query/load.py` | trace_loads |
| **ClockDomainTracer** | `query/clock_domain.py` | trace_clock_domain |
| **ModuleTracer** | `query/module.py` | trace_module |

`trace_fanin_detailed()` 返回 `list[DriverInfo]`，DriverInfo 包含 SignalSource.

---

## 六、Graph/Analyzer 层

| 分析器 | 职责 | 稳定性 |
|--------|------|--------|
| **DataFlowGraph** | 跨模块数据流路径搜索 | ✅ 核心 |
| **ControlFlowAnalyzer** | 控制流分析 | ⚠️ 次流 |
| **CDCAnalyzer** | 跨时钟域检测 | ✅ 核心 |
| **TimingAnalyzer** | 关键路径 (reg depth) | ⚠️ 次流 |
| **SignalClassifier** | DATA/CONTROL/CLOCK 分类 | ✅ 核心 |
| **ControlCoverageGenerator** | 控制覆盖率生成 | ⚠️ 次流 |
| **HandshakeDetector** | 握手协议检测 | ⚠️ 次流 |
| **HandshakeDetector** | 握手协议检测 | ⚠️ 次流 |

---

## 七、技术栈

| 组件 | 技术 |
|------|------|
| AST 解析 | pyslang (Compilation + getRoot) |
| 图结构 | NetworkX DiGraph |
| 数据类 | dataclass + Enum + auto() |
| VISITOR | @on 装饰器 handler 注册 |
| CLI | Typer |
| 测试 | pytest (2958 tests, 97.1% pass) |
| 渲染 | Graphviz DOT + `dot -Tpng/svg` |

---

## 八、核心设计铁律

| 铁律 | 内容 |
|------|------|
| 铁律1 | pyslang Semantic AST 唯一数据源 |
| 铁律4 | 不允许创建孤儿节点 |
| 铁律13 | 金标准测试优先 |
| 铁律15 | Visitor 模式 |
| 铁律16 | ENABLE/DATA 不作为独立边类型 |
| 铁律26 | AST 遍历必须使用 Visitor，禁止 if-elif 链 |
| 铁律29 | Visitor 调用统一通过 extract() |

---

## 九、版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07-29 | V6.7 | VizData 统一可视化层，graph/dataflow/pipeline 迁移 |
| 2026-07-29 | V6.6 | DriverSource→SignalSource, DriverInfo含SignalSource, NodeKind/EdgeKind分区, 可视化清理 |
| 2026-07-28 | V6.5 | DriverSource结构化驱动源 (位精确binary decomposition) |
| 2026-07-28 | V6.4 | binary operator decomposition + generate-if限制文档化 |
| 2026-07-27 | V6.3 | ast_utils: unwrap/kind_matches 统一包装解包 |
| 2026-06-25 | PR1-7 | Module-level抽取+L2跨模块+L3内部信号+L4可视化+L5 benchmark+L6 CI+L7 picorv32 |
| 2026-06-15 | 1.0+ | Evidence/Snapshot/Verify/Dataflow/Controlflow 全套 |
| 2026-05-26 | 1.0 | 初始架构 + 996 tests |
