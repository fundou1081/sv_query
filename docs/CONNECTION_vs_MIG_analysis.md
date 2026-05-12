# ConnectionExtractor vs ModuleInstanceGraph 详细分析报告

**生成时间**: 2026-05-13 01:47
**状态**: 仅记录，不做决策

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
| 实例解析 | ✅ get_module_instances + get_generate_instances | ✅ get_module_instances (无 get_generate_instances) | ⚠️ 部分重复 |
| 实例路径构建 | ✅ 递归 get_path() | ⚠️ 用 parent_path 拼接，无递归路径查找 | ⚠️ 部分重复 |
| generate block 支持 | ✅ _get_generate_block_name() + gen_block 路径拼接 | ❌ 完全不支持 | ⚠️ **关键差异** |
| 端口方向获取 | ✅ all_module_ports[module_name] | ✅ _module_ports[module_name] | 重复 |
| 端口位宽获取 | ✅ all_module_widths[module_name] + 后处理推断 | ✅ extract_port_width() | 重复 |
| 边创建 | ✅ CONNECTION + DRIVER 边 | ❌ 无边概念 | ❌ **职责不同** |
| 节点创建 | ✅ INSTANTIATED_MODULE + PORT_IN/OUT | ✅ 内部有 ModuleInstanceNode 但不是 TraceNode | ⚠️ 不同抽象 |
| 端口映射表 | ❌ 无 | ✅ port_to_internal + internal_to_port | ⚠️ **关键差异** |
| 路径解析器 | ❌ 无 | ✅ PathResolver.find_path() | ❌ **职责不同** |
| 实例 → 端口连接映射 | ❌ 无 | ❌ 无 (但 comment 说要有) | ❌ 共同缺失 |

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

### 4.2 各 commit 的具体修改内容

#### commit 1: `867380b` - "fix: ConnectionExtractor 边创建修复"
```
修改内容:
- inst_module_name 获取方式: 从 inst.parent.type 获取
- all_module_ports 查找方式: module_ports = all_module_ports.get(inst_module_name, {})
- direction 判断: direction_clean = direction.strip()
- 边类型: EdgeKind.CONNECTION (原来是 DRIVER)

修改前:
  kind=EdgeKind.DRIVER

修改后:
  kind=EdgeKind.CONNECTION
```

#### commit 2: `baf0fce` - "fix: 完整模块实例化连接链"
```
修改内容:
- input 端口: 同时创建 CONNECTION 边 (外部→端口) 和 DRIVER 边 (端口→child)
- output 端口: 同时创建 CONNECTION 边 (端口→外部) 和 DRIVER 边 (child→端口)

修改前:
  无 child_signal 边

修改后:
  # input:
  result.edges.append(TraceEdge(src=外部信号, dst=inst_port, kind=CONNECTION))
  result.edges.append(TraceEdge(src=inst_port, dst=child_signal, kind=DRIVER))

  # output:
  result.edges.append(TraceEdge(src=inst_port, dst=外部信号, kind=CONNECTION))
  result.edges.append(TraceEdge(src=child_signal, dst=inst_port, kind=DRIVER))
```

#### commit 3: `c98b71f` - "fix: ConnectionExtractor 完整驱动链修复"
```
修改内容:
- 修正 DRIVER 边方向 (input 时外部→child, output 时 child→外部)
- 追溯需要: top.a -> child.d (DRIVER)

修改前 (output):
  src=inst_port, dst=child_signal  (错误)

修改后 (output):
  src=child_signal, dst=inst_port  (正确)
```

#### commit 4: `da9d49c` - "fix: ConnectionExtractor 嵌套实例化 + 多项测试"
```
修改内容:
- 第一阶段: instances_info 列表收集 (inst_module_name, inst_name, parent_module, gen_block)
- 第二阶段: module_to_path 字典 {(module, name, gen_block) -> full_path}
- 递归 get_path(info, depth=0) 函数

修改前:
  inst_path = f"top.{inst_name}"  (简单硬编码)

修改后:
  module_to_path.get(key, f"top.{inst_name}")  (动态查询)
```

#### commit 5: `ee94e98` - "fix: TimingControlExpression 解析"
```
修改内容:
- 与 ConnectionExtractor 无关，是 TimingControlExpression 的其他解析修复
```

#### commit 6: `5a98587` - "fix: 修复参数化模块实例端口未加实例前缀的bug"
```
修改内容:
- inst_module_name: inst_type_value (from inst.type.value) if inst_type_value != inst_name else inst.parent.header.name

修改前:
  inst_module_name = str(inst.parent.type).strip()

修改后:
  inst_type_value = inst.type.value.strip() if hasattr(inst.type, 'value') and inst.type.value else ''
  inst_module_name = inst_type_value if inst_type_value and inst_type_value != inst_name else self._get_parent_module_name(inst)
```

#### commit 7: `e256c62` - "fix: 修复 width=(1,0) 硬编码 bug，提取真实位宽"
```
修改内容:
- all_module_widths[module_name] = port_widths (使用 extract_port_width)
- 实例端口节点: width=port_widths.get(port_name, (1, 0))

修改前:
  width=(1, 0)

修改后:
  width=port_widths.get(port_name, (1, 0))
```

#### commit 8: `3b82c57` - "fix: Add INSTANTIATED_MODULE node kind and fix nested instance paths"
```
修改内容:
- 新增 NodeKind.INSTANTIATED_MODULE
- inst_path = module_to_path.get(key, f"top.{inst_name}")
- 修复嵌套实例路径
- 添加 instance 节点 (id=inst_path, kind=INSTANTIATED_MODULE)
- 修复方向判断: direction_clean = direction.strip()

修改前:
  inst_port_id = f"top.{inst_name}.{port_name}"
  module = f"top.{inst_name}"

修改后:
  inst_port_id = f"{inst_path}.{port_name}"
  module = inst_path
```

#### commit 9: `27985bf` - "fix: Add port width propagation and instance port driver tracing"
```
修改内容:
- CONNECTION 边也能作为 driver 的起点: top.u1.q -> top.dout
- 即: 追踪 driver 时，需要通过 CONNECTION 边传递驱动

修改前:
  无 CONNECTION 边作为 driver 源的处理

修改后:
  在 trace_drivers 中增加了对 CONNECTION 边的处理
```

#### commit 10: `229e3e1` - "fix: Infer instance port width from parent module signal width"
```
修改内容:
- 后处理: 修复实例端口位宽
- 如果实例端口位宽为 (0,0) 或 (1,0)，从 src_node.width 推断

修改后:
  for edge in result.edges:
    if edge.kind == EdgeKind.CONNECTION:
      if dst_node.width in [(0,0), (1,0)] and src_node.width != (0,0):
        更新 dst_node.width = src_node.width
```

#### commit 11: `1196bd0` - "fix: Support generate block instances in ConnectionExtractor"
```
修改内容:
- 新增 _get_parent_module_name(inst): 递归向上找 ModuleDeclarationSyntax
- 新增 _get_generate_block_name(inst): 递归向上找 GenerateBlockSyntax
- instances = get_module_instances() + get_generate_instances()
- gen_block 路径拼接: top.{gen_block}.{inst_name}

修改前:
  无 generate block 支持

修改后:
  instances = self.adapter.get_module_instances(trees) + self.adapter.get_generate_instances(trees)
  gen_block = self._get_generate_block_name(inst)
  get_path(info, depth=0)  # 包含 gen_block
```

#### commit 12: `4f0bbf0` - "fix: Add generate block container nodes and fix path calculation"
```
修改内容:
- 创建 generate block 容器节点 (top.GEN)
- gen_path = inst_path.rsplit('.', 1)[0]
- 检查是否已存在，避免重复

修改前:
  无 generate block 容器节点

修改后:
  result.nodes.append(TraceNode(
    id=gen_path, name=gen_block,
    module=gen_module,
    kind=NodeKind.GENERATE_BLOCK,
    width=(1, 0), is_port=False
  ))
```

#### commit 13: `9639d74` - "feat(P0-3): add modport_dir tracking for interface signals"
```
修改内容:
- 与 ConnectionExtractor 无关，是 modport 方向追踪
```

#### commit 14: `17957dd` - "fix: LoadExtractor MultipleConcatenation handling + orphan node guard"
```
修改内容:
- 与 ConnectionExtractor 无关，是 LoadExtractor 的修复
```

### 4.3 与 ConnectionExtractor 直接相关的 fix (11个)

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
| 10 | `1196bd0` | generate block 支持 | ❌ **MIG 完全不支持** |
| 11 | `4f0bbf0` | generate block 容器节点 | ❌ **MIG 完全不支持** |

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
  (无 get_generate_instances 调用)

处理:
  1. 遍历所有模块:
     a. _store_module_ports(module_name, node)
        - 从 header.ports 提取 {port_name: PortInfo}
  2. 递归遍历每个模块的 AST:
     a. HierarchyInstantiation → _extract_module_instantiation
        - 遍历 instances_list (HierarchicalInstance)
        - 获取 instance_name (elem.decl.name.value)
        - 构造 instance_id = {parent_path}.{instance_name}
        - 创建 ModuleInstanceNode
        - _add_instance_ports(instance_id, module_type)
     b. ContinuousAssign → _extract_port_connections (当前为空实现)
     c. 递归子节点

  3. _add_instance_ports(instance_id, module_type):
     - 从 _module_ports[module_type] 读取端口列表
     - 构建 port_to_internal: {instance_id.port: module_type.port}
     - 构建 internal_to_port: {module_type.port: instance_id.port}

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

### 7.1 直接断言 CONNECTION 边的测试

| 测试文件 | 测试方法 | 断言内容 |
|---|---|---|
| `test_instance_connection.py::test_instance_port_connection` | 验证 CONNECTION 边存在且类型正确 | `EdgeKind.CONNECTION` + `graph.get_edge('top.a', 'top.u1.d')` |
| `test_instance_connection.py::test_signal_trace_through_instance` | 验证 DRIVER 追溯通过 CONNECTION 边 | `assertIn('top.u1.q', driver_ids)` |
| `test_instance_connection.py::test_multiple_instances` | 验证多个实例的边 | CONNECTION 边检查 |

### 7.2 依赖 ModuleInstanceGraph API 的测试

| 测试文件 | 测试方法 | 使用的 API |
|---|---|---|
| `test_cross_module_tracking.py::TestModuleInstanceGraph::test_instances_exist` | `mig.instances` | `mig.instances` dict |
| `test_cross_module_tracking.py::TestModuleInstanceGraph::test_port_mapping` | `mig.get_internal_signal('top.u_dut.clk')` | `get_internal_signal()` |
| `test_cross_module_tracking.py::TestCrossModulePath::test_internal_signal_clock_edge` | 时钟边检查 | `graph.get_edge()` |
| `test_cross_module_tracking.py::TestCrossModulePath::test_path_resolution` | `path_resolver.find_path()` | `PathResolver.find_path()` |
| `test_cross_module_tracking.py::TestMultiLevelHierarchy` | 层级实例 | MIG instances + SignalGraph 边 |
| `test_cross_module_tracking.py::TestHierarchicalPort` | 层级端口 | graph.get_node() + graph.get_edge() |
| `test_cross_module_tracking.py::TestOneToMany` | 一驱多 | MIG instances + SignalGraph 边 |
| `test_cross_module_tracking.py::TestInterfaceCrossModule` | Interface 跨模块 | MIG get_internal_signal() |
| `test_cross_module_tracking.py::TestAsyncResetPropagation` | 异步复位传播 | MIG instances + SignalGraph 边 |
| `test_cross_module_tracking.py::TestMasterSlaveConnection` | 主从连接 | MIG instances + SignalGraph 边 |

### 7.3 弱断言测试 (只检查不崩溃)

| 测试文件 | 测试方法 | 断言内容 |
|---|---|---|
| `test_module_instance.py::TestModuleInstance::test_single_instance` | `result.confidence` | 只检查非空，无强断言 |
| `test_module_instance.py::TestModuleInstance::test_chained_instances` | `result.confidence` | 只检查非空 |
| `test_module_instance.py::TestModuleInstance::test_module_with_ff` | `result.confidence` | 只检查非空 |
| `test_module_instance.py::TestModuleInstance::test_empty_instance` | `confidence == 'uncertain'` | 负向测试 |

### 7.4 测试改动评估

| 场景 | 如果删除 ConnectionExtractor | 如果删除 MIG |
|---|---|---|
| `test_instance_connection.py` (3 个方法) | ❌ 失败：CONNECTION 边不存在 | ✅ 正常 (只依赖 SignalGraph) |
| `test_cross_module_tracking.py` (10+ 个方法) | ✅ 正常（MIG 独立工作） | ❌ 失败：`get_internal_signal`, `find_path` 不可用 |
| `test_module_instance.py` (5 个方法) | ✅ 正常（MIG 工作） | ⚠️ 可能失败（取决于 trace_module 实现） |
| `test_instance_hierarchy.py` (segfault) | ❌ 失败（已有 segfault） | ⚠️ 可能失败（已有 segfault） |

---

## 8. 两个系统的当前调用关系

### 8.1 调用关系图

```
unified_tracer.py::build_graph()
  ├── GraphBuilder(adapter).build()
  │   └── _extract_all_edges()
  │       ├── DriverExtractor.extract()      → EdgeKind.DRIVER, LOAD
  │       ├── LoadExtractor.extract()        → EdgeKind.LOAD
  │       ├── ConnectionExtractor.extract()  → EdgeKind.CONNECTION, DRIVER  ← 独立实现
  │       └── ClockDomainExtractor.extract() → EdgeKind.CLOCK, RESET
  │
  ├── ClassGraphBuilder.build()
  │
  ├── BitSelectHandler.process()
  │
  └── ModuleInstanceGraph(adapter).build()   ← 完全独立，互不调用  ← 独立实现

unified_tracer.py (Query Layer)
  ├── trace_module() → ModuleTracer(self._graph).trace(module)  ← 基于 SignalGraph 工作
  ├── get_internal_signal(port_path) → self._module_graph.get_internal_signal()  ← 调用 MIG
  └── find_path(src, dst) → self._path_resolver.find_path(src, dst)  ← 调用 MIG
```

### 8.2 关键发现

1. **ConnectionExtractor 和 MIG 完全独立**，互不调用
2. **ConnectionExtractor 是 GraphBuilder 的一部分**，产生的边合并到 SignalGraph
3. **MIG 独立 build**，不合并到 SignalGraph，作为独立数据结构存在
4. **Query Layer 同时访问两者**：
   - `SignalGraph` (含 ConnectionExtractor 产生的边)
   - `ModuleInstanceGraph` (port_to_internal + PathResolver)

---

## 9. 设计文档回顾

### 9.1 DESIGN_cross_module_tracking.md 描述

根据设计文档，`ModuleInstanceGraph` 的预期职责：
- 管理模块实例层级 (top.u_tb, top.u_dut)
- 维护端口到内部信号的映射 (top.u_dut.clk → dut.clk)
- 支持跨模块路径查找 (PathResolver)

**缺失的描述**：
- 设计文档没有提到 ConnectionExtractor 的存在
- 设计文档假设 MIG 是跨模块追踪的唯一数据源
- 实际上 ConnectionExtractor 也做了一部分跨模块追踪

### 9.2 架构纪律检查

| 铁律 | ConnectionExtractor | ModuleInstanceGraph |
|---|---|---|
| 铁律1: AST唯一数据源 | ⚠️ 大部分用 AST 属性，但有 `str(inst.type).strip()` 字符串转换 | ⚠️ `_extract_module_instantiation` 用 `str(inst_type).strip()` |
| 铁律4: 模型即契约 | ✅ 产生的边符合 EdgeKind 定义 | ✅ 产生的映射符合设计文档 |
| 铁律5: 原子化必须保持 | ⚠️ ConnectionExtractor 处理多种语法节点 | ✅ 每个方法职责单一 |
| 铁律14: 通过 PyslangAdapter 获取信息 | ✅ 使用 adapter 方法 | ✅ 使用 adapter 方法 |
| 铁律15: Visitor 模式 | ⚠️ 内部大量 if-elif 链处理语法类型 | ⚠️ 内部也有 if-elif 链 |
| 铁律16: 改动前评估理想实现 | ✅ 已完成两次深入分析 | ✅ 已完成两次深入分析 |

---

## 10. 未解决的问题 (记录，不决策)

1. **generate block 支持空白**: ConnectionExtractor 有完整的 gen_block 处理，MIG 完全缺失。是否需要为 MIG 补齐？

2. **两套实例解析逻辑**: ConnectionExtractor 和 MIG 都在解析模块实例化，代码重复。如何处理？

3. **MIG 不产生边**: MIG 管理端口映射但不产生 SignalGraph 边。是否需要 MIG 也产生边？

4. **ConnectionExtractor 路径和 MIG 路径的一致性**: 两者对同一实例可能产生不同的路径格式。如何保证一致？

5. **PathResolver 的必要性**: ConnectionExtractor 没有路径解析能力，MIG 有。如果合并，谁来提供路径解析？

6. **test_instance_connection.py 依赖 CONNECTION 边**: 如果删除 ConnectionExtractor，这些测试会失败。如果删除 MIG，`get_internal_signal` 等 API 不可用。是否可以重构测试？

---

## 11. 抽象角度评估

### 11.1 两个系统的本质抽象

| 系统 | 抽象本质 | 模型 |
|---|---|---|
| `ModuleInstanceGraph` | "实例结构字典" (metadata store) | `Instance → Port → InternalSignal` (静态映射表) |
| `ConnectionExtractor` | "实例端口边的生产者" (edge producer) | `Port + Direction → SignalEdge` (动态连接) |

**关键洞察**：两个系统属于不同的抽象域，不应该被视为"功能重复"。

- MIG 回答: "这个实例的某个端口对应模块内部哪个信号"
- ConnectionExtractor 回答: "外部信号怎么通过实例端口驱动内部信号"

两者是垂直分层关系，不是平行替代关系。

### 11.2 抽象合理性对比

| 维度 | `ModuleInstanceGraph` | `ConnectionExtractor` |
|---|---|---|
| **设计合理性** | ✅ 强内聚，职责边界清晰 | ❌ 职责混乱：实例解析 + 边创建耦合 |
| **长期可维护性** | ✅ 实例结构稳定，边逻辑变化频繁 | ⚠️ 14个 fix 沉淀了大量边界 case |
| **扩展性** | ✅ 任何消费者可在不修改的情况下工作 | ❌ 输出直接写入 SignalGraph，无中间抽象 |
| **PathResolver 支持** | ✅ 路径查找需要全局实例视图，MIG 天然提供 | ❌ 无路径解析能力 |
| **当前功能完整性** | ⚠️ generate block 空白 | ✅ 14个 fix + generate block + 边创建 |
| **可测试性** | ✅ 纯数据结构，可独立测试 | ⚠️ 依赖 GraphBuilder 环境 |

### 11.3 正确的分层架构（抽象视角）

```
Layer 1: 实例结构 (MIG 负责)
  - Instance + Port 元数据
  - port_to_internal / internal_to_port 映射表
  - PathResolver (全局实例视图)

Layer 2: 信号边 (Edge Producer 负责)
  - 输入: MIG 的实例结构
  - 输出: SignalGraph 的 DRIVER/CONNECTION 边
```

**当前问题**：MIG 没有向 ConnectionExtractor 提供任何东西，两者平行独立工作。

**正确设计**：ConnectionExtractor 应该接受 MIG 作为输入，而不是自己重新解析一遍实例结构。

### 11.4 理想重构方向

1. **MIG 作为基础设施**：提供唯一的实例结构解析，PathResolver 基于 MIG 工作
2. **ConnectionExtractor 改造为消费者**：不再自己解析实例，而是调用 MIG 获取实例结构，只负责边创建逻辑
3. **消除重复**：`_get_parent_module_name`、`_get_generate_block_name`、路径拼接逻辑只在 MIG 中保留一份

### 11.5 MIG 必须补齐的能力（才能成为唯一基础设施）

| 能力 | 当前状态 | 优先级 |
|---|---|---|
| generate block 支持 | ❌ 完全不支持 | 🔴 高（当前任何测试都无法覆盖 gen_block 场景的 MIG 侧） |
| 向 Edge Producer 提供实例结构 API | ❌ 无此接口 | 🔴 高 |
| get_generate_instances() 调用 | ❌ 未调用 | 🟡 中 |
| 实例节点类型与 ConnectionExtractor 对齐 | ⚠️ 轻微差异 | 🟢 低 |

### 11.6 结论

抽象上 **MIG 更合适作为跨模块追踪的基础设施**，因为：
1. 强内聚、单一职责（管理实例结构）
2. 可组合、扩展性好
3. PathResolver 天然适合在 MIG 提供的基础上工作

但 MIG 当前不完整，必须先补齐 generate block 支持，才能承担基础设施的角色。

ConnectionExtractor 的价值在于完整的边创建逻辑，这部分不应该被删除，而应该被改造为"消费 MIG 实例结构"的消费者。

---

## 12. 已确认的方向（用户决策）

> 以下内容为用户确认的后续行动方向，本文件从"仅记录不做决策"更新为"记录决策"状态。

### 12.1 第一阶段：MIG 功能补齐

**目标**：确保 MIG 功能完整，内部实现符合项目纪律。

**待补齐能力**：
| 能力 | 当前状态 | 说明 |
|---|---|---|
| generate block 支持 | ❌ 完全不支持 | ConnectionExtractor 在 1196bd0/4f0bbf0 已实现，MIG 缺失 |
| get_generate_instances() 调用 | ❌ 未调用 | 需在 `_extract_instances` 中追加 generate instances 遍历 |
| _get_generate_block_name() | ❌ 无 | 需参考 ConnectionExtractor 的实现 |
| generate block 容器节点 | ❌ 无 | 与上面同步实现 |

**纪律检查清单**：
- [ ] 铁律1: 不使用正则解析源码，全部通过 AST 属性访问
- [ ] 铁律5: 原子化保持，一个语法节点对应一个方法
- [ ] 铁律15: 避免 if-elif 链，改用结构化分发
- [ ] 铁律14: 通过 PyslangAdapter 获取信息，不直接访问 parser 属性

### 12.2 第二阶段：融合进 ConnectionExtractor

**前提**：MIG 功能补齐完成且测试通过。

**目标**：ConnectionExtractor 改为消费 MIG 的实例结构，消除重复的实例解析逻辑。

**融合步骤（待细化）**：
1. ConnectionExtractor 调用 MIG 获取实例信息（不再自己解析）
2. 保留 ConnectionExtractor 的边创建逻辑（DRIVER/CONNECTION）
3. 删除 ConnectionExtractor 中重复的 `_get_parent_module_name` 等方法
4. 验证 test_cross_module_tracking.py 和 test_instance_connection.py 全部通过

### 12.3 约束

- 两个阶段的改动都必须确保现有测试全部通过（参考铁律13/22）
- 每个 commit 必须可独立验证，不能跨越两个阶段合并
- 暂不删除任何现有实现，先补齐再考虑删除

---

*本文件记录了分析过程和用户确认的后续方向。*
*如需修改代码，请遵循 DEVELOPMENT.md 中的铁律要求。*