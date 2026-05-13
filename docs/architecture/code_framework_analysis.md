# 代码框架核心模块职责分析

**生成时间**: 2026-05-13 14:45

---

## 模块概览

```
┌─────────────────────────────────────────────────────────────┐
│  UnifiedTracer                              137 行          │
│  Facade：trace_signal / find_path / trace_module           │
└────────────────┬────────────────────────────────────────────┘
                 │ build_graph()
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  GraphBuilder                               1517 行         │
│  编排所有 Extractor，构建 SignalGraph (nodes + edges)       │
└──────┬────────┬───────────┬────────────┬───────────────────┘
       │        │           │            │
       ▼        ▼           ▼            ▼
┌──────────┐ ┌─────────┐ ┌────────────────┐ ┌─────────────────┐
│ Driver   │ │  Load   │ │ Connection     │ │ ClockDomain     │
│Extractor│ │Extractor│ │Extractor       │ │Extractor        │
│ 17-179  │ │ 795-803 │ │ 1004-1275      │ │ 1276-1335       │
│DRIVER边 │ │ LOAD边  │ │CONNECTION边    │ │时钟域元数据     │
└──────────┘ └─────────┘ └────────────────┘ └─────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  ModuleInstanceGraph                      969 行            │
│  模块实例层级 + 端口映射 + PathResolver                      │
│  instances / port_to_internal / PathResolver               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PyslangAdapter                           1352 行           │
│  pyslang AST 封装：模块/端口/实例/连接 查询接口              │
│  唯一的数据来源，Extractor 和 MIG 都依赖它                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 各模块核心职责

### UnifiedTracer

- **文件**: `src/trace/unified_tracer.py:22`
- **行数**: 137 行
- **职责**: Facade 模式，对外暴露 trace_signal / trace_loads / find_path 等 API，屏蔽内部复杂度
- **数据输出**: SignalChain / LoadChain / 信号路径 / 时钟域追踪结果

### GraphBuilder

- **文件**: `src/trace/core/graph_builder.py:1336`
- **行数**: 1517 行
- **职责**: 编排所有 Extractor，协调 build 流程，最终输出 SignalGraph
- **核心流程**:
  ```
  build()
    → _extract_all_nodes()      (调用所有 Extractor.extract()，收集 nodes)
    → _extract_all_edges()      (调用所有 Extractor.extract()，收集 edges)
    → _mark_special_signals()
    → _create_hierarchical_bit_nodes()   (位选节点父子关系)
    → _upgrade_reg_nodes()      (reg 节点升级)
  ```

### DriverExtractor

- **文件**: `graph_builder.py:17`
- **行数**: ~162 行
- **职责**: 从 always_ff / always_comb / assign 语句中提取信号驱动关系
- **输出**: DRIVER 边 → 表示 "信号 A 由信号 B 驱动"

### LoadExtractor

- **文件**: `graph_builder.py:795`
- **行数**: ~8 行（核心约 50 行）
- **职责**: 提取信号的负载（被哪些信号引用）
- **输出**: LOAD 边 → 表示 "信号 A 被信号 B 加载"

### ConnectionExtractor

- **文件**: `graph_builder.py:1004`
- **行数**: ~271 行
- **职责**: 从模块实例化语法中提取端口连接关系
- **输出**: CONNECTION 边 → 表示 "模块实例端口连接到外部信号"
- **注意**: 包含自己的路径构建逻辑 `get_path()`，与 MIG 重复

### ClockDomainExtractor

- **文件**: `graph_builder.py:1276`
- **行数**: ~59 行
- **职责**: 提取时钟域信息（哪些信号属于相同时钟域）
- **输出**: 时钟域元数据

### ModuleInstanceGraph (MIG)

- **文件**: `src/trace/core/module_instance_graph.py:50`
- **行数**: 969 行
- **职责**: 管理模块实例层级、维护端口到内部信号的映射、支持跨模块路径查找
- **核心数据结构**:
  - `instances: Dict[str, ModuleInstanceNode]` — 实例 ID → 实例节点
  - `port_to_internal: Dict[str, str]` — "top.u_dut.clk" → "dut.clk"
  - `internal_to_port: Dict[str, str]` — 反向映射
- **子组件**: `PathResolver` — 基于 MIG 的信号路径查找

### PathResolver

- **文件**: `module_instance_graph.py:873`
- **行数**: ~96 行
- **职责**: 基于 MIG 的信号路径查找，协调 SignalGraph 和 ModuleInstanceGraph
- **方法**: `find_path(src, dst)` / `find_all_paths(src, dst)`

### PyslangAdapter

- **文件**: `src/trace/core/base.py:65`
- **行数**: 1352 行
- **职责**: 封装 pyslang AST，提供统一的数据访问接口
- **核心方法**:
  - `get_modules()` / `get_module(name)` — 获取模块
  - `get_port_declarations(module)` — 获取端口
  - `get_module_instances(trees)` — 获取 HierarchyInstantiation 节点
  - `get_generate_instances(trees)` — 获取 generate block 内的实例
  - `get_instance_connection(instance)` — 获取实例端口连接
- **依赖方**: 所有 Extractor 和 MIG 都通过它获取原始数据

---

## 职责边界

| 模块 | 输入 | 输出 | 调用者 |
|---|---|---|---|
| **UnifiedTracer** | 用户 API 调用 | SignalChain / 路径列表 | 用户代码 |
| **GraphBuilder** | PyslangAdapter + trees | SignalGraph (nodes+edges) | UnifiedTracer |
| **DriverExtractor** | always_ff/always_comb/assign | DRIVER 边 | GraphBuilder |
| **LoadExtractor** | assign/always 等 | LOAD 边 | GraphBuilder |
| **ConnectionExtractor** | 模块实例化 AST | CONNECTION 边 | GraphBuilder |
| **ClockDomainExtractor** | always_ff 块 | 时钟域信息 | GraphBuilder |
| **ModuleInstanceGraph** | trees（自己用 PyslangAdapter） | instance 图 + 端口映射 | UnifiedTracer / PathResolver |
| **PathResolver** | SignalGraph + ModuleInstanceGraph | 最短路径列表 | UnifiedTracer |
| **PyslangAdapter** | SyntaxTree | 模块/端口/实例/连接数据 | GraphBuilder / MIG |

---

## 数据流

```
源码(.sv)
    ↓ pyslang
SyntaxTree
    ↓
PyslangAdapter (查询接口)
    │
    ├──────────────────────────────┐
    ↓                              ↓
GraphBuilder                     ModuleInstanceGraph.build()
    │                              │
    ├─ DriverExtractor.extract() → DRIVER 边
    ├─ LoadExtractor.extract()   → LOAD 边
    ├─ ConnectionExtractor.extract() → CONNECTION 边
    │      └→ adapter.get_module_instances()   ← 重叠！
    │      └→ adapter.get_generate_instances()  ← 重叠！
    └─ ClockDomainExtractor.extract()
                                     │
                                     ↓
                               instances
                               port_to_internal
                               PathResolver

UnifiedTracer.get_graph() ← SignalGraph
UnifiedTracer.trace_signal() ← 基于 SignalGraph
UnifiedTracer.find_path() ← PathResolver (基于 MIG)
```

---

## 重叠区域

| 功能 | PyslangAdapter | MIG |
|---|---|---|
| 发现 HierarchyInstantiation | `get_module_instances()` | `_find_all_hierarchy_instantiations()` |
| 构建嵌套实例路径 | CE 自己用 `get_path()` | 遍历时直接构建 |
| 处理 generate block | 需配合 `get_generate_instances()` | 内置统一处理 |

详见 `docs/CONNECTION_vs_MIG_analysis.md` 第 12 节。

---

## 当前问题

1. **功能重叠**: base.py 和 MIG 在实例发现上完全重复
2. **路径不一致风险**: CE 的 `get_path()` 和 MIG 的路径构建可能产生不同格式
3. **PyslangAdapter 职责过重**: 1352 行，混合了数据查询和通用遍历逻辑

---

## 建议的抽象方向

### 方向 A: 统一实例数据层

```
InstanceRegistry（单一数据源）
├── 发现所有 HierarchyInstantiation
├── 构建 instance_path（支持嵌套 + generate block）
├── 提供 resolve_path() 查询
└── CE / MIG 共同依赖

CE: adapter.get_all_instances() → 建边
MIG: adapter.get_all_instances() → 构建端口映射
```

### 方向 B: 分层隔离

- **Data Layer** (PyslangAdapter): 只做 AST 查询，不含遍历逻辑
- **Instance Layer** (新增): 统一实例发现，包含路径构建
- **Graph Layer** (GraphBuilder): 消费 Instance Layer 输出，建边
- **MIG Layer** (ModuleInstanceGraph): 消费 Instance Layer 输出，建端口映射

### 方向 C: 保持现状（风险最低）

当前架构功能正常，两个系统独立演进代价最小。

---

*最后更新: 2026-05-13 14:45*
---

## 当前抽象结构评估

### 问题 1：PyslangAdapter 职责膨胀（1352 行）

当前 PyslangAdapter 混合了三类完全不同的职责：

| 类别 | 方法示例 | 性质 |
|---|---|---|
| **AST 数据查询** | `get_module_name`, `get_modules`, `get_port_declarations`, `get_instance_connection` | 稳定 public API，Extractor 依赖 |
| **通用树遍历** | `iter_children`, `_extract_modules`, `_extract_classes` | 内部辅助逻辑 |
| **实例发现** | `get_module_instances`, `get_generate_instances` | 可独立，CE 和 MIG 都用 |
| **信号分析** | `_analyze_stmt_for_drivers`, `analyze_task_internal_drivers` | DriverExtractor 的辅助 |

**问题**：任何改动都可能破坏 Extractor 的稳定依赖。

### 问题 2：实例发现双重兜底

```
PyslangAdapter.get_module_instances()      → CE 建边用
PyslangAdapter.get_generate_instances()   → CE 建边用（补 generate block）
ModuleInstanceGraph._find_all_hierarchy_instantiations() → MIG 自己用
```

CE 用 PyslangAdapter 的实例发现，MIG 用自己的实例发现。两套路径构建逻辑独立，容易产生不一致。

### 问题 3：MIG 对 PyslangAdapter 的使用不一致

MIG 用 adapter 获取端口信息，但实例发现用自己遍历 AST 的方式。这造成：
- `adapter.get_module_instances()` 能返回原始 AST 节点给 CE
- 但 MIG 需要自己重新解析一遍才能拿到 `{module_type, inst_name, instance_path}` 结构

---

## 更合适的抽象结构：数据层 + 实例层 + 图层 三层分离

### 目标架构

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: 数据层 (PyslangAdapter)           ~400 行          │
│  只做 AST 查询，稳定 public API                            │
│  get_modules / get_port_declarations / get_instance_connection │
└─────────────────────────────────────────────────────────────┘
                          ↑
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: 实例层 (InstanceResolver)        ~200 行          │
│  统一实例发现 + 路径构建，CE 和 MIG 共享                     │
│  get_all_instances() → [{module_type, inst_name, path, ...}] │
└────────────┬─────────────────────────────┬───────────────────┘
             │                           │
             ↓                           ↓
┌──────────────────────┐    ┌────────────────────────────┐
│  GraphBuilder        │    │  ModuleInstanceGraph      │
│  CE/Driver/Load 等   │    │  port_to_internal 构建     │
│  消费 InstanceResolver│    │  消费 InstanceResolver     │
└──────────────────────┘    └────────────────────────────┘
             │                           │
             └─────────────┬─────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: 图层 (GraphBuilder + SignalGraph)                  │
│  统一编排 Extraction，结果输出 SignalGraph                   │
└─────────────────────────────────────────────────────────────┘
```

### 关键变化

| 变化 | 说明 |
|---|---|
| **PyslangAdapter 瘦身** | 只保留模块/端口/接口的数据查询，删除 `get_module_instances` / `get_generate_instances` |
| **InstanceResolver 新类** | 统一实例发现 + generate block 处理 + 路径构建，向 CE 和 MIG 同时提供服务 |
| **MIG 重构** | 从 `adapter` 接收 `InstanceResolver`，不再自己遍历 AST |
| **ConnectionExtractor 重构** | 用 `InstanceResolver` 的结构化输出替代自己的 `get_path()` 逻辑 |

### InstanceResolver 接口设计

```python
class InstanceResolver:
    """统一的实例发现层"""

    def __init__(self, adapter: PyslangAdapter, trees: dict):
        self.adapter = adapter
        self.trees = trees

    def get_all_instances(self) -> List[InstanceInfo]:
        """返回所有模块实例的结构化信息
        
        InstanceInfo = {
            'module_type': str,      # 模块类型名
            'inst_name': str,        # 实例名
            'instance_path': str,    # 完整路径 top.u_dut.u_inner
            'parent_module': str,    # 父模块名
            'gen_block': Optional[str],  # generate block 标签
            'ast_node': HierarchyInstantiation  # 原始 AST 节点（供 CE 使用）
        }
        """
        ...

    def resolve_path(module_type: str, inst_name: str) -> str:
        """查询指定实例的完整路径"""
        ...
```

### 收益对比

| 问题 | 当前状态 | 解决方式 |
|---|---|---|
| 实例发现重复 | PyslangAdapter + MIG 各自发现 | 单一 InstanceResolver |
| 路径构建重复 | CE.get_path() + MIG._find_all_hierarchy_instantiations() | InstanceResolver 统一构建 |
| PyslangAdapter 膨胀 | 1352 行混合职责 | 拆分为 400行数据层 + 200行实例层 |
| generate block 处理不一致 | CE 需配合 get_generate_instances()，MIG 内置处理 | InstanceResolver 内置统一处理 |
| 路径格式不一致风险 | CE 和 MIG 可能产生不同路径 | 共享 InstanceResolver 保证一致 |

### 重构风险

| 风险项 | 说明 | 缓解措施 |
|---|---|---|
| ConnectionExtractor 破坏 | 约 271 行需要重构 | 保留旧接口，内部调用 InstanceResolver |
| PyslangAdapter 兼容性 | 删除的方法可能被其他模块使用 | 重构前先扫描所有使用者 |
| MIG 路径格式变化 | 现有测试依赖当前路径格式 | 更新测试路径格式（已部分完成） |
| API 兼容性问题 | 其他模块直接依赖 PyslangAdapter 的实例方法 | 保持向后兼容，新增方法，逐步废弃旧方法 |

### 重构优先级建议

```
阶段1: 新增 InstanceResolver 类
        - 实现 get_all_instances()
        - 内置处理 LoopGenerate/IfGenerate/CaseGenerate
        - 保留旧的 get_module_instances/get_generate_instances（内部调用 InstanceResolver）

阶段2: MIG 重构使用 InstanceResolver
        - 删除 _find_all_hierarchy_instantiations
        - 依赖 InstanceResolver.get_all_instances()
        - 保持现有 API 不变

阶段3: ConnectionExtractor 重构
        - 使用 InstanceResolver 替代 get_module_instances + get_generate_instances
        - 删除自己的 get_path() 逻辑
        - 验证输出与当前完全一致

阶段4: PyslangAdapter 瘦身
        - 删除实例发现相关方法（由 InstanceResolver 接管）
        - 删除通用树遍历方法（迁入 InstanceResolver 或独立工具类）
        - 只保留数据查询 API
```

### 结论

当前架构功能正常，重构收益明确但风险中等。建议：

- **有明确需求驱动时**（如需要统一路径格式、支持新语法、修复路径不一致 bug）再执行重构
- **重构时严格分阶段**，每阶段验证测试通过后再进入下一阶段
- **保持向后兼容**，旧接口包装新实现，不破坏现有调用方

---

*最后更新: 2026-05-13 14:59（抽象结构评估与建议）*

---

## MIG 是否必要的抽象？

### 关键发现：PathResolver 从未被使用

`UnifiedTracer` 的所有公开 API 都**没有调用 PathResolver**：

```
trace_signal()       → SignalTracer (基于 SignalGraph)
trace_loads()         → LoadTracer (基于 SignalGraph)
trace_fanout/fanin() → SignalTracer
trace_module()       → ModuleTracer
trace_port()         → ModuleTracer
find_connected_modules() → ModuleTracer
find_path()          → self._graph.find_path() (SignalGraph 的 nx.shortest_path)
detect_cycles()      → self._graph.detect_cycles()
```

PathResolver 被创建并存储（`unified_tracer.py:60`），但从未在任何公开 API 中被调用。它只在测试中可选地使用（`test_cross_module_tracking.py:173-175` 的 fallback 逻辑）。

### MIG 提供了什么 vs 替代品

| 功能 | 来源 | 是否有替代 |
|---|---|---|
| `instances`: 模块实例列表 + 父子关系 | MIG 独有 | SignalGraph 没有实例拓扑概念 |
| `port_to_internal`: 外部路径 → 内部信号映射 | MIG 独有 | ❌ ConnectionExtractor 建 CONNECTION 边，但没这个映射表 |
| `get_internal_signal(port_path)` | MIG 独有 | ❌ 同上 |
| `PathResolver.find_path(src, dst)` | 依赖 MIG | ❌ 只用于跨模块路径查找 |

### ConnectionExtractor 和 MIG 的本质差异

| 维度 | ConnectionExtractor | MIG |
|---|---|---|
| **目标** | 构建 SignalGraph 的边 | 构建实例拓扑 + 端口映射 |
| **实例信息用途** | 建 INSTANTIATED_MODULE 节点 + CONNECTION 边 | 给 PathResolver 用 |
| **数据结构** | 分散在 SignalGraph 的节点和边中 | 集中的 `instances` dict + `port_to_internal` dict |

MIG 实际上是把 ConnectionExtractor 应该生产的某些**元数据**（实例拓扑 + 端口映射）单独提取出来，形成独立结构。这在概念上类似于**索引**：把分散的信息集中起来，提供快速查询。

### 核心矛盾

- **MIG 的主要价值**是提供 `port_to_internal` 给 PathResolver
- **但 PathResolver 从未被调用过**

这意味着：
1. 如果不需要跨模块路径查找，MIG 的核心价值就不存在
2. 如果只需要 `instances` 字典，可以从 ConnectionExtractor 的实例化信息中导出

### 结论：MIG 是必要抽象吗？

**取决于 PathResolver 是否是必要的**：

| 场景 | PathResolver 价值 | MIG 必要性 |
|---|---|---|
| 只做信号追踪（trace_signal/trace_loads） | ❌ 不需要 | ❌ 不需要 |
| 需要跨模块路径查找（find_path 跨模块） | ✅ 需要 | ✅ 需要 |
| 需要验证实例拓扑和端口映射 | ❌ 可以从 SignalGraph 推导 | ⚠️ 可选 |

**MIG 不是必要的抽象——PathResolver 才是。PathResolver 依赖 MIG，所以 MIG 只是被动跟着。**

MIG 更像是一个"预见到需要"的抽象，而不是当前实际需要的抽象。

### 更理想的架构（无 PathResolver 需求时）

```
实例信息 → 从 ConnectionExtractor 导出（复用）
          └── CE 已经有 inst_module_name, inst_name, parent_module
              只需要增加一个集中索引: instances[path] = {module_type, parent, ports}

port_to_internal 映射 → 从 CONNECTION 边 + DRIVER 边推导
          └── top.u_dut.clk (port) → dut.clk (internal)
              这个映射已经在 SignalGraph 的边中存在
              不需要单独的 port_to_internal dict

MIG 简化为: 实例信息收集器（轻量级，不维护 port_to_internal）
```

### 更理想的架构（有 PathResolver 需求时）

```
InstanceRegistry（单一实例数据源）
    │
    ├──→ ConnectionExtractor → SignalGraph
    │
    └──→ MIG（消费 registry 的 instance_path + ports）
              ├── port_to_internal 构建（依赖 registry）
              └── PathResolver（依赖 MIG）
```

---

*最后更新: 2026-05-13 15:33（MIG 必要性分析）*

---

## port_to_internal 应该在何处实现

### 核心问题

`port_to_internal` 映射：`{top.u_dut.clk: dut.clk}` 是谁产生的？

**当前状态**：
- ConnectionExtractor 在 `extract()` 中已经构建了这个映射关系
- 但以**边**的形式分散存储在 SignalGraph 中，没有集中的数据结构
- MIG 自己重新构建了一份

### CE 已经产生的信息

```python
# CE 在 extract() 中产生的边：
# 输入端口: parent_signal → top.u_dut.clk → dut.clk
# 输出端口: dut.clk → top.u_dut.clk → parent_signal

# inst_port_id = f"{inst_path}.{port_name}"      # e.g., "top.u_dut.clk"
# child_signal_id = f"{inst_module_name}.{port_name}"  # e.g., "dut.clk"
# CONNECTION: top.u_dut.clk → dut.clk           ← 这就是 port_to_internal 映射
```

`port_to_internal` 的本质是：`{inst_port_id: child_signal_id}`

这已经在 SignalGraph 的边中存在，只是没有集中的数据结构。

### 三个候选位置

| 位置 | 优点 | 缺点 |
|---|---|---|
| **A. ConnectionExtractor** | 作为建边的副产品，直接可得 | CE 职责增加，产生与 MIG 的耦合 |
| **B. InstanceRegistry** | 统一实例数据源，消除重复 | 新增类，需要重构 CE |
| **C. SignalGraph** | 不新增类，从边推导 | 推导代价高，需要缓存 |

### 推荐：Option A（最小改动方案）

CE 在 `extract()` 时已经知道每个端口的 `inst_port_id` 和 `child_signal_id`，只需要增加一个输出：

```python
class ConnectionExtractor:
    def extract(self) -> ExtractorResult:
        result = ExtractorResult()
        ...
        port_to_internal = {}  # 新增

        for port_name, signal_name, direction in connections:
            inst_port_id = f"{inst_path}.{port_name}"      # e.g., "top.u_dut.clk"
            child_signal_id = f"{inst_module_name}.{port_name}"  # e.g., "dut.clk"

            if direction == 'input':
                result.edges.append(TraceEdge(src=parent_signal, dst=inst_port_id, kind=CONNECTION))
                result.edges.append(TraceEdge(src=inst_port_id, dst=child_signal_id, kind=CONNECTION))
            elif direction == 'output':
                result.edges.append(TraceEdge(src=inst_port_id, dst=parent_signal, kind=CONNECTION))
                result.edges.append(TraceEdge(src=child_signal_id, dst=inst_port_id, kind=DRIVER))

            port_to_internal[inst_port_id] = child_signal_id  # 新增

        result.port_to_internal = port_to_internal  # 新增输出
        return result
```

然后在 `GraphBuilder.build()` 中收集：

```python
def build(self) -> SignalGraph:
    ...
    for name, extractor in self._extractors.items():
        result = extractor.extract()
        for node in result.nodes:
            self.graph.add_trace_node(node)
        for edge in result.edges:
            self.graph.add_trace_edge(edge)
        # 新增: 收集 port_to_internal
        if hasattr(result, 'port_to_internal'):
            self._graph._port_to_internal.update(result.port_to_internal)
    ...
```

MIG 从 `SignalGraph._port_to_internal` 获取映射，不再自己构建。

### 目标架构（Option A）

```
当前:
  PyslangAdapter.get_module_instances() → CE → SignalGraph (CONNECTION边)
  MIG 自己构建 port_to_internal

目标:
  PyslangAdapter.get_module_instances() → CE
       │                               ↓
       │                          SignalGraph
       │                          (CONNECTION边 + _port_to_internal)
       │
       └──────────────────────────────→ MIG（从 SignalGraph 获取 port_to_internal）
       │
       └──────────────────────────────→ PathResolver
```

**关键变化**:
1. CE 在 `extract()` 中输出 `port_to_internal`（作为 ExtractorResult 的属性）
2. GraphBuilder 收集到 SignalGraph 的 `_port_to_internal` 字典
3. MIG 从 SignalGraph 获取，不再自己构建
4. PathResolver 从 SignalGraph 获取

**消除的重复**: MIG 不再自己构建 `port_to_internal`，复用 CE 的结果

### 为什么不选 B（InstanceRegistry）

InstanceRegistry 是更理想的架构，但改动代价高：
- 需要新增类
- 需要重构 CE 的路径构建逻辑
- 需要重构 MIG 的实例遍历逻辑

而 Option A 只需要：
- 在 CE 中增加一个 `port_to_internal` 输出
- 在 GraphBuilder 中收集到 SignalGraph
- MIG 改为从 SignalGraph 读取

**收益/风险比更高。**

### 为什么不选 C（SignalGraph 推导）

从边推导 `port_to_internal` 需要遍历所有边，时间复杂度 O(E)。如果每次查询都推导，代价高。如果缓存，又需要额外的存储空间和管理逻辑。不如在构建时直接计算并存储。

### Option A 的后续收益

如果未来采用 InstanceRegistry 方案，port_to_internal 可以自然迁移到 InstanceRegistry：

```
InstanceRegistry
  ├── get_all_instances() → [{instance_path, ports: [PortDef]}]
  └── port_to_internal（从 InstanceInfo.ports 构建）
      │
      ├──→ CE（复用 InstanceRegistry，不自己构建）
      └──→ MIG（从 InstanceRegistry 读取）
```

---

*最后更新: 2026-05-13 15:43（port_to_internal 实现位置分析）*

---

## 如果 CE 添加 port_to_internal，MIG 还剩什么？

### MIG 当前提供的东西

| 功能 | MIG | SignalGraph 是否有替代 |
|---|---|---|
| `port_to_internal` 映射 | ✅ 自己构建 | ❌ CE 添加后才有 |
| `instances` dict | ✅ | ❌ SignalGraph 只有 INSTANTIATED_MODULE 节点，没有集中索引 |
| `ModuleInstanceNode.parent` | ✅ | ❌ CE 没有存储父子关系 |
| `ModuleInstanceNode.ports` | ✅ `PortInfo` 对象 | ❌ 没有对应结构 |
| `get_instance(path)` | ✅ | ❌ 需要遍历 SignalGraph 节点 |
| `get_child_instances(parent_id)` | ✅ | ❌ 需要遍历所有节点 |
| `PathResolver.find_path()` | ✅ 依赖 MIG | ❌ 从未被调用 |

### SignalGraph 能提供什么

SignalGraph 有 INSTANTIATED_MODULE 节点和 CONNECTION 边，理论上有：
- 从边可以推断哪些节点是实例端口
- 从边可以推断实例父子关系（通过 CONNECTION 追踪）

但实际上：
- SignalGraph 没有集中的 `instances` dict
- 没有 parent 字段
- 没有 PortInfo 对象
- 每次查询需要遍历图，复杂度高

### MIG 在跨模块追踪场景下的价值

| 场景 | MIG 价值 | 说明 |
|---|---|---|
| 获取实例列表 | ✅ 有价值 | `instances` dict 是集中的索引 |
| 父子关系查询 | ✅ 有价值 | `get_child_instances()` 没有替代 |
| 端口信息（方向/位宽） | ✅ 有价值 | PortInfo 对象 |
| 路径解析 | ❌ 无价值 | PathResolver 从未被调用 |
| port_to_internal | ❌ 重复 | CE 添加后 MIG 不需要再构建 |

### MIG vs SignalGraph：结构视图差异

| 视图 | 提供者 | 特点 |
|---|---|---|
| **结构化的实例视图** | MIG | 集中的 `instances` dict、父子关系、端口信息、O(1) 查询 |
| **扁平的图视图** | SignalGraph | 节点+边、分散存储、需要遍历查询 |

对于需要快速查询实例结构、父子关系、端口信息的场景，MIG 有价值。
对于只需要信号追踪、边遍历的场景，SignalGraph 足够。

### 结论：需要 MIG 吗？

**取决于使用场景**：

| 场景 | 需要的抽象 | 说明 |
|---|---|---|
| 只做信号追踪（trace_signal/trace_loads） | SignalGraph | 不需要 MIG |
| 需要实例列表 + 父子关系 + 端口信息 | MIG | 但不需要自己构建 `port_to_internal` |
| 需要 `find_path` 跨模块 | PathResolver + MIG | PathResolver 从未被调用，价值待验证 |
| 需要 `port_to_internal` | CE 添加后 SignalGraph 有 | MIG 不需要再构建 |

**当前使用场景下**：MIG 的额外价值主要在 `instances` 集中索引 + 父子关系查询，不是 `port_to_internal`（因为那是给 PathResolver 用的，而 PathResolver 从未被调用）。

### 简化 MIG 的方向

如果采用 Option A（CE 添加 `port_to_internal`），MIG 可以简化为：

```
MIG（简化版）
  ├── instances dict（集中索引）→ 保留
  ├── ModuleInstanceNode.parent → 保留
  ├── ModuleInstanceNode.ports → 保留
  ├── port_to_internal → 从 SignalGraph 获取（不再自己构建）
  └── PathResolver → → 保留但标注为"未使用，待验证"
```

### 后续方向

1. **短期**: CE 添加 `port_to_internal` 输出 → SignalGraph 收集 → MIG 从 SignalGraph 获取
2. **中期**: 验证 PathResolver 是否是必要的抽象，如果是，保留；否则删除
3. **长期**: 如有统一实例数据源需求，采用 InstanceRegistry 方案

---

*最后更新: 2026-05-13 15:50（CE 添加 port_to_internal 后 MIG 的价值分析）*
