# ConnectionExtractor vs ModuleInstanceGraph 详细分析报告

**生成时间**: 2026-05-13 01:47
**更新**: 2026-05-13 13:18（融合评估结论 + 需求驱动架构变化分析）

---

## 状态：已完成评估，建议保持现状

经过代码审查、测试用例依赖分析、未来需求推演，结论如下：

**当前架构适合当前需求，不需要强行融合。MIG generate block 支持已补齐（commit 5c283c4）。**

---

## 1. 两个系统的概述

### 1.1 ConnectionExtractor

- **文件**: `src/trace/core/graph_builder.py` (line 1004)
- **类名**: `ConnectionExtractor`
- **职责**: 为模块实例端口创建 CONNECTION 边，建立外部信号与实例端口的连接关系
- **在 GraphBuilder 中的位置**: `GraphBuilder._extract_all_edges()` 调用
- **数据输出**: `ExtractorResult` (nodes + edges，合并到 SignalGraph)

### 1.2 ModuleInstanceGraph

- **文件**: `src/trace/core/module_instance_graph.py` (line 50)
- **类名**: `ModuleInstanceGraph`
- **职责**: 管理模块实例层级、维护端口到内部信号的映射、支持跨模块路径查找
- **在 UnifiedTracer 中的位置**: `build_graph()` 时独立 build，不合并到 SignalGraph
- **数据输出**: `instances` dict + `port_to_internal` dict + `PathResolver`

---

## 2. 两个系统的代码结构

### 2.1 ConnectionExtractor 代码结构

```
ConnectionExtractor (graph_builder.py line 1004)
├── __init__(adapter)
├── _get_parent_module_name(inst)           # 递归向上找 ModuleDeclarationSyntax
├── _get_generate_block_name(inst)           # 递归向上找 GenerateBlockSyntax
└── extract() -> ExtractorResult
    ├── 收集 all_module_ports[module_name] = {port: direction}
    ├── 收集 all_module_widths[module_name] = {port: width}
    ├── 获取 instances: get_module_instances() + get_generate_instances()
    ├── 第一阶段: 收集所有实例信息 (inst_module_name, inst_name, parent_module, gen_block)
    ├── 第二阶段: 递归构建 module_to_path {(module, name, gen_block) -> path}
    ├── 对每个实例:
    │   ├── 创建 INSTANTIATED_MODULE 节点 (inst_path)
    │   ├── 如果在 gen_block 中，创建 GENERATE_BLOCK 容器节点
    │   └── 对每个端口连接:
    │       ├── 创建 PORT_IN/PORT_OUT 节点 (inst_port_id = {path}.{port})
    │       ├── 获取端口方向和位宽
    │       └── 创建边:
    │           input:  parent_signal -> inst_port (CONNECTION)
    │                   inst_port -> child_signal (DRIVER)
    │           output: child_signal -> inst_port (DRIVER)
    │                   inst_port -> parent_signal (CONNECTION)
    └── 后处理: 修复实例端口位宽 (从父模块信号宽度推断)
```

**代码行数**:
- `ConnectionExtractor` 类: ~280 行 (line 1004 ~ 1275)
- `extract()` 方法: ~260 行 (line 1047 ~ 1270)

### 2.2 ModuleInstanceGraph 代码结构

```
ModuleInstanceGraph (module_instance_graph.py line 50)
├── __init__(adapter)
├── build(trees)
│   ├── 遍历所有模块
│   │   ├── _store_module_ports(module_name, node)  # 收集端口定义
│   │   └── _extract_instances(node, parent_path)    # 递归遍历
│   ├── _extract_instances(node, parent_path)
│   │   ├── ModuleDeclarationSyntax → 递归子节点
│   │   ├── HierarchyInstantiation → _extract_module_instantiation
│   │   └── ContinuousAssign → _extract_port_connections
│   ├── _extract_module_instantiation(node, parent_path)
│   │   ├── 获取 module_type (inst.type)
│   │   ├── 遍历 instances_list (HierarchicalInstance)
│   │   ├── 获取 instance_name (elem.decl.name.value)
│   │   ├── 构造 instance_id = {parent_path}.{instance_name}
│   │   ├── 创建 ModuleInstanceNode
│   │   └── _add_instance_ports(instance_id, module_type)
│   ├── _add_instance_ports(instance_id, module_type)
│   │   └── 从 _module_ports[module_type] 读取端口列表
│   ├── _extract_port_connections(node, parent_path)
│   │   └── (当前实现为空或简单)
│   └── _store_module_ports(module_name, node)
│       └── 从 header.ports 提取端口名、方向、位宽
├── get_internal_signal(port_path)          # port_to_internal[port_path]
├── get_port_path(internal_signal)          # internal_to_port[internal_signal]
├── get_instance(instance_id)               # instances[instance_id]
├── get_child_instances(parent_id)
├── get_all_instances()
└── PathResolver (line 483)
    ├── __init__(signal_graph, module_graph)
    ├── find_path(src, dst)                 # 递归追踪驱动源，跨模块时用 port_to_internal
    └── find_all_paths(src, dst)
```

**代码行数**:
- `ModuleInstanceGraph` 类: ~390 行 (line 57 ~ 446)
- `PathResolver` 类: ~70 行 (line 483 ~ 553)

---

## 3. 两个系统的核心功能对比

| 功能 | ConnectionExtractor | ModuleInstanceGraph | 是否重复 |
|---|---|---|---|
| 实例解析 | ✅ get_module_instances + get_generate_instances | ✅ _find_all_hierarchy_instantiations (三阶段) | ⚠️ 重复但数据源不同 |
| 实例路径构建 | ✅ get_path() 递归 | ✅ _process_module_at_path + module_to_paths | ⚠️ 重复但实现不同 |
| generate block 支持 | ✅ 完整 | ✅ 完整（commit 5c283c4） | 完全重复 |
| 端口方向/位宽收集 | ✅ 完整 | ✅ 完整 | 完全重复 |
| 边创建 | ✅ CONNECTION + DRIVER 边 | ❌ 无 | 无重复 |
| 节点创建 | ✅ INSTANTIATED_MODULE + PORT_IN/OUT | ⚠️ ModuleInstanceNode（非 TraceNode） | ⚠️ 不同抽象 |
| 端口映射表 | ❌ 无 | ✅ port_to_internal + internal_to_port | 无重复 |
| 路径解析器 | ❌ 无 | ✅ PathResolver.find_path() | 无重复 |
| 数据消费者 | SignalGraph (边) | Query Layer (映射表) | 不同 |

---

## 4. 两个系统的 14 个 fix commit 详细记录

### 4.1 提交历史

| # | Commit | 日期 | 核心修复内容 |
|---|---|---|---|
| 1 | `867380b` | 2026-05-09 | CONNECTION 边类型修正 (原 DRIVER→CONNECTION)，_get_parent_module_name 改为 inst.parent.type |
| 2 | `baf0fce` | 2026-05-09 | 同时连接 child 内部信号 ↔ 实例端口 (双向边) |
| 3 | `c98b71f` | 2026-05-09 | DRIVER/CONNECTION 方向修正：input 时 src=外部信号, dst=child信号; output 时 src=child信号, dst=外部信号 |
| 4 | `da9d49c` | 2026-05-09 | 嵌套实例路径构建：引入 get_path() 递归 + instances_info |
| 5 | `ee94e98` | 2026-05-09 | TimingControlExpression 解析修复（与连接无关，是其他 bug） |
| 6 | `5a98587` | 2026-05-09 | 参数化模块实例端口加实例前缀：inst_module_name = inst_type_value if inst_type_value != inst_name else inst.parent.header.name |
| 7 | `e256c62` | 2026-05-09 | width=(1,0) 硬编码 → extract_port_width() 获取真实位宽 |
| 8 | `3b82c57` | 2026-05-10 | INSTANTIATED_MODULE node kind + nested instance path 修复 |
| 9 | `27985bf` | 2026-05-10 | CONNECTION 边也能作为 driver 的起点 (port width propagation) |
| 10 | `229e3e1` | 2026-05-10 | 实例端口位宽从父模块信号宽度推断 (0,0) → parent_width |
| 11 | `1196bd0` | 2026-05-10 | **新增**: _get_parent_module_name() + _get_generate_block_name() + get_generate_instances() + gen_block 路径拼接 |
| 12 | `4f0bbf0` | 2026-05-10 | generate block 容器节点 + 路径修正 |
| 13 | `9639d74` | 2026-05-11 | modport_dir tracking (与连接无关) |
| 14 | `17957dd` | 2026-05-11 | LoadExtractor MultipleConcatenation handling (与连接无关) |

### 4.2 与 ConnectionExtractor 直接相关的 fix (11个)

| # | Commit | 功能领域 | 对 MIG 的影响 |
|---|---|---|---|
| 1 | `867380b` | 边类型修正 | ❌ MIG 无边 |
| 2 | `baf0fce` | 双向边创建 | ❌ MIG 无边 |
| 3 | `c98b71f` | 边方向修正 | ❌ MIG 无边 |
| 4 | `da9d49c` | 嵌套实例路径 | ⚠️ MIG 有但实现不同 |
| 5 | `5a98587` | 参数化模块实例前缀 | ⚠️ MIG 无法做到 (需知道实例化) |
| 6 | `e256c62` | 端口位宽提取 | ✅ MIG 有 extract_port_width |
| 7 | `3b82c57` | INSTANTIATED_MODULE node | ⚠️ MIG 有 instance 节点但类型不同 |
| 8 | `27985bf` | CONNECTION 边作为 driver 起点 | ❌ MIG 无边 |
| 9 | `229e3e1` | 位宽推断后处理 | ⚠️ MIG 无后处理 |
| 10 | `1196bd0` | generate block 支持 | ✅ **MIG 已补齐** (5c283c4) |
| 11 | `4f0bbf0` | generate block 容器节点 | ✅ **MIG 已补齐** (5c283c4) |

---

## 5. 两个系统的数据流

### 5.1 ConnectionExtractor 数据流

```
输入:
  - adapter.get_module_instances(trees)
  - adapter.get_generate_instances(trees)
  - adapter.get_assignments(module)
  - adapter.get_port_declarations(module)
  - adapter.extract_port_width(port)
  - adapter.clean_name(name)
  - adapter.get_instance_connection(inst)

处理:
  1. 收集 all_module_ports[module_name] = {port_name: direction}
  2. 收集 all_module_widths[module_name] = {port_name: width}
  3. 获取 instances (module + generate)
  4. 收集 instances_info = [{inst_module_name, inst_name, parent_module, gen_block}, ...]
  5. 构建 module_to_path = {(module, name, gen_block): path}
  6. 对每个 instance:
     a. 创建 INSTANTIATED_MODULE 节点
     b. 如果 gen_block: 创建 GENERATE_BLOCK 节点
     c. 对每个端口连接 (named_conns):
        - 获取方向 direction_clean
        - 创建 PORT_IN/PORT_OUT 节点 (inst_port_id)
        - 创建边 (CONNECTION + DRIVER)
  7. 后处理: 推断实例端口位宽

输出:
  - nodes: INSTANTIATED_MODULE, GENERATE_BLOCK, PORT_IN, PORT_OUT
  - edges: CONNECTION (外部↔端口), DRIVER (child↔端口)
```

### 5.2 ModuleInstanceGraph 数据流

```
输入:
  - adapter.get_modules()
  - adapter.get_port_declarations(module)
  - adapter.get_module_instances(trees)
  - adapter.extract_port_width(port)

处理:
  三阶段 build():
  Phase 0: 遍历所有模块，存储端口定义，建立 _module_ast_cache
  Phase 1: _find_all_hierarchy_instantiations 全树遍历，收集所有 {module_type, inst_name, instance_path}
  Phase 2: 建立 module_to_paths 映射 {module_type: [instance_paths]}
  Phase 3: 对每个模块，在其所有实例路径上调用 _process_module_at_path

  _process_module_at_path(module_node, base_path, module_to_paths):
    - 遍历模块成员（LoopGenerate/IfGenerate/CaseGenerate/GenerateRegion/HierarchyInstantiation）
    - HierarchyInstantiation → _extract_module_instantiation
    - 如果被实例化的模块自身还有子实例，递归处理

输出:
  - instances: {instance_id: ModuleInstanceNode}
  - port_to_internal: {port_path: internal_signal}
  - internal_to_port: {internal_signal: port_path}
  - _module_ports: {module_name: {port_name: PortInfo}}
```

---

## 6. 两个系统的 Node/Edge 类型

### 6.1 ConnectionExtractor 创建的节点

| NodeKind | ID 格式 | 示例 | 说明 |
|---|---|---|---|
| `INSTANTIATED_MODULE` | `{path}` | `top.u_dut` | 实例父节点 |
| `GENERATE_BLOCK` (if exists) | `{path}` | `top.GEN` | generate block 容器 |
| `PORT_IN` | `{path}.{port}` | `top.u_dut.clk` | input 端口 |
| `PORT_OUT` | `{path}.{port}` | `top.u_dut.q` | output 端口 |
| `PORT_INOUT` | `{path}.{port}` | - | bidir 端口 |

### 6.2 ConnectionExtractor 创建的边

| EdgeKind | 方向 | 条件 | assign_type |
|---|---|---|---|
| `CONNECTION` | 外部信号 → 实例端口 | direction == 'input' | "connection" |
| `DRIVER` | 实例端口 → child 信号 | direction == 'input' | "internal" |
| `CONNECTION` | 实例端口 → 外部信号 | direction == 'output' | "connection" |
| `DRIVER` | child 信号 → 实例端口 | direction == 'output' | "internal" |

### 6.3 ModuleInstanceGraph 创建的节点

| 类型 | ID 格式 | 说明 |
|---|---|---|
| `ModuleInstanceNode` (非 TraceNode) | `{parent_path}.{inst_name}` | 实例节点，有 ports dict |

### 6.4 ModuleInstanceGraph 的端口映射

| 映射 | key | value | 示例 |
|---|---|---|---|
| `port_to_internal` | 实例端口路径 | 模块内部信号 | `top.u_dut.clk` → `dut.clk` |
| `internal_to_port` | 模块内部信号 | 实例端口路径 | `dut.clk` → `top.u_dut.clk` |

---

## 7. 测试用例影响

### 7.1 直接断言 CONNECTION 边的测试（仅由 ConnectionExtractor 提供）

| 测试文件 | 测试方法 | 断言内容 |
|---|---|---|
| `test_instance_connection.py::test_instance_port_connection` | 验证 CONNECTION 边存在且类型正确 | `EdgeKind.CONNECTION` + `graph.get_edge('top.a', 'top.u1.d')` |
| `test_instance_connection.py::test_signal_trace_through_instance` | 验证 DRIVER 追溯通过 CONNECTION 边 | `assertIn('top.u1.q', driver_ids)` |
| `test_instance_connection.py::test_multiple_instances` | 验证多个实例的边 | CONNECTION 边检查 |

### 7.2 依赖 ModuleInstanceGraph API 的测试（仅由 MIG 提供）

| 测试文件 | 测试方法 | 使用的 API |
|---|---|---|
| `test_mig_generate_block.py` (7个) | `mig.instances`, `mig.port_to_internal`, `get_internal_signal()` | 全部 MIG API |
| `test_cross_module_tracking.py::TestModuleInstanceGraph` | `mig.instances`, `mig.port_to_internal` | MIG 数据结构 |
| `test_cross_module_tracking.py::TestCrossModulePath` | `path_resolver.find_path()` | PathResolver |
| `test_cross_module_tracking.py::TestHierarchicalPort` | `mig.get_internal_signal()` | MIG 映射表 |

### 7.3 两者都依赖的测试

| 测试 | 依赖什么 |
|------|---------|
| `test_instance_hierarchy.py` | Graph 节点（含 CE 产生的）+ MIG 实例路径 |
| `test_cross_module_tracking.py` 部分方法 | SignalGraph 边（CE）+ MIG 映射（都有） |

### 7.4 测试改动评估

| 场景 | 如果删除 ConnectionExtractor | 如果删除 MIG |
|---|---|---|
| `test_instance_connection.py` (3 个方法) | ❌ 失败：CONNECTION 边不存在 | ✅ 正常（只依赖 SignalGraph） |
| `test_mig_generate_block.py` (7 个方法) | ✅ 正常（MIG 独立工作） | ❌ 失败：`port_to_internal`, `get_internal_signal` 不可用 |
| `test_cross_module_tracking.py` (10+ 个方法) | ✅ 正常（MIG 独立工作） | ❌ 失败：`get_internal_signal`, `find_path` 不可用 |
| `test_instance_hierarchy.py` (6 个方法) | ✅ 正常 | ✅ 正常（MIG 已修复 nested instance） |

---

## 8. 当前调用关系

```
unified_tracer.py::build_graph()
  ├── GraphBuilder(adapter).build()
  │   └── _extract_all_edges()
  │       ├── DriverExtractor.extract()      → EdgeKind.DRIVER, LOAD
  │       ├── LoadExtractor.extract()        → EdgeKind.LOAD
  │       ├── ConnectionExtractor.extract()  → EdgeKind.CONNECTION, DRIVER
  │       └── ClockDomainExtractor.extract() → EdgeKind.CLOCK, RESET
  │
  ├── ClassGraphBuilder.build()
  │
  ├── BitSelectHandler.process()
  │
  └── ModuleInstanceGraph(adapter).build()   ← 完全独立，互不调用

unified_tracer.py (Query Layer)
  ├── trace_module() → ModuleTracer(self._graph)  ← 基于 SignalGraph 工作
  ├── get_internal_signal(port_path) → self._module_graph.get_internal_signal()  ← 调用 MIG
  └── find_path(src, dst) → self._path_resolver.find_path(src, dst)  ← 调用 MIG
```

**关键发现**：ConnectionExtractor 和 MIG 完全独立，互不调用。属于"同一信息源（AST）被两个消费者独立解析"的模式。

---

## 9. 融合评估结论（2026-05-13）

### 9.1 代码重复分析

| 功能 | ConnectionExtractor | MIG | 重复程度 |
|------|---------------------|-----|---------|
| 实例解析（遍历 HierarchyInstantiation） | ✅ 完整 | ✅ 完整 | **完全重复** |
| 嵌套实例路径构建 | ✅ `get_path()` 递归 | ✅ `_process_module_at_path` | **完全重复** |
| generate block 支持 | ✅ 完整 | ✅ 完整（已修复） | 完全重复 |
| 端口方向/位宽收集 | ✅ 完整 | ✅ 完整 | 完全重复 |
| 边创建 | ✅ CONNECTION/DRIVER | ❌ 无 | 无重复 |
| 端口映射表 | ❌ 无 | ✅ `port_to_internal` | 无重复 |
| PathResolver | ❌ 无 | ✅ `find_path()` | 无重复 |

### 9.2 两个系统的本质抽象

| 系统 | 抽象本质 | 模型 |
|---|---|---|
| `ModuleInstanceGraph` | "实例结构字典" (metadata store) | `Instance → Port → InternalSignal` (静态映射表) |
| `ConnectionExtractor` | "实例端口边的生产者" (edge producer) | `Port + Direction → SignalEdge` (动态连接) |

**核心洞察**：两个系统属于不同的抽象域，不应该被视为"功能重复"。

- MIG 回答: "这个实例的某个端口对应模块内部哪个信号"
- ConnectionExtractor 回答: "外部信号怎么通过实例端口驱动内部信号"

两者是垂直分层关系，不是平行替代关系。

### 9.3 更理想的方案

```
InstanceRegistry（单一数据源）
├── 收集所有模块实例（HierarchyInstantiation + generate instances）
├── 构建 instance_path (支持嵌套 + generate block)
├── 提供 resolve_path() 查询
└── 提供 get_instance_info() 元数据

CE (Consumer A) → 消费 InstanceRegistry，创建 CONNECTION/DRIVER 边
MIG (Consumer B) → 消费 InstanceRegistry，构建端口映射 + PathResolver
```

**核心思想**：一次解析，多方消费。

### 9.4 会导致架构大变化的需求

经过推演，以下 5 个需求会对融合后的架构产生重大冲击：

#### 1. 接口信号（interface/modport）作为端口类型

当前模型：端口是标量或向量。

如果 `top.u_fifo.read_data` 是一个 32bit 接口信号束，需要结构化数据：

```python
# 未来需要
port_to_internal['top.u_fifo.read_data'] = {
    'type': 'interface',
    'bundle': 'fifo.read_data',
    'signals': ['fifo.read_data[0]', ..., 'fifo.read_data[31]']
}
```

**影响**：MIG 的 `port_to_internal` 需要变成结构化数据，PathResolver 需要理解接口的内部结构。CE 和 MIG 都需要修改，但修改方向不同。

#### 2. 动态实例层级（genvar 展开 + 条件 generate）

当前行为：genvar 不展开，产生模板实例 `top.GEN.u_dut`。

如果需要**实际展开**的实例（从仿真器/SLint 获取每个 genvar 迭代的具体实例）：

```systemverilog
generate
  for (i=0; i<2; i=i+1) begin : GEN
    dut u_dut();  // 想要 top.GEN[0].u_dut 和 top.GEN[1].u_dut
  end
endgenerate
```

**影响**：这会彻底改变 MIG 的 `instances` 结构（从模板 → 展开列表），CE 也需要相应变化。**架构冲击极大**。

#### 3. 参数化模块的动态内容

```systemverilog
module buffer #(parameter WIDTH = 8) (...);
  logic [WIDTH-1:0] fifo;  // 位宽取决于参数
endmodule

buffer #(.WIDTH(16)) u_buf();  // 实例化时 WIDTH=16
buffer #(.WIDTH(8)) u_buf2();   // 同一个模块类型，不同参数
```

如果 `get_internal_signal('top.u_buf.fifo')` 需要返回 `buffer_16.fifo[15:0]`，MIG 需要跟踪参数化实例的具体参数。

**影响**：MIG 的 `port_to_internal` 需要参数化，`_module_ports` 需要按实例具体化。

#### 4. 多驱动 resolve 和 timing annotation

如果需要在 SignalGraph 上标注 timing/switching 信息：

```python
edge.annotate(timing_ns=2.5, drive_strength='STRONG')
```

**影响**：CE 的边模型需要扩展，PathResolver 需要理解 timing。**中等冲击**。

#### 5. 跨时钟域路径追踪

如果需要追踪 `top.clk_a` → `top.u1.q` → `top.clk_b` 的跨时钟域路径，需要知道：
- 哪些信号是时钟
- 从哪个时钟域到哪个时钟域
- CDC-safe vs CDC-unsafe 判定

**影响**：PathResolver 需要扩展为 `ClockDomainResolver`。**中等冲击**。

### 9.5 这些需求的优先级

| 需求 | 当前支持 | 架构冲击 | 优先级 |
|------|---------|---------|--------|
| 接口信号 | ❌ 无 | 高（需要结构化 port） | 低（接口用得少） |
| genvar 展开 | ❌ 无 | 极高（改变 instance 模型） | 低（模板已够用） |
| 参数化实例 | ⚠️ 有限 | 高（需要实例级参数） | 中（当前设计够用） |
| timing annotation | ❌ 无 | 中（Edge 扩展） | 低（仿真前不需要） |
| CDC 分析 | ❌ 无 | 中（PathResolver 扩展） | 低（仿真前不需要） |

### 9.6 融合价值评估

**结论**：即便融合了，未来的主要变化来源（接口信号、参数化展开）都会同时冲击两个 consumer，融合不能减少这些变化。

融合的价值有限：
- Pros: 消除重复解析，路径逻辑统一
- Cons: MIG 出问题会影响 CE，耦合增加
- 风险: 当前 MIG 已稳定，风险低；但融合后新需求来临时两者会同时变

### 9.7 最终建议

**保持现状，暂不融合。**

理由：
1. 两个系统各自承担不可替代的职责，删除任何一个都会导致部分测试彻底失败
2. 未来的主要变化来源会同时冲击两个 consumer，融合不能减少变化
3. MIG generate block 支持已补齐（5c283c4），功能完整
4. 保持现状让两者完全解耦，一个挂了另一个继续工作
5. segfault 问题（base.py find_inst）需要单独处理，与融合无关

---

## 10. 后续行动

| 优先级 | 行动 | 说明 |
|--------|------|------|
| 🔴 高 | 修 segfault（base.py find_inst） | test_find_connected_modules 的 segfault 阻塞测试套件完整运行 |
| 🟡 中 | 观察期 | 保持现状，3-6 个月后重新评估 |
| 🟢 低 | 文档同步 | 更新 DESIGN_cross_module_tracking.md，增加 ConnectionExtractor 的描述 |

---

## 11. 未解决的问题（记录）

1. **segfault**: `base.py:598 find_inst` 递归导致的 segfault，暂时只能规避
2. **ConnectionExtractor 路径和 MIG 路径的一致性**: 两者对同一实例可能产生不同的路径格式（需要对比验证）
3. **Design 文档不完整**: DESIGN_cross_module_tracking.md 没有提到 ConnectionExtractor 的存在

---

*本文件记录了分析过程和评估结论。*
*最后更新: 2026-05-13 13:18（融合评估 + 需求驱动变化分析）*
---

## 12. 功能重叠分析：base.py vs MIG

### 12.1 重叠概览

`base.py` 的 `PyslangAdapter` 和 `ModuleInstanceGraph` 在实例发现功能上存在**完全重叠**：

| 功能 | `base.py get_module_instances()` | `MIG _find_all_hierarchy_instantiations()` |
|---|---|---|
| 发现 HierarchyInstantiation | ✅ | ✅ |
| 构建嵌套实例路径 | ❌ CE 自己用 `get_path()` 递归构建 | ✅ 遍历时直接构建 |
| 处理 LoopGenerate | ❌（需配合 `get_generate_instances()`） | ✅ |
| 处理 IfGenerate | ❌（需配合 `get_generate_instances()`） | ✅ |
| 处理 CaseGenerate | ❌ | ✅ |

### 12.2 关键区别

#### base.py 的实现

```python
# base.py:563 - get_module_instances()
def find_inst(node, depth=0):
    # 遍历找 HierarchyInstantiation 节点
    # 但不进入 generate block 内部（需要单独的 get_generate_instances()）
    ...

# base.py:609 - get_generate_instances()
def walk(node, depth=0):
    # 单独处理 generate block 中的实例
    # LoopGenerate, IfGenerate 的 block.members 被遍历
    # 不处理 CaseGenerate
```

**输出**: `List[HierarchyInstantiation AST节点]` — 原始 AST，需要 CE 进一步处理

#### MIG 的实现

```python
# module_instance_graph.py:183 - _find_all_hierarchy_instantiations()
def _find_all_hierarchy_instantiations(self, node, result_list, parent_path=''):
    # 统一遍历：ModuleDeclaration → HierarchyInstantiation
    # LoopGenerate / IfGenerate / CaseGenerate 全部内置处理
    # 在遍历时直接构建 instance_path
```

**输出**: `List[{module_type, inst_name, instance_path}]` — 结构化信息

### 12.3 CE 的路径构建（在 graph_builder.py:1068-1085）

CE 在拿到 AST 节点后，自己维护了一套路径构建逻辑：

```python
def get_path(info, depth=0):
    """递归获取实例的完整路径"""
    if depth > 20:
        return f"top.{info['inst_name']}"
    parent_mod = info['parent_module']
    gen_block = info.get('gen_block')
    if parent_mod == 'top':
        return f"top.{gen_block}.{info['inst_name']}" if gen_block else f"top.{info['inst_name']}"
    else:
        # 递归向上找父模块
        for other_info in instances_info:
            if other_info['inst_module_name'] == parent_mod:
                parent_path = get_path(other_info, depth+1)
                return f"{parent_path}.{gen_block}.{info['inst_name']}" if gen_block else f"{parent_path}.{info['inst_name']}"
```

这和 MIG 的路径构建**完全重复**。

### 12.4 调用链

```
graph_builder.py:ConnectionExtractor.extract()
  └── adapter.get_module_instances(trees)        ← base.py（返回 AST 节点）
      + adapter.get_generate_instances(trees)   ← base.py（返回 AST 节点）
  └── 自己调用 _get_parent_module_name() 构建路径

unified_tracer.py:UnifiedTracer.build()
  └── mig.build(trees)
      └── _find_all_hierarchy_instantiations()  ← MIG（返回结构化信息）
```

### 12.5 为什么重复

两个系统**独立演进**：
- `base.py get_module_instances()` 是 ConnectionExtractor 的辅助函数，最初只为 CE 建边服务
- `MIG _find_all_hierarchy_instantiations()` 是 MIG 自己需要收集实例信息来构建端口映射

它们服务于不同目的，但都在做同样的**实例发现**工作。

### 12.6 消除重复的方案

**方案：统一实例发现接口**

```python
# base.py
def get_all_instances(trees) -> List[InstanceInfo]:
    """统一的实例发现接口，返回结构化信息"""
    # 合并 get_module_instances + get_generate_instances + generate block 处理
    # 输出: [{module_type, inst_name, instance_path, parent_module, gen_block}]

# 使用方：
CE: inst_info = adapter.get_all_instances(trees)  # 替代原来的 get_module_instances + get_generate_instances
generate_path = inst_info.instance_path  # 替代 CE 自己的 get_path() 逻辑

MIG: 直接用 MIG 自己的一套（或者也切换到 get_all_instances）
```

**代价**：
- 需要重构 `ConnectionExtractor.extract()` 中的路径构建逻辑（约 60 行）
- 需要保持向后兼容，不能破坏现有 API

**结论**：重叠是事实，但不影响功能。当前不建议重构，除非有明确需求驱动。

---

*本文件记录了分析过程和评估结论。*
*最后更新: 2026-05-13 14:34（功能重叠分析）*
