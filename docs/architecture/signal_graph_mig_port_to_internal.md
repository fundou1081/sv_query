# SignalGraph + MIG port_to_internal 架构设计

**日期**: 2026-05-13  
**时间**: 15:00 - 16:40  
**状态**: 已实施 (Commit `2fc6f05`)

---

## 背景

在分析 `ConnectionExtractor` (CE) 和 `ModuleInstanceGraph` (MIG) 的功能重叠时，发现：

1. **MIG 的 `_add_port_mapping()`** 独立构建 `port_to_internal` 映射
2. **CE 的 `_build_connection_edges()`** 也构建了相同的 `inst_port_id → child_signal_id` 映射
3. **PathResolver 是死代码** — 没有任何公共 API 调用它

这导致了重复构建和数据不一致的风险。

---

## 架构分析结论

### 重叠分析

| 组件 | 用途 | 构建方式 |
|------|------|----------|
| CE `_build_connection_edges()` | 构建 CONNECTION 边时 | `inst_port_id = f"{inst_path}.{port_name}"`, `child_signal_id = f"{inst_module_name}.{port_name}"` |
| MIG `_add_port_mapping()` | 维护实例端口映射 | 相同逻辑，独立构建 |

### 语义区分

| 映射来源 | 语义 | 示例 |
|----------|------|------|
| MIG 构建的 | 模块结构定义 | `top.u_dut.clk` → `dut.clk` (端口定义) |
| CE 构建的 | 实际连接关系 | `top.u_sub.data` → `sub.data` (实际连接) |

两者语义不同，不应简单合并，而是让 MIG 复用 CE 的结果。

---

## Option A 方案 (实施)

### 设计原则

1. **数据源单一**: CE 是 `port_to_internal` 的唯一构建者
2. **MIG 消费者**: MIG 从 SignalGraph 读取，而非自己构建
3. **语义分离**: MIG 保留自己的 `port_to_internal` (结构语义)，备用 SignalGraph (连接语义)

### 数据流

```
ConnectionExtractor.extract()
    ↓
    构建 CONNECTION 边时同步填充 result.port_to_internal
    ↓
ExtractorResult(port_to_internal: Dict[str, str])
    ↓
GraphBuilder._extract_all_edges()
    ↓
    收集 result.port_to_internal → SignalGraph._port_to_internal
    ↓
SignalGraph.get_port_to_internal() / get_internal_signal()
    ↓
ModuleInstanceGraph(signal_graph=graph)
    ↓
    MIG.get_internal_signal() 优先用自己的，备用 SignalGraph
```

### 核心代码变更

#### 1. ExtractorResult (graph_builder.py)

```python
@dataclass
class ExtractorResult:
    nodes: List[TraceNode] = field(default_factory=list)
    edges: List[TraceEdge] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    port_to_internal: Dict[str, str] = field(default_factory=dict)  # 新增
```

#### 2. ConnectionExtractor.extract() (graph_builder.py)

```python
# 构建 CONNECTION 边时同步填充
result.port_to_internal[inst_port_id] = child_signal_id
```

#### 3. SignalGraph (graph_models.py)

```python
class SignalGraph(nx.DiGraph):
    def __init__(self):
        super().__init__()
        self._node_data: Dict[str, TraceNode] = {}
        self._edge_data: Dict[Tuple[str, str], TraceEdge] = {}
        self._port_to_internal: Dict[str, str] = {}  # 新增

    def get_port_to_internal(self) -> Dict[str, str]:
        return self._port_to_internal

    def get_internal_signal(self, inst_port_id: str) -> Optional[str]:
        return self._port_to_internal.get(inst_port_id)
```

#### 4. GraphBuilder._extract_all_edges() (graph_builder.py)

```python
def _extract_all_edges(self):
    for name, extractor in self._extractors.items():
        result = extractor.extract()
        for edge in result.edges:
            self.graph.add_trace_edge(edge)
        # 收集 port_to_internal 映射
        if hasattr(result, 'port_to_internal') and result.port_to_internal:
            self.graph._port_to_internal.update(result.port_to_internal)
```

#### 5. ModuleInstanceGraph (module_instance_graph.py)

```python
def __init__(self, adapter, signal_graph=None):
    self.adapter = adapter
    self.signal_graph = signal_graph  # 新增：引用 SignalGraph
    self.instances: Dict[str, ModuleInstanceNode] = {}

def get_internal_signal(self, port_path: str) -> Optional[str]:
    # 优先用 MIG 自带的（结构语义）
    if self.port_to_internal:
        return self.port_to_internal.get(port_path)
    # 备用：从 SignalGraph 获取（连接语义）
    if self.signal_graph is not None:
        return self.signal_graph.get_internal_signal(port_path)
    return None
```

#### 6. UnifiedTracer (unified_tracer.py)

```python
# 传 signal_graph 给 MIG
self._module_graph = ModuleInstanceGraph(adapter, self._graph)
```

---

## 语义分离策略

| 场景 | MIG.port_to_internal | SignalGraph.port_to_internal |
|------|----------------------|------------------------------|
| 定义来源 | 模块端口声明 | 实际 assign 连接 |
| 用途 | 父子模块结构关系 | 跨模块 driver 链追踪 |
| 示例 | `top.u_dut.clk` → `dut.clk` | `top.u_sub.data` → `sub.data` |

MIG 的 `get_internal_signal()` 优先用自己的映射，因为那是模块结构的语义定义。SignalGraph 的映射作为备用，用于连接语义。

---

## 验证结果

### 测试

- integration: 200 passed ✅
- cross_module_tracking MIG tests: 5 passed ✅
- new driver/load tests: 6 passed ✅

### 示例验证

```python
# SignalGraph 有 CE 构建的 port_to_internal
graph._port_to_internal
# {'top.u_sub.data': 'sub.data', 'top.u_gen.clk': 'clk_gen.clk'}

# MIG 从 SignalGraph 读取
mig.get_internal_signal('top.u_sub.data')  # → 'sub.data'

# MIG 自己的 port_to_internal (结构语义)
mig.port_to_internal
# {'top.u_dut.clk': 'dut.clk', ...}
```

---

## 决策记录

| 日期 | 时间 | 决策 | 理由 |
|------|------|------|------|
| 2026-05-13 | 15:00 | 分析 CE vs MIG 功能重叠 | 发现重复构建 port_to_internal |
| 2026-05-13 | 15:30 | 确认 PathResolver 是死代码 | 所有公共 API 都用 SignalGraph |
| 2026-05-13 | 15:50 | 选择 Option A 方案 | CE 已有数据，改动最小 |
| 2026-05-13 | 16:00 | 实施 Option A | 代码变更 + 测试 |
| 2026-05-13 | 16:40 | 验证通过 | 提交 `2fc6f05` |

---

## 后续工作 (未实施)

| 项目 | 状态 | 说明 |
|------|------|------|
| 移除 MIG._add_port_mapping() | 待定 | 需确认无其他代码依赖 |
| 移除 PathResolver | 待定 | 确认是死代码后可清理 |
| MIG 统一使用 SignalGraph 数据 | 待定 | 当前保持语义分离 |

---

## 相关文档

- `docs/CONNECTION_vs_MIG_analysis.md` — CE vs MIG 功能对比分析
- `docs/code_framework_analysis.md` — 代码框架分析
- `EXAMPLES.md` §8.1 — 跨模块路径追踪示例
- `EXAMPLES.md` §8.1.1 — MIG 高级查询 API 示例