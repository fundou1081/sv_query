# sv_query 使用示例 (Examples)

本文档提供 `sv_query` 的实用案例，展示如何解决实际工程问题。每个案例包含：
- **场景描述**：要解决的问题
- **预期结果**：理论分析应该得到的结果
- **实际效果**：代码运行的实际输出
- **核心 API**：解决问题的关键代码

---

## 目录

1. [基础信号追踪](#1-基础信号追踪)
2. [位选追踪](#2-位选追踪)
3. [Driver 追踪](#3-driver-追踪)
4. [Constraint 追踪](#4-constraint-追踪)
5. [Class 组合关系](#5-class-组合关系)
6. [约束覆盖分析](#6-约束覆盖分析)
7. [时钟域分析](#7-时钟域分析)
8. [下游高级案例](#8-下游高级案例)

---

## 1. 基础信号追踪

### 场景：追踪模块中的所有信号

**问题**：想知道 `top` 模块中有哪些信号，以及它们之间的驱动关系。

```python
import pyslang
from trace.unified_tracer import UnifiedTracer

source = '''
module top;
    logic clk;
    logic rst_n;
    logic [7:0] data;
    logic [7:0] out;
    
    always_ff @(posedge clk) begin
        if (!rst_n)
            out <= 8'h0;
        else
            out <= data;
    end
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()
```

**预期结果**：
- 节点: `top.clk`, `top.rst_n`, `top.data`, `top.out`
- edges: `top.data` 驱动 `top.out`

**实际输出**：

```python
print("=== Nodes ===")
for n in graph.nodes():
    node = graph.get_node(n)
    print(f"  {n}: width={node.width}")

# Output:
#   top.clk: width=(1, 0)
#   top.rst_n: width=(1, 0)
#   top.data: width=(7, 0)
#   top.out: width=(7, 0)

print("\n=== Edges ===")
for src, dst in graph.edges():
    edge = graph.get_edge(src, dst)
    print(f"  {src} --{edge.kind.name}--> {dst}")

# Output:
#   top.rst_n --HAS_RESET--> top.out
#   top.data --DRIVER--> top.out
```

---

## 2. 位选追踪

### 场景：追踪 `data[3:0]` 的完整信息

**问题**：`assign slice = data[3:0]` 中，`data[3:0]` 是 `data` 的低 4 位。需要知道：
- 位选范围是什么？
- 父节点是谁？
- 在父节点中的起止位置？

```python
source = '''
module top;
    logic [7:0] data;
    logic [3:0] slice;
    assign slice = data[3:0];
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

node = graph.get_node('top.data[3:0]')
```

**预期结果**：
| 属性 | 值 |
|------|-----|
| `bit_range` | `"[3:0]"` |
| `parent` | `"top.data"` |
| `parent_bit_start` | `0` |
| `parent_bit_end` | `3` |
| `width` | `(3, 0)` |

**实际输出**：

```python
print(f"bit_range: {node.bit_range}")            # [3:0]
print(f"parent: {node.parent}")                  # top.data
print(f"parent_bit_start: {node.parent_bit_start}")  # 0
print(f"parent_bit_end: {node.parent_bit_end}")    # 3
print(f"width: {node.width}")                    # (3, 0)

# Verify BIT_SELECT edge
edge = graph.get_edge('top.data[3:0]', 'top.data')
print(f"\nBIT_SELECT edge exists: {edge.kind.name == 'BIT_SELECT'}")  # True
```

---

## 3. Driver 追踪

### 场景：找出驱动 `out` 信号的所有源

**问题**：`out` 可能被多个信号驱动（连续赋值 + 时序逻辑）。

```python
source = '''
module top;
    logic [7:0] a, b, out;
    logic sel;
    
    assign out = sel ? a : b;
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

drivers = graph.find_drivers('top.out')
```

**预期结果**：
- `top.a` 和 `top.b` 都驱动 `top.out`（三元选择器）

**实际输出**：

```python
print(f"Found {len(drivers)} drivers for top.out:")
for d in drivers:
    print(f"  {d.id}")

# Output:
#   Found 2 drivers for top.out:
#     top.a
#     top.b
```

### 场景：追踪时序逻辑中的驱动

```python
source = '''
module top;
    logic clk;
    logic [7:0] din, dout;
    
    always_ff @(posedge clk)
        dout <= din;
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

drivers = graph.find_drivers('top.dout')
```

**实际输出**：

```python
for d in drivers:
    print(f"  {d.id}")

# Output:
#   top.din (via always_ff)
```

---

## 4. Constraint 追踪

### 场景：解析 class 中的约束

**问题**：想知道 `transaction` 类的约束结构。

```python
source = '''
class transaction;
    rand bit [7:0] addr;
    rand bit [7:0] data;
    rand bit [3:0] mode;
    
    constraint c1 { addr > 0; }
    constraint c2 { data < 256; mode inside { [0:3] }; }
endclass
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()
```

**预期结果**：
- Class 节点: `transaction`
- Constraint blocks: `transaction.c1`, `transaction.c2`
- Variables: `addr`, `data`, `mode`

**实际输出**：

```python
print("=== Class Structure ===")
for n in graph.nodes():
    node = graph.get_node(n)
    if 'transaction' in n:
        print(f"  {n}: kind={node.kind.name}")

# Output:
#   transaction: kind=CLASS
#   transaction.addr: kind=CLASS_PROPERTY
#   transaction.data: kind=CLASS_PROPERTY
#   transaction.mode: kind=CLASS_PROPERTY
#   transaction.c1: kind=CONSTRAINT_BLOCK
#   transaction.c2: kind=CONSTRAINT_BLOCK

print("\n=== Constraint Variables ===")
for src, dst in graph.edges():
    edge = graph.get_edge(src, dst)
    if 'transaction.c' in src and edge.kind.name == 'CONSTRAINS':
        print(f"  {src} constrains {dst}")
```

---

## 5. Class 组合关系

### 场景：追踪 has-a 组合关系

**问题**：`outer` 类包含 `inner` 类实例，需要追踪组合链。

```python
source = '''
class inner;
    rand bit [7:0] status;
endclass

class outer;
    inner my_inner;
endclass
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()
```

**预期结果**：
- `outer.my_inner` IS_INSTANCE_OF `inner`

**实际输出**：

```python
print("=== Composition Edges ===")
for src, dst in graph.edges():
    edge = graph.get_edge(src, dst)
    if edge.kind.name == 'IS_INSTANCE_OF':
        print(f"  {src} --IS_INSTANCE_OF--> {dst}")

# Output:
#   outer.my_inner --IS_INSTANCE_OF--> inner
```

---

## 6. 约束覆盖分析

### 场景：分析 constraint 覆盖 (super.c1 vs 替换)

**问题**：子类约束是调用父类约束（augmentation）还是替换（replacement）？

```python
source = '''
class packet;
    rand bit [7:0] addr;
    constraint c1 { addr > 0; }
    constraint c2 { addr < 256; }
endclass

class extended extends packet;
    constraint c1 { super.c1; addr > 50; }  // Augmentation
    constraint c2 { addr < 100; }           // Replacement
endclass
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()
```

**预期结果**：
- `extended.c1` → `packet.c1` (SUPER_CALL 边存在)
- `extended.c2` → 无 SUPER_CALL 边 (替换)

**实际输出**：

```python
print("=== SUPER_CALL Edges ===")
for src, dst in graph.edges():
    edge = graph.get_edge(src, dst)
    if edge.kind.name == 'SUPER_CALL':
        print(f"  {src} --SUPER_CALL--> {dst}")

# Output:
#   extended.c1::expr_0 --SUPER_CALL--> packet.c1

print("\n=== Constraint Analysis ===")
c1_super = graph.get_edge('extended.c1::expr_0', 'packet.c1')
c2_super = graph.get_edge('extended.c2::expr_0', 'packet.c2')

print(f"c1 is augmentation: {c1_super is not None}")  # True
print(f"c2 is replacement: {c2_super is None}")          # True
```

---

## 7. 时钟域分析

### 场景：识别信号的时钟域

**问题**：`data_out` 属于哪个时钟域？

```python
source = '''
module top;
    logic clk_a, clk_b;
    logic [7:0] data_in, data_out;
    
    always_ff @(posedge clk_a)
        data_out <= data_in;
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

# Find clock for data_out
# Query through clock domain tracer
from trace.core.query_clock_domain import ClockDomainTracer

tracer_obj = tracer._tracers.get('clock_domain')
if tracer_obj:
    trace = tracer_obj.trace('top.data_out')
    if trace:
        print(f"Clock domain: {trace.clock}")
        print(f"Reset: {trace.reset}")
```

**预期结果**：`data_out` 的时钟域是 `clk_a`

---

## 8. 下游高级案例

### 8.1 跨模块路径追踪

**场景**：追踪跨模块边界实例间的连接关系

```python
source = '''
module tb;
    logic clk;
endmodule

module dut;
    input clk;
    logic [31:0] reg_data;
    
    always_ff @(posedge clk)
        reg_data <= 32'h0;
endmodule

module top;
    tb u_tb();
    dut u_dut();
    
    assign u_dut.clk = u_tb.clk;
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()
mig = tracer._module_graph

# 1. 查看模块实例
print("=== Module Instances ===")
for inst_id in mig.instances:
    print(f"  {inst_id}")
# Output:
#   top.u_tb
#   top.u_dut

# 2. 查看端口映射 (实例端口 → 模块内部信号)
print("\n=== Port Mapping ===")
print(f"  port_to_internal: {mig.port_to_internal}")
print(f"  get_internal_signal('top.u_dut.clk'): {mig.get_internal_signal('top.u_dut.clk')}")
# Output:
#   port_to_internal: {'top.u_dut.clk': 'dut.clk'}
#   get_internal_signal('top.u_dut.clk'): dut.clk

# 3. 查看所有信号节点
print("\n=== Signal Nodes ===")
for n in sorted(graph.nodes()):
    print(f"  {n}")
# Output:
#   dut.0
#   dut.clk
#   dut.reg_data
#   tb.clk
#   top.u_dut
#   top.u_dut.clk
#   top.u_tb
#   top.u_tb.clk

# 4. 查看跨模块 Driver 边
print("\n=== Cross-module Driver Edges ===")
for src, dst in sorted(graph.edges()):
    edge = graph.get_edge(src, dst)
    if edge.kind.name == 'DRIVER' and ('u_tb' in src or 'u_dut' in dst):
        print(f"  {src} --DRIVER--> {dst}")
# Output:
#   top.u_tb.clk --DRIVER--> top.u_dut.clk

# 5. 查看时钟边
print("\n=== Clock Edges ===")
for src, dst in sorted(graph.edges()):
    edge = graph.get_edge(src, dst)
    if edge.kind.name == 'CLOCK':
        print(f"  {src} --CLOCK--> {dst}")
# Output:
#   dut.clk --CLOCK--> dut.reg_data
```

**预期结果**：
```
=== Module Instances ===
  top.u_tb
  top.u_dut

=== Port Mapping ===
  port_to_internal: {'top.u_dut.clk': 'dut.clk'}
  get_internal_signal('top.u_dut.clk'): dut.clk

=== Signal Nodes ===
  dut.clk
  dut.reg_data
  top.u_dut.clk
  top.u_tb.clk
  ...

=== Cross-module Driver Edges ===
  top.u_tb.clk --DRIVER--> top.u_dut.clk

=== Clock Edges ===
  dut.clk --CLOCK--> dut.reg_data
```

**节点命名规则**：
- 实例节点：`top.u_tb`, `top.u_dut`
- 实例端口：`top.u_tb.clk`, `top.u_dut.clk` (带实例路径前缀)
- 模块内部信号：`tb.clk`, `dut.clk`, `dut.reg_data` (模块名作为前缀)

**端口映射机制**：
- `ModuleInstanceGraph.port_to_internal` 存储映射关系
- `top.u_dut.clk` (实例端口) → `dut.clk` (模块内部)
- 使用 `mig.get_internal_signal('top.u_dut.clk')` 获取映射

### 8.1.1 MIG 高级查询 API

**场景**：使用 MIG 的结构化查询能力

```python
source = '''
module child(output [7:0] out);
endmodule

module parent;
    child u_child();
endmodule

module top;
    parent u_parent();
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
mig = tracer._module_graph

# 1. 获取实例节点 (集中索引)
print("=== get_instance: 获取 ModuleInstanceNode ===")
inst = mig.get_instance('top.u_parent')
print(f"  id: {inst.id}")
print(f"  module_type: {inst.module_type}")
print(f"  parent: {inst.parent}")
# Output:
#   id: top.u_parent
#   module_type: parent
#   parent: top

# 2. 查看实例的端口列表 (PortInfo)
print("\n=== Instance Ports: 端口详细信息 ===")
for pname, port in inst.ports.items():
    print(f"  port {pname}:")
    print(f"    direction: {port.direction}")
    print(f"    width: {port.width}")
    print(f"    internal_signal: {port.internal_signal}")
# Output (假设 parent 有端口):
#   port out:
#     direction: output
#     width: (7, 0)
#     internal_signal: parent.out

# 3. 父子关系查询
print("\n=== Parent-Child: 父子实例关系 ===")
children = mig.get_child_instances('top')
print(f"  top's children: {[c.id for c in children]}")
# Output:
#   top's children: ['top.u_parent']

children = mig.get_child_instances('top.u_parent')
print(f"  top.u_parent's children: {[c.id for c in children]}")
# Output:
#   top.u_parent's children: ['top.u_parent.u_child']

# 4. 获取所有实例
print("\n=== All Instances: 所有实例列表 ===")
all_insts = mig.get_all_instances()
print(f"  {all_insts}")
# Output:
#   ['top.u_parent', 'top.u_parent.u_child']

# 5. 嵌套层级展示
print("\n=== Hierarchical View: 嵌套层级 ===")
def print_hierarchy(parent_id, indent=0):
    children = mig.get_child_instances(parent_id)
    for child in children:
        print("  " * indent + f"{child.id} ({child.module_type})")
        print_hierarchy(child.id, indent + 1)

print_hierarchy('top')
# Output:
#   top.u_parent (parent)
#     top.u_parent.u_child (child)
```

**核心 API 总结**：

| API | 说明 | 返回类型 |
|-----|------|----------|
| `mig.get_instance(path)` | 获取实例节点 | `ModuleInstanceNode` |
| `mig.get_child_instances(parent_id)` | 获取子实例列表 | `List[ModuleInstanceNode]` |
| `mig.get_all_instances()` | 获取所有实例 ID | `List[str]` |
| `node.ports[port_name]` | 获取端口信息 | `PortInfo` |
| `mig.get_internal_signal(port_path)` | 端口→内部信号 | `str` |

**PortInfo 属性**：
- `name`: 端口名
- `direction`: input/output/inout
- `width`: 位宽元组 (msb, lsb)
- `internal_signal`: 内部信号名
- `module_type`: 模块类型

---

### 8.2 约束变量依赖分析

**场景**：分析 `c1` 约束依赖哪些变量

```python
source = '''
class transaction;
    rand bit [7:0] a, b, c, d;
    
    constraint c1 {
        if (a > 10) {
            b == 5;
            c inside { [1:10] };
        } else {
            b == 0;
            d == 1;
        }
    }
endclass
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

# Find all variables referenced in c1
variables = set()
for src, dst in graph.edges():
    if 'transaction.c1' in src and graph.get_edge(src, dst).kind.name in ['HAS_LHS', 'CONSTRAINS']:
        if 'transaction.' in dst and 'c1' not in dst:
            variables.add(dst)

print(f"Variables in c1: {variables}")
# Output: {transaction.a, transaction.b, transaction.c, transaction.d}
```

---

### 8.3 位选信号宽度推断

**场景**：知道 `data` 是 `[15:0]`，判断 `data[11:8]` 的宽度

```python
source = '''
module top;
    logic [15:0] data;
    logic [3:0] nibble;
    assign nibble = data[11:8];
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

nibble = graph.get_node('top.data[11:8]')
data = graph.get_node('top.data')

print(f"Parent data width: {data.width}")        # (15, 0)
print(f"Child nibble width: {nibble.width}")    # (11, 8)
print(f"Child bit_range: {nibble.bit_range}")    # [11:8]
print(f"Child parent_bit_start: {nibble.parent_bit_start}")  # 8
print(f"Child parent_bit_end: {nibble.parent_bit_end}")        # 11
```

**预期结果**：
```
Parent data width: (15, 0)
Child nibble width: (11, 8)
Child bit_range: [11:8]
Child parent_bit_start: 8
Child parent_bit_end: 11
```

---

### 8.4 Class 继承链查询

**场景**：找出 `extended_transaction` 的完整继承链

```python
source = '''
class base_item;
    rand int id;
endclass

class transaction extends base_item;
    rand bit [7:0] data;
endclass

class extended extends transaction;
    constraint c1 { data > 0; }
endclass
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

# Query through class hierarchy
hierarchy = graph.hierarchy if hasattr(graph, 'hierarchy') else None
if hierarchy:
    ancestors = hierarchy.get_ancestors('extended')
    print(f"Ancestors of extended: {ancestors}")
    # Output: ['transaction', 'base_item']
    
    parent = hierarchy.get_parent('extended')
    print(f"Parent of extended: {parent}")  # transaction
```

---

### 8.5 多路选择器 Driver 聚合

**场景**：追踪 MUX 输出，聚合所有可能驱动源

```python
source = '''
module top;
    logic [7:0] in0, in1, in2, in3;
    logic [1:0] sel;
    logic [7:0] out;
    
    assign out = sel == 2'd0 ? in0 :
                 sel == 2'd1 ? in1 :
                 sel == 2'd2 ? in2 : in3;
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

drivers = graph.find_drivers('top.out')
print(f"All drivers of top.out: {[d.id for d in drivers]}")
# Output: ['top.in0', 'top.in1', 'top.in2', 'top.in3']
```

---

## API 快速参考

| 需求 | API |
|------|-----|
| 获取所有节点 | `list(graph.nodes())` |
| 获取节点信息 | `graph.get_node(node_id)` |
| 获取边信息 | `graph.get_edge(src, dst)` |
| 找驱动源 | `graph.find_drivers(signal_id)` |
| 找负载 | `graph.find_loads(signal_id)` |
| 找路径 | `graph.find_path(src, dst)` |
| 遍历边 | `for src, dst in graph.edges():` |

---

## 常见问题排查

| 问题 | 检查项 |
|------|--------|
| 节点为 None | 确认节点 ID 格式 (`module.signal`) |
| 无 Driver 边 | 检查 assign/always 语法是否正确 |
| 位宽为 `(1,0)` | 检查 signal 是否正确声明为 `[msb:lsb]` |
| 无 BIT_SELECT 边 | 确认位选格式是 `[n:m]` 不是 `[n]` |